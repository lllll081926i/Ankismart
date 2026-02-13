from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from ankismart.anki_gateway.apkg_exporter import ApkgExporter
from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.gateway import AnkiGateway, UpdateMode
from ankismart.card_gen.generator import CardGenerator
from ankismart.card_gen.llm_client import LLMClient
from ankismart.core.config import LLMProviderConfig
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft, GenerateRequest, MarkdownResult
from ankismart.core.models import BatchConvertResult, ConvertedDocument

if TYPE_CHECKING:
    from ankismart.converter.converter import DocumentConverter

# Keep monkeypatch target available while avoiding startup import cost.
DocumentConverter = None

logger = get_logger(__name__)


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

            result = self._converter.convert(
                self._file_path,
                progress_callback=progress_callback
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class GenerateWorker(QThread):
    """Worker thread for card generation."""

    progress = pyqtSignal(str)  # Progress message
    finished = pyqtSignal(list)  # list[CardDraft]
    error = pyqtSignal(str)  # Error message
    cancelled = pyqtSignal()

    def __init__(
        self,
        generator: CardGenerator,
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
            self.error.emit(str(e))


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

            self.progress.emit(f"正在推送 {len(self._cards)} 张卡片到 Anki")

            # Push with progress tracking
            result = self._gateway.push(self._cards, update_mode=self._update_mode)

            if self._cancelled:
                self.cancelled.emit()
                return

            self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))


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
            self.error.emit(str(e))


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
            self.finished.emit(False, str(exc))


class BatchConvertWorker(QThread):
    """Worker thread for batch conversion with progress and retry support."""

    file_progress = pyqtSignal(str, int, int)
    page_progress = pyqtSignal(str, int, int)  # file_name, current_page, total_pages
    ocr_progress = pyqtSignal(str)
    file_error = pyqtSignal(str)
    file_completed = pyqtSignal(str, object)  # file_name, ConvertedDocument
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, file_paths: list[Path], config: Any = None) -> None:
        super().__init__()
        self._file_paths = list(file_paths)
        self._config = config
        self._cancelled = False
        self._start_time = 0.0

    def cancel(self) -> None:
        """Cancel the conversion operation."""
        self._cancelled = True
        self.cancelled.emit()

    def run(self) -> None:
        import time
        from ankismart.core.config import save_config
        from ankismart.converter.detector import detect_file_type

        try:
            self._start_time = time.time()
            documents: list[ConvertedDocument] = []
            errors: list[str] = []
            total = len(self._file_paths)

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

            # Process text files first (fast, direct to MD)
            for index, file_path in enumerate(text_files, 1):
                if self._cancelled:
                    self.cancelled.emit()
                    return

                self.file_progress.emit(file_path.name, index, total)

                converted = self._convert_with_retry(file_path)
                if converted is None:
                    continue

                doc = ConvertedDocument(result=converted, file_name=file_path.name)
                documents.append(doc)
                self.file_completed.emit(file_path.name, doc)

            # Process PDF files (check text layer first)
            for index, file_path in enumerate(pdf_files, len(text_files) + 1):
                if self._cancelled:
                    self.cancelled.emit()
                    return

                self.file_progress.emit(file_path.name, index, total)

                converted = self._convert_with_retry(file_path)
                if converted is None:
                    continue

                doc = ConvertedDocument(result=converted, file_name=file_path.name)
                documents.append(doc)
                self.file_completed.emit(file_path.name, doc)

            # Merge all images into one PDF and OCR
            if image_files:
                if self._cancelled:
                    self.cancelled.emit()
                    return

                index = len(text_files) + len(pdf_files) + 1
                self.file_progress.emit("图片合集", index, total)

                merged_result = self._merge_and_convert_images(image_files)
                if merged_result is not None:
                    doc = ConvertedDocument(result=merged_result, file_name="图片合集")
                    documents.append(doc)
                    self.file_completed.emit("图片合集", doc)

            # Process other files (convert to PDF then OCR)
            for index, file_path in enumerate(other_files, len(text_files) + len(pdf_files) + (1 if image_files else 0) + 1):
                if self._cancelled:
                    self.cancelled.emit()
                    return

                self.file_progress.emit(file_path.name, index, total)

                converted = self._convert_with_retry(file_path)
                if converted is None:
                    continue

                doc = ConvertedDocument(result=converted, file_name=file_path.name)
                documents.append(doc)
                self.file_completed.emit(file_path.name, doc)

            if self._cancelled:
                self.cancelled.emit()
                return

            # Update statistics
            if self._config and documents:
                elapsed_time = time.time() - self._start_time
                self._config.total_files_processed += len(documents)
                self._config.total_conversion_time += elapsed_time
                save_config(self._config)

            batch_result = BatchConvertResult(documents=documents, errors=errors)
            self.finished.emit(batch_result)
        except Exception as exc:
            if not self._cancelled:
                self.error.emit(str(exc))

    def _merge_and_convert_images(self, image_files: list[Path]) -> MarkdownResult | None:
        """Merge multiple images into one PDF and convert via OCR."""
        try:
            from PIL import Image
            import pypdfium2 as pdfium
            import tempfile
            import os

            self.ocr_progress.emit(f"正在合并 {len(image_files)} 张图片...")

            # Create temporary PDF
            temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            temp_pdf_path = Path(temp_pdf.name)
            temp_pdf.close()

            try:
                # Load all images
                images = []
                for img_path in image_files:
                    try:
                        img = Image.open(img_path)
                        # Convert to RGB if necessary
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        images.append(img)
                    except Exception as e:
                        self.ocr_progress.emit(f"无法加载图片 {img_path.name}: {e}")
                        continue

                if not images:
                    self.file_error.emit("图片合集: 没有可用的图片")
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
                        append_images=images[1:]
                    )

                # Close images
                for img in images:
                    img.close()

                self.ocr_progress.emit("图片合并完成，开始 OCR 识别...")

                # Convert PDF via OCR
                converter_cls = DocumentConverter
                if converter_cls is None:
                    from ankismart.converter.converter import DocumentConverter as converter_cls

                converter = converter_cls()

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
                # Clean up temporary PDF
                try:
                    if temp_pdf_path.exists():
                        os.unlink(temp_pdf_path)
                except Exception:
                    pass

        except Exception as exc:
            self.file_error.emit(f"图片合集: {exc}")
            return None

    def _convert_with_retry(self, file_path: Path) -> MarkdownResult | None:
        last_error: Exception | None = None

        for _ in range(2):
            if self._cancelled:
                return None

            try:
                converter_cls = DocumentConverter
                if converter_cls is None:
                    from ankismart.converter.converter import DocumentConverter as converter_cls

                converter = converter_cls()

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

        message = f"{file_path.name}: {last_error}" if last_error else f"{file_path.name}: unknown error"
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
        llm_client: LLMClient,
        deck_name: str,
        tags: list[str],
        enable_auto_split: bool = False,
        split_threshold: int = 70000,
        config: Any = None,
    ) -> None:
        super().__init__()
        self._documents = documents
        self._generation_config = generation_config
        self._llm_client = llm_client
        self._deck_name = deck_name
        self._tags = tags
        self._cancelled = False
        self._enable_auto_split = enable_auto_split
        self._split_threshold = split_threshold
        self._config = config
        self._start_time = 0.0

    def cancel(self) -> None:
        """Cancel the generation operation."""
        self._cancelled = True

    def run(self) -> None:
        import time
        import concurrent.futures
        from ankismart.core.config import save_config

        try:
            self._start_time = time.time()

            # Extract configuration
            target_total = self._generation_config.get("target_total", 20)
            strategy_mix = self._generation_config.get("strategy_mix", [])
            max_workers = getattr(self._config, "llm_concurrency", 2) if self._config else 2

            # 0 means unlimited
            if max_workers == 0:
                max_workers = None

            if not strategy_mix:
                self.error.emit("No strategy mix configured")
                return

            if not self._documents:
                self.error.emit("No documents to generate cards from")
                return

            # Step 1: Allocate card counts per strategy
            strategy_counts = self._allocate_mix_counts(target_total, strategy_mix)
            if not strategy_counts:
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

            def generate_for_document(doc_idx: int, document: ConvertedDocument) -> list[CardDraft]:
                """Generate cards for a single document."""
                nonlocal cards_generated

                if self._cancelled:
                    return []

                allocation = per_doc_allocations[doc_idx]
                if not allocation:
                    return []

                self.progress.emit(
                    f"正在为 {document.file_name} 生成卡片 ({doc_idx + 1}/{len(self._documents)})"
                )

                doc_cards: list[CardDraft] = []
                generator = CardGenerator(self._llm_client)

                # Generate cards for each strategy in this document's allocation
                for strategy, count in allocation.items():
                    if self._cancelled:
                        return doc_cards

                    if count <= 0:
                        continue

                    self.progress.emit(
                        f"正在从 {document.file_name} 生成 {count} 张 {strategy} 卡片"
                    )

                    try:
                        request = GenerateRequest(
                            markdown=document.result.content,
                            strategy=strategy,
                            deck_name=self._deck_name,
                            tags=self._tags,
                            trace_id=document.result.trace_id,
                            source_path=document.result.source_path,
                            target_count=count,
                            enable_auto_split=self._enable_auto_split,
                            split_threshold=self._split_threshold,
                        )

                        cards = generator.generate(request)
                        doc_cards.extend(cards)

                        # Update progress with lock
                        with cards_lock:
                            cards_generated += len(cards)
                            self.card_progress.emit(cards_generated, total_cards_to_generate)

                    except Exception as e:
                        # Log error but continue with other strategies
                        self.progress.emit(
                            f"生成 {strategy} 卡片时出错 ({document.file_name}): {str(e)}"
                        )

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
                    if self._cancelled:
                        # Cancel all pending futures
                        for f in future_to_doc:
                            f.cancel()
                        self.cancelled.emit()
                        return

                    try:
                        cards = future.result()
                        all_cards.extend(cards)
                    except Exception as e:
                        idx, doc = future_to_doc[future]
                        self.progress.emit(f"处理 {doc.file_name} 时出错: {str(e)}")

            if self._cancelled:
                self.cancelled.emit()
                return

            # Update statistics
            if self._config and all_cards:
                elapsed_time = time.time() - self._start_time
                self._config.total_generation_time += elapsed_time
                self._config.total_cards_generated += len(all_cards)
                save_config(self._config)

            self.finished.emit(all_cards)

        except Exception as e:
            self.error.emit(str(e))

    @staticmethod
    def _allocate_mix_counts(target_total: int, ratio_items: list[dict[str, Any]]) -> dict[str, int]:
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
        counts: dict[str, int] = {strategy: int(amount) for strategy, amount in raw_allocations.items()}

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
