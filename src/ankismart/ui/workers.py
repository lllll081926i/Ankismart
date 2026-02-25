from __future__ import annotations

import re
import threading
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QThread, pyqtSignal

from ankismart.anki_gateway.apkg_exporter import ApkgExporter
from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.gateway import AnkiGateway, UpdateMode
from ankismart.core.config import LLMProviderConfig, record_operation_metric
from ankismart.core.errors import AnkiSmartError
from ankismart.core.logging import get_logger
from ankismart.core.models import (
    BatchConvertResult,
    CardDraft,
    ConvertedDocument,
    GenerateRequest,
    MarkdownResult,
)

if TYPE_CHECKING:
    from ankismart.card_gen.llm_client import LLMClient
    from ankismart.converter.converter import DocumentConverter

# Keep monkeypatch target available while avoiding startup import cost.
DocumentConverter = None

logger = get_logger(__name__)


def _format_error_for_ui(exc: Exception) -> str:
    """Preserve structured error code in UI error payload."""
    if isinstance(exc, AnkiSmartError):
        return f"[{exc.code}] {exc.message}"
    return str(exc)


def _load_card_generator_class():
    from ankismart.card_gen.generator import CardGenerator as CardGeneratorClass

    return CardGeneratorClass


class CardGenerator:
    """Lazy proxy to keep monkeypatch target stable and defer heavy import."""

    def __init__(self, *args, **kwargs) -> None:
        self._impl = _load_card_generator_class()(*args, **kwargs)

    def generate(self, request):
        return self._impl.generate(request)


def _normalize_text_for_quality(text: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", text or "")
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain


def _extract_question_text(card: CardDraft) -> str:
    for key in ("Front", "Question", "Text"):
        value = str(card.fields.get(key, "") or "")
        if value.strip():
            return _normalize_text_for_quality(value)
    if card.fields:
        return _normalize_text_for_quality(str(next(iter(card.fields.values())) or ""))
    return ""


def _extract_answer_text(card: CardDraft) -> str:
    for key in ("Back", "Answer", "Extra"):
        value = str(card.fields.get(key, "") or "")
        if value.strip():
            return _normalize_text_for_quality(value)
    if (card.note_type or "").startswith("Cloze"):
        return _normalize_text_for_quality(str(card.fields.get("Text", "") or ""))
    chunks = []
    for key, value in card.fields.items():
        if key in {"Front", "Question", "Text"}:
            continue
        text = str(value or "").strip()
        if text:
            chunks.append(text)
    return _normalize_text_for_quality(" ".join(chunks))


def _card_quality_issue(card: CardDraft, *, min_chars: int) -> str | None:
    question = _extract_question_text(card)
    answer = _extract_answer_text(card)
    if len(question) < min_chars:
        return "question_too_short"
    if len(answer) < min_chars:
        return "answer_too_short"
    if not (card.note_type or "").startswith("Cloze") and question == answer:
        return "question_equals_answer"
    return None


def _is_semantic_duplicate(
    question: str,
    existing_questions: list[str],
    *,
    threshold: float,
) -> bool:
    if not question:
        return False
    normalized = question.lower()
    for candidate in existing_questions:
        if not candidate:
            continue
        if SequenceMatcher(None, normalized, candidate.lower()).ratio() >= threshold:
            return True
    return False


def _ocr_markdown_quality_warning(text: str, *, min_chars: int) -> str | None:
    normalized = _normalize_text_for_quality(text)
    if len(normalized) < min_chars:
        return f"content_too_short<{min_chars}"

    replacement_count = normalized.count("\ufffd")
    if replacement_count > 0:
        ratio = replacement_count / max(1, len(normalized))
        if ratio > 0.01:
            return f"replacement_char_ratio={ratio:.3f}"

    useful = sum(1 for ch in normalized if (ch.isalnum() or ("\u4e00" <= ch <= "\u9fff")))
    useful_ratio = useful / max(1, len(normalized))
    if useful_ratio < 0.35:
        return f"useful_char_ratio={useful_ratio:.3f}"

    return None


class ConvertWorker(QThread):
    """Worker thread for file conversion."""

    progress = pyqtSignal(str)  # Progress message
    finished = pyqtSignal(object)  # MarkdownResult
    error = pyqtSignal(str)  # Error message
    cancelled = pyqtSignal()

    def __init__(self, converter: "DocumentConverter", file_path: Path) -> None:
        super().__init__()
        self._converter = converter
        self._file_path = file_path

    def run(self) -> None:
        try:
            self.progress.emit(f"正在转换文件: {self._file_path.name}")

            def progress_callback(msg: str) -> None:
                self.progress.emit(msg)

            result = self._converter.convert(self._file_path, progress_callback=progress_callback)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(_format_error_for_ui(e))


class GenerateWorker(QThread):
    """Worker thread for card generation."""

    progress = pyqtSignal(str)  # Progress message
    finished = pyqtSignal(list)  # list[CardDraft]
    error = pyqtSignal(str)  # Error message
    cancelled = pyqtSignal()

    def __init__(
        self,
        generator: "CardGenerator",
        markdown_result: MarkdownResult,
        deck_name: str,
        tags: list[str],
        strategy: str,
        target_count: int = 0,
    ) -> None:
        super().__init__()
        self._generator = generator
        self._markdown_result = markdown_result
        self._deck_name = deck_name
        self._tags = tags
        self._strategy = strategy
        self._target_count = target_count

    def run(self) -> None:
        try:
            self.progress.emit(f"正在生成卡片 (策略: {self._strategy})")

            request = GenerateRequest(
                markdown=self._markdown_result.content,
                strategy=self._strategy,
                deck_name=self._deck_name,
                tags=self._tags,
                trace_id=self._markdown_result.trace_id,
                source_path=self._markdown_result.source_path,
                target_count=self._target_count,
            )

            cards = self._generator.generate(request)
            self.finished.emit(cards)
        except Exception as e:
            self.error.emit(_format_error_for_ui(e))


class PushWorker(QThread):
    """Worker thread for pushing cards to Anki."""

    progress = pyqtSignal(str)  # Progress message
    card_progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(object)  # PushResult
    error = pyqtSignal(str)  # Error message
    cancelled = pyqtSignal()

    def __init__(
        self,
        gateway: AnkiGateway,
        cards: list[CardDraft],
        update_mode: UpdateMode = "create_only",
    ) -> None:
        super().__init__()
        self._gateway = gateway
        self._cards = cards
        self._update_mode = update_mode
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel the push operation."""
        self._cancelled = True

    def run(self) -> None:
        try:
            if self._cancelled:
                self.cancelled.emit()
                return

            logger.info(
                "push workflow started",
                extra={
                    "event": "worker.push.started",
                    "cards_count": len(self._cards),
                    "update_mode": self._update_mode,
                },
            )
            self.progress.emit(f"正在推送 {len(self._cards)} 张卡片到 Anki")

            # Push with progress tracking
            result = self._gateway.push(self._cards, update_mode=self._update_mode)

            if self._cancelled:
                self.cancelled.emit()
                return

            logger.info(
                "push workflow finished",
                extra={
                    "event": "worker.push.finished",
                    "cards_count": len(self._cards),
                    "succeeded": getattr(result, "succeeded", None),
                    "failed": getattr(result, "failed", None),
                },
            )
            self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                logger.exception(
                    "push workflow failed",
                    extra={"event": "worker.push.failed"},
                )
                self.error.emit(_format_error_for_ui(e))


class ExportWorker(QThread):
    """Worker thread for exporting cards to APKG."""

    progress = pyqtSignal(str)  # Progress message
    finished = pyqtSignal(str)  # Output path
    error = pyqtSignal(str)  # Error message
    cancelled = pyqtSignal()

    def __init__(
        self,
        exporter: ApkgExporter,
        cards: list[CardDraft],
        output_path: Path,
    ) -> None:
        super().__init__()
        self._exporter = exporter
        self._cards = cards
        self._output_path = output_path

    def run(self) -> None:
        try:
            self.progress.emit(f"正在导出 {len(self._cards)} 张卡片到 APKG")
            result_path = self._exporter.export(self._cards, self._output_path)
            self.finished.emit(str(result_path))
        except Exception as e:
            self.error.emit(_format_error_for_ui(e))


class ConnectionCheckWorker(QThread):
    """Worker thread for checking AnkiConnect connectivity."""

    finished = pyqtSignal(bool)

    def __init__(self, url: str, key: str, proxy_url: str = "") -> None:
        super().__init__()
        self._url = url
        self._key = key
        self._proxy_url = proxy_url

    def run(self) -> None:
        try:
            client = AnkiConnectClient(url=self._url, key=self._key, proxy_url=self._proxy_url)
            self.finished.emit(client.check_connection())
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"AnkiConnect connection check failed: {e}")
            self.finished.emit(False)


class ProviderConnectionWorker(QThread):
    """Worker thread for checking LLM provider connectivity."""

    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        provider: LLMProviderConfig,
        *,
        proxy_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 0,
    ) -> None:
        super().__init__()
        self._provider = provider
        self._proxy_url = proxy_url
        self._temperature = temperature
        self._max_tokens = max_tokens

    def run(self) -> None:
        try:
            from ankismart.card_gen.llm_client import LLMClient

            client = LLMClient(
                api_key=self._provider.api_key,
                model=self._provider.model,
                base_url=self._provider.base_url or None,
                rpm_limit=self._provider.rpm_limit,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                proxy_url=self._proxy_url,
            )
            ok = client.validate_connection()
            self.finished.emit(ok, "")
        except Exception as exc:
            self.finished.emit(False, _format_error_for_ui(exc))


class OCRCloudConnectionWorker(QThread):
    """Worker thread for checking cloud OCR connectivity."""

    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        *,
        provider: str,
        endpoint: str,
        api_key: str,
        proxy_url: str = "",
    ) -> None:
        super().__init__()
        self._provider = provider
        self._endpoint = endpoint
        self._api_key = api_key
        self._proxy_url = proxy_url

    def run(self) -> None:
        try:
            from ankismart.converter.ocr_converter import test_cloud_connectivity

            ok, detail = test_cloud_connectivity(
                cloud_provider=self._provider,
                cloud_endpoint=self._endpoint,
                cloud_api_key=self._api_key,
                proxy_url=self._proxy_url,
            )
            self.finished.emit(ok, detail)
        except Exception as exc:
            self.finished.emit(False, _format_error_for_ui(exc))


class BatchConvertWorker(QThread):
    """Worker thread for batch conversion with progress and retry support."""

    file_progress = pyqtSignal(str, int, int)
    page_progress = pyqtSignal(str, int, int)  # file_name, current_page, total_pages
    ocr_progress = pyqtSignal(str)
    file_error = pyqtSignal(str)
    file_warning = pyqtSignal(str)
    file_completed = pyqtSignal(str, object)  # file_name, ConvertedDocument
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, file_paths: list[Path], config: Any = None) -> None:
        super().__init__()
        self._file_paths = list(file_paths)
        self._config = config
        self._cancelled = False
        self._cancel_event = threading.Event()
        self._start_time = 0.0
        self._last_file_error_message: str | None = None
        self._ocr_correction_fn = None
        self._ocr_correction_fn_ready = False
        self._quality_warnings: list[str] = []
        self._ocr_quality_min_chars = int(getattr(config, "ocr_quality_min_chars", 80))

    def cancel(self) -> None:
        """Cancel the conversion operation."""
        cancel_event = self.__dict__.get("_cancel_event")
        if cancel_event is not None:
            cancel_event.set()
        self._cancelled = True

    def _is_cancelled(self) -> bool:
        cancel_event = self.__dict__.get("_cancel_event")
        cancelled = bool(self.__dict__.get("_cancelled", False))
        return cancelled or bool(cancel_event is not None and cancel_event.is_set())

    def run(self) -> None:
        import time

        from ankismart.converter.detector import detect_file_type
        from ankismart.core.config import record_operation_metric, save_config

        try:
            self._start_time = time.time()
            documents: list[ConvertedDocument] = []
            errors: list[str] = []
            total = len(self._file_paths)
            logger.info(
                "batch conversion started",
                extra={"event": "worker.batch_convert.started", "total_files": total},
            )

            # Separate files by type
            text_files: list[Path] = []
            pdf_files: list[Path] = []
            image_files: list[Path] = []
            other_files: list[Path] = []

            for file_path in self._file_paths:
                try:
                    file_type = detect_file_type(file_path)
                    if file_type == "image":
                        image_files.append(file_path)
                    elif file_type == "pdf":
                        pdf_files.append(file_path)
                    elif file_type in {"markdown", "text", "docx", "pptx"}:
                        text_files.append(file_path)
                    else:
                        other_files.append(file_path)
                except Exception:
                    other_files.append(file_path)

            logger.info(
                "batch conversion grouped files",
                extra={
                    "event": "worker.batch_convert.grouped",
                    "text_files": len(text_files),
                    "pdf_files": len(pdf_files),
                    "image_files": len(image_files),
                    "other_files": len(other_files),
                },
            )

            # Process text files first (fast, direct to MD)
            for index, file_path in enumerate(text_files, 1):
                if self._is_cancelled():
                    self.cancelled.emit()
                    return

                self.file_progress.emit(file_path.name, index, total)

                converted = self._convert_with_retry(file_path)
                if converted is None:
                    if self._last_file_error_message:
                        errors.append(self._last_file_error_message)
                        self._last_file_error_message = None
                    continue

                doc = ConvertedDocument(result=converted, file_name=file_path.name)
                documents.append(doc)
                self._check_ocr_quality(file_path.name, converted)
                self.file_completed.emit(file_path.name, doc)

            # Process PDF files (check text layer first)
            for index, file_path in enumerate(pdf_files, len(text_files) + 1):
                if self._is_cancelled():
                    self.cancelled.emit()
                    return

                self.file_progress.emit(file_path.name, index, total)

                converted = self._convert_with_retry(file_path)
                if converted is None:
                    if self._last_file_error_message:
                        errors.append(self._last_file_error_message)
                        self._last_file_error_message = None
                    continue

                doc = ConvertedDocument(result=converted, file_name=file_path.name)
                documents.append(doc)
                self.file_completed.emit(file_path.name, doc)

            # Merge all images into one PDF and OCR
            if image_files:
                if self._is_cancelled():
                    self.cancelled.emit()
                    return

                index = len(text_files) + len(pdf_files) + 1
                self.file_progress.emit("图片合集", index, total)

                merged_result = self._merge_and_convert_images(image_files)
                if merged_result is not None:
                    doc = ConvertedDocument(result=merged_result, file_name="图片合集")
                    documents.append(doc)
                    self._check_ocr_quality("图片合集", merged_result)
                    self.file_completed.emit("图片合集", doc)
                elif self._last_file_error_message:
                    errors.append(self._last_file_error_message)
                    self._last_file_error_message = None

            # Process other files (convert to PDF then OCR)
            for index, file_path in enumerate(
                other_files, len(text_files) + len(pdf_files) + (1 if image_files else 0) + 1
            ):
                if self._is_cancelled():
                    self.cancelled.emit()
                    return

                self.file_progress.emit(file_path.name, index, total)

                converted = self._convert_with_retry(file_path)
                if converted is None:
                    if self._last_file_error_message:
                        errors.append(self._last_file_error_message)
                        self._last_file_error_message = None
                    continue

                doc = ConvertedDocument(result=converted, file_name=file_path.name)
                documents.append(doc)
                self._check_ocr_quality(file_path.name, converted)
                self.file_completed.emit(file_path.name, doc)

            if self._is_cancelled():
                self.cancelled.emit()
                return

            # Update statistics
            if self._config and documents:
                elapsed_time = time.time() - self._start_time
                self._config.total_files_processed += len(documents)
                self._config.total_conversion_time += elapsed_time
                record_operation_metric(
                    self._config,
                    event="convert",
                    duration_seconds=elapsed_time,
                    success=len(errors) == 0,
                    error_code="partial_failure" if errors else "",
                )
                save_config(self._config)

            batch_result = BatchConvertResult(
                documents=documents, errors=errors, warnings=self._quality_warnings
            )
            logger.info(
                "batch conversion finished",
                extra={
                    "event": "worker.batch_convert.finished",
                    "total_files": total,
                    "converted_files": len(documents),
                    "failed_files": len(errors),
                    "quality_warnings": len(self._quality_warnings),
                    "duration_ms": round((time.time() - self._start_time) * 1000, 2),
                },
            )
            self.finished.emit(batch_result)
        except Exception as exc:
            if not self._is_cancelled():
                logger.exception(
                    "batch conversion failed",
                    extra={"event": "worker.batch_convert.failed"},
                )
                if self._config:
                    elapsed_time = (
                        max(0.0, time.time() - self._start_time) if self._start_time else 0.0
                    )
                    record_operation_metric(
                        self._config,
                        event="convert",
                        duration_seconds=elapsed_time,
                        success=False,
                        error_code="worker_exception",
                    )
                    save_config(self._config)
                self.error.emit(_format_error_for_ui(exc))
        finally:
            self._release_ocr_runtime()

    @staticmethod
    def _release_ocr_runtime() -> None:
        """Release OCR engine after batch conversion to avoid long-lived memory usage."""
        try:
            from ankismart.converter.ocr_converter import release_ocr_runtime
        except Exception:
            return

        try:
            release_ocr_runtime(reason="batch_convert_finished")
        except Exception as exc:
            logger.debug(f"Failed to release OCR runtime after batch conversion: {exc}")

    def _resolve_ocr_correction_fn(self):
        if self._ocr_correction_fn_ready:
            return self._ocr_correction_fn

        self._ocr_correction_fn_ready = True
        if not self._config or not getattr(self._config, "ocr_correction", False):
            self._ocr_correction_fn = None
            return None

        provider = getattr(self._config, "active_provider", None)
        if provider is None:
            raise ValueError("OCR correction is enabled but no active provider is configured")
        if not getattr(provider, "model", ""):
            raise ValueError(f"Provider '{provider.name}' requires a model for OCR correction")
        if "Ollama" not in provider.name and not getattr(provider, "api_key", "").strip():
            raise ValueError(f"Provider '{provider.name}' requires an API key for OCR correction")

        proxy_mode = str(getattr(self._config, "proxy_mode", "system"))
        proxy_url = (
            str(getattr(self._config, "proxy_url", "")).strip() if proxy_mode == "manual" else ""
        )

        from ankismart.card_gen.generator import CardGenerator
        from ankismart.card_gen.llm_client import LLMClient

        llm_client = LLMClient(
            api_key=provider.api_key,
            model=provider.model,
            base_url=provider.base_url or None,
            rpm_limit=getattr(provider, "rpm_limit", 0),
            temperature=float(getattr(self._config, "llm_temperature", 0.3)),
            max_tokens=int(getattr(self._config, "llm_max_tokens", 0)),
            proxy_url=proxy_url,
        )
        generator = CardGenerator(llm_client)
        self._ocr_correction_fn = generator.correct_ocr_text
        return self._ocr_correction_fn

    def _check_ocr_quality(self, file_name: str, result: MarkdownResult) -> None:
        warning = _ocr_markdown_quality_warning(
            result.content,
            min_chars=max(10, self._ocr_quality_min_chars),
        )
        if not warning:
            return
        message = f"{file_name}: OCR质量警告({warning})"
        self._quality_warnings.append(message)
        self.file_warning.emit(message)

    def _build_converter(self):
        converter_class = DocumentConverter
        if converter_class is None:
            from ankismart.converter.converter import DocumentConverter as DocumentConverterClass

            converter_class = DocumentConverterClass

        proxy_mode = str(getattr(self._config, "proxy_mode", "system"))
        proxy_url = (
            str(getattr(self._config, "proxy_url", "")).strip() if proxy_mode == "manual" else ""
        )

        return converter_class(
            ocr_correction_fn=self._resolve_ocr_correction_fn(),
            ocr_mode=str(getattr(self._config, "ocr_mode", "local")),
            ocr_cloud_provider=str(getattr(self._config, "ocr_cloud_provider", "")).strip(),
            ocr_cloud_endpoint=str(getattr(self._config, "ocr_cloud_endpoint", "")).strip(),
            ocr_cloud_api_key=str(getattr(self._config, "ocr_cloud_api_key", "")).strip(),
            proxy_url=proxy_url,
        )

    def _merge_and_convert_images(self, image_files: list[Path]) -> MarkdownResult | None:
        """Merge multiple images into one PDF and convert via OCR."""
        try:
            import os
            import tempfile

            from PIL import Image

            self.ocr_progress.emit(f"正在合并 {len(image_files)} 张图片...")

            # Create temporary PDF
            temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            temp_pdf_path = Path(temp_pdf.name)
            temp_pdf.close()
            images: list[Image.Image] = []

            try:
                # Load all images
                for img_path in image_files:
                    try:
                        with Image.open(img_path) as opened:
                            # Copy image data to detach from file descriptor.
                            img = opened.convert("RGB") if opened.mode != "RGB" else opened.copy()
                            images.append(img)
                    except Exception as e:
                        self.ocr_progress.emit(f"无法加载图片 {img_path.name}: {e}")
                        continue

                if not images:
                    message = "图片合集: 没有可用的图片"
                    self._last_file_error_message = message
                    self.file_error.emit(message)
                    return None

                # Save as PDF
                if len(images) == 1:
                    images[0].save(temp_pdf_path, "PDF", resolution=100.0)
                else:
                    images[0].save(
                        temp_pdf_path,
                        "PDF",
                        resolution=100.0,
                        save_all=True,
                        append_images=images[1:],
                    )

                self.ocr_progress.emit("图片合并完成，开始 OCR 识别...")

                # Convert PDF via OCR
                converter = self._build_converter()

                def progress_callback(*args):
                    if len(args) == 3:
                        current_page, total_pages, message = args
                        self.page_progress.emit("图片合集", int(current_page), int(total_pages))
                        self.ocr_progress.emit(str(message))
                        return

                    if len(args) == 1:
                        self.ocr_progress.emit(str(args[0]))
                        return

                    if len(args) >= 2:
                        current_page, total_pages = args[:2]
                        self.page_progress.emit("图片合集", int(current_page), int(total_pages))

                result = converter.convert(temp_pdf_path, progress_callback=progress_callback)

                # Update source path to indicate it's from merged images
                result.source_path = "图片合集"

                return result
            finally:
                for image in images:
                    close_fn = getattr(image, "close", None)
                    if callable(close_fn):
                        close_fn()
                try:
                    if temp_pdf_path.exists():
                        os.unlink(temp_pdf_path)
                except Exception:
                    pass

        except Exception as exc:
            message = f"图片合集: {exc}"
            self._last_file_error_message = message
            logger.warning(
                "image merge conversion failed",
                extra={
                    "event": "worker.batch_convert.image_merge_failed",
                    "error_detail": str(exc),
                },
            )
            self.file_error.emit(message)
            return None

    def _convert_with_retry(self, file_path: Path) -> MarkdownResult | None:
        last_error: Exception | None = None

        for attempt in range(2):
            if self._is_cancelled():
                return None

            try:
                converter = self._build_converter()

                # Create progress callback that emits page progress
                def progress_callback(*args):
                    if len(args) == 3:
                        current_page, total_pages, message = args
                        self.page_progress.emit(file_path.name, int(current_page), int(total_pages))
                        self.ocr_progress.emit(str(message))
                        return

                    if len(args) == 1:
                        self.ocr_progress.emit(str(args[0]))
                        return

                    if len(args) >= 2:
                        current_page, total_pages = args[:2]
                        self.page_progress.emit(file_path.name, int(current_page), int(total_pages))

                return converter.convert(file_path, progress_callback=progress_callback)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "file conversion attempt failed",
                    extra={
                        "event": "worker.batch_convert.retry",
                        "file_name": file_path.name,
                        "attempt": attempt + 1,
                        "error_detail": str(exc),
                    },
                )

        message = (
            f"{file_path.name}: {last_error}" if last_error else f"{file_path.name}: unknown error"
        )
        self._last_file_error_message = message
        self.file_error.emit(message)
        return None


class BatchGenerateWorker(QThread):
    """Worker thread for batch card generation with concurrent document processing."""

    progress = pyqtSignal(str)
    card_progress = pyqtSignal(int, int)  # current, total
    document_completed = pyqtSignal(str, int)  # document_name, cards_count
    finished = pyqtSignal(list)  # list[CardDraft]
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(
        self,
        documents: list[ConvertedDocument],
        generation_config: dict[str, Any],
        llm_client: "LLMClient",
        deck_name: str,
        tags: list[str],
        enable_auto_split: bool = False,
        split_threshold: int = 70000,
        config: Any = None,
    ) -> None:
        super().__init__()
        # Keep an immutable snapshot to avoid accidental cross-thread mutation.
        self._documents = tuple(documents)
        self._generation_config = generation_config
        self._llm_client = llm_client
        self._deck_name = deck_name
        self._tags = tags
        self._cancelled = False
        self._cancel_event = threading.Event()
        self._enable_auto_split = enable_auto_split
        self._split_threshold = split_threshold
        self._config = config
        self._start_time = 0.0
        threshold = float(getattr(config, "semantic_duplicate_threshold", 0.9))
        self._semantic_duplicate_threshold = min(1.0, max(0.6, threshold))
        self._card_quality_min_chars = int(getattr(config, "card_quality_min_chars", 2))
        self._card_quality_retry_rounds = int(getattr(config, "card_quality_retry_rounds", 2))
        self._adaptive_enabled = bool(getattr(config, "llm_adaptive_concurrency", True))
        self._concurrency_cap = int(getattr(config, "llm_concurrency_max", 6))
        self._throttle_events = 0
        self._timeout_events = 0

    def cancel(self) -> None:
        """Cancel the generation operation."""
        cancel_event = self.__dict__.get("_cancel_event")
        if cancel_event is not None:
            cancel_event.set()
        self._cancelled = True

    def _is_cancelled(self) -> bool:
        cancel_event = self.__dict__.get("_cancel_event")
        cancelled = bool(self.__dict__.get("_cancelled", False))
        return cancelled or bool(cancel_event is not None and cancel_event.is_set())

    def run(self) -> None:
        import concurrent.futures
        import time

        from ankismart.core.config import save_config

        try:
            self._start_time = time.time()

            # Extract configuration
            target_total = self._generation_config.get("target_total", 20)
            strategy_mix = self._generation_config.get("strategy_mix", [])
            configured_workers = getattr(self._config, "llm_concurrency", 2) if self._config else 2
            try:
                configured_workers = int(configured_workers)
            except (TypeError, ValueError):
                configured_workers = 2

            # 0 means auto-size by document count, avoiding ThreadPoolExecutor default cap.
            if configured_workers <= 0:
                max_workers = max(1, len(self._documents))
            else:
                max_workers = configured_workers

            logger.info(
                "batch generation started",
                extra={
                    "event": "worker.batch_generate.started",
                    "documents_count": len(self._documents),
                    "target_total": target_total,
                    "max_workers": max_workers,
                },
            )

            if not strategy_mix:
                logger.warning(
                    "batch generation aborted: no strategy mix",
                    extra={"event": "worker.batch_generate.invalid_input"},
                )
                self.error.emit("No strategy mix configured")
                return

            if not self._documents:
                logger.warning(
                    "batch generation aborted: no documents",
                    extra={"event": "worker.batch_generate.invalid_input"},
                )
                self.error.emit("No documents to generate cards from")
                return

            # Step 1: Allocate card counts per strategy
            strategy_counts = self._allocate_mix_counts(target_total, strategy_mix)
            if not strategy_counts:
                logger.warning(
                    "batch generation aborted: allocation failed",
                    extra={"event": "worker.batch_generate.allocation_failed"},
                )
                self.error.emit("Failed to allocate strategy counts")
                return

            # Step 2: Distribute counts across documents
            per_doc_allocations = self._distribute_counts_per_document(
                len(self._documents), strategy_counts
            )

            # Step 3: Generate cards concurrently for each document
            all_cards: list[CardDraft] = []
            total_cards_to_generate = sum(strategy_counts.values())
            cards_generated = 0
            cards_lock = threading.Lock()
            first_error_message = [None]
            first_error_lock = threading.Lock()

            def generate_for_document(doc_idx: int, document: ConvertedDocument) -> list[CardDraft]:
                """Generate cards for a single document."""
                nonlocal cards_generated

                if self._is_cancelled():
                    return []

                allocation = per_doc_allocations[doc_idx]
                if not allocation:
                    return []

                self.progress.emit(
                    f"正在为 {document.file_name} 生成卡片 ({doc_idx + 1}/{len(self._documents)})"
                )

                doc_cards: list[CardDraft] = []
                accepted_questions: list[str] = []
                generator = CardGenerator(self._llm_client)

                # Generate cards for each strategy in this document's allocation
                for strategy, count in allocation.items():
                    if self._is_cancelled():
                        return doc_cards

                    if count <= 0:
                        continue

                    self.progress.emit(
                        f"正在从 {document.file_name} 生成 {count} 张 {strategy} 卡片"
                    )

                    accepted_for_strategy: list[CardDraft] = []
                    rejected_quality = 0
                    rejected_duplicate = 0
                    max_rounds = max(1, self._card_quality_retry_rounds + 1)
                    rounds_used = 0

                    while len(accepted_for_strategy) < count and rounds_used < max_rounds:
                        rounds_used += 1
                        remaining = count - len(accepted_for_strategy)
                        try:
                            request = GenerateRequest(
                                markdown=document.result.content,
                                strategy=strategy,
                                deck_name=self._deck_name,
                                tags=self._tags,
                                trace_id=document.result.trace_id,
                                source_path=document.result.source_path,
                                target_count=remaining,
                                enable_auto_split=self._enable_auto_split,
                                split_threshold=self._split_threshold,
                            )
                            round_cards = generator.generate(request)
                        except Exception as e:
                            self._mark_runtime_error(e)
                            with first_error_lock:
                                if first_error_message[0] is None:
                                    first_error_message[0] = _format_error_for_ui(e)
                            logger.warning(
                                "strategy generation failed",
                                extra={
                                    "event": "worker.batch_generate.strategy_failed",
                                    "strategy": strategy,
                                    "file_name": document.file_name,
                                    "round": rounds_used,
                                    "error_detail": str(e),
                                },
                            )
                            self.progress.emit(
                                f"生成 {strategy} 卡片时出错 ({document.file_name}): "
                                f"{_format_error_for_ui(e)}"
                            )
                            break

                        if not round_cards:
                            continue

                        for card in round_cards:
                            issue = _card_quality_issue(
                                card, min_chars=max(1, self._card_quality_min_chars)
                            )
                            if issue is not None:
                                rejected_quality += 1
                                continue

                            question = _extract_question_text(card)
                            if _is_semantic_duplicate(
                                question,
                                accepted_questions,
                                threshold=self._semantic_duplicate_threshold,
                            ):
                                rejected_duplicate += 1
                                continue

                            accepted_for_strategy.append(card)
                            accepted_questions.append(question)
                            if len(accepted_for_strategy) >= count:
                                break

                    if rejected_quality or rejected_duplicate:
                        self.progress.emit(
                            f"{document.file_name}/{strategy}: "
                            f"质量过滤 {rejected_quality} 张，近重复过滤 {rejected_duplicate} 张"
                        )
                    if len(accepted_for_strategy) < count:
                        self.progress.emit(
                            f"{document.file_name}/{strategy}: "
                            f"目标 {count} 张，实际 {len(accepted_for_strategy)} 张"
                        )

                    doc_cards.extend(accepted_for_strategy)
                    with cards_lock:
                        cards_generated += len(accepted_for_strategy)
                        self.card_progress.emit(cards_generated, total_cards_to_generate)

                # Emit document completion signal
                if doc_cards:
                    self.document_completed.emit(document.file_name, len(doc_cards))

                return doc_cards

            # Use ThreadPoolExecutor for concurrent generation
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all document generation tasks
                future_to_doc = {
                    executor.submit(generate_for_document, idx, doc): (idx, doc)
                    for idx, doc in enumerate(self._documents)
                }

                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_doc):
                    if self._is_cancelled():
                        # Cancel all pending futures
                        for f in future_to_doc:
                            f.cancel()
                        self.cancelled.emit()
                        return

                    try:
                        cards = future.result()
                        all_cards.extend(cards)
                    except Exception as e:
                        self._mark_runtime_error(e)
                        with first_error_lock:
                            if first_error_message[0] is None:
                                first_error_message[0] = _format_error_for_ui(e)
                        idx, doc = future_to_doc[future]
                        logger.warning(
                            "document generation failed",
                            extra={
                                "event": "worker.batch_generate.document_failed",
                                "document_index": idx,
                                "file_name": doc.file_name,
                                "error_detail": str(e),
                            },
                        )
                        self.progress.emit(
                            f"处理 {doc.file_name} 时出错: {_format_error_for_ui(e)}"
                        )

            if self._is_cancelled():
                self.cancelled.emit()
                return

            if not all_cards and first_error_message[0] is not None:
                self.error.emit(first_error_message[0])
                return

            self._apply_adaptive_concurrency(
                configured_workers=configured_workers,
                had_error=first_error_message[0] is not None,
            )

            # Update statistics
            if self._config and all_cards:
                elapsed_time = time.time() - self._start_time
                self._config.total_generation_time += elapsed_time
                self._config.total_cards_generated += len(all_cards)
                record_operation_metric(
                    self._config,
                    event="generate",
                    duration_seconds=elapsed_time,
                    success=first_error_message[0] is None,
                    error_code="strategy_error" if first_error_message[0] else "",
                )
                save_config(self._config)

            logger.info(
                "batch generation finished",
                extra={
                    "event": "worker.batch_generate.finished",
                    "documents_count": len(self._documents),
                    "cards_generated": len(all_cards),
                    "throttle_events": self._throttle_events,
                    "timeout_events": self._timeout_events,
                    "duration_ms": round((time.time() - self._start_time) * 1000, 2),
                },
            )
            self.finished.emit(all_cards)

        except Exception as e:
            logger.exception(
                "batch generation failed",
                extra={"event": "worker.batch_generate.failed"},
            )
            if self._config:
                elapsed_time = max(0.0, time.time() - self._start_time) if self._start_time else 0.0
                record_operation_metric(
                    self._config,
                    event="generate",
                    duration_seconds=elapsed_time,
                    success=False,
                    error_code="worker_exception",
                )
                save_config(self._config)
            self.error.emit(_format_error_for_ui(e))

    def _mark_runtime_error(self, exc: Exception) -> None:
        message = _format_error_for_ui(exc).lower()
        if "429" in message or "rate limit" in message or "rate_limit" in message:
            self._throttle_events += 1
        if "timeout" in message or "timed out" in message:
            self._timeout_events += 1

    def _apply_adaptive_concurrency(self, *, configured_workers: int, had_error: bool) -> None:
        if not self._config or not self._adaptive_enabled:
            return
        if configured_workers <= 0:
            # Keep "auto" mode unchanged.
            return

        current = int(getattr(self._config, "llm_concurrency", configured_workers))
        if current <= 0:
            return

        next_value = current
        if self._throttle_events > 0 or self._timeout_events > 0:
            next_value = max(1, current - 1)
        elif not had_error:
            next_value = min(max(1, self._concurrency_cap), current + 1)

        if next_value == current:
            return

        self._config.llm_concurrency = next_value
        if next_value < current:
            self.progress.emit(
                f"检测到限流/超时，已自动将并发从 {current} 调整为 {next_value}"
            )
        else:
            self.progress.emit(
                f"运行稳定，已自动将并发从 {current} 调整为 {next_value}"
            )

    @staticmethod
    def _allocate_mix_counts(
        target_total: int, ratio_items: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Allocate card counts to strategies based on ratios.

        Args:
            target_total: Total number of cards to generate
            ratio_items: List of dicts with 'strategy' and 'ratio' keys

        Returns:
            Dictionary mapping strategy names to card counts
        """
        if target_total <= 0 or not ratio_items:
            return {}

        # Normalize and validate ratio items
        normalized: list[tuple[str, float]] = []
        for item in ratio_items:
            strategy = str(item.get("strategy", "")).strip()
            ratio = item.get("ratio")
            if not strategy or not isinstance(ratio, (int, float)) or ratio <= 0:
                continue
            normalized.append((strategy, float(ratio)))

        if not normalized:
            return {}

        # Calculate total ratio sum
        ratio_sum = sum(value for _, value in normalized)
        if ratio_sum <= 0:
            return {}

        # Calculate raw allocations (may have fractional parts)
        raw_allocations: dict[str, float] = {
            strategy: target_total * value / ratio_sum for strategy, value in normalized
        }

        # Floor all allocations
        counts: dict[str, int] = {
            strategy: int(amount) for strategy, amount in raw_allocations.items()
        }

        # Distribute remainder to strategies with largest fractional parts
        remainder = target_total - sum(counts.values())
        if remainder > 0:
            ordered = sorted(
                normalized,
                key=lambda item: raw_allocations[item[0]] - int(raw_allocations[item[0]]),
                reverse=True,
            )
            for i in range(remainder):
                strategy = ordered[i % len(ordered)][0]
                counts[strategy] += 1

        return counts

    @staticmethod
    def _distribute_counts_per_document(
        total_docs: int,
        strategy_counts: dict[str, int],
    ) -> list[dict[str, int]]:
        """Distribute strategy card counts across documents.

        Args:
            total_docs: Number of documents
            strategy_counts: Dictionary mapping strategy names to total card counts

        Returns:
            List of dictionaries, one per document, mapping strategy to count
        """
        if total_docs <= 0:
            return []

        per_doc: list[dict[str, int]] = [dict() for _ in range(total_docs)]

        for strategy, total in strategy_counts.items():
            if total <= 0:
                continue

            # Distribute evenly with remainder handling
            base = total // total_docs
            remainder = total % total_docs

            for idx in range(total_docs):
                # First 'remainder' documents get one extra card
                value = base + (1 if idx < remainder else 0)
                if value > 0:
                    per_doc[idx][strategy] = value

        return per_doc
