from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from ankismart.anki_gateway.apkg_exporter import ApkgExporter
from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.gateway import AnkiGateway, UpdateMode
from ankismart.card_gen.generator import CardGenerator
from ankismart.card_gen.llm_client import LLMClient
from ankismart.converter.converter import DocumentConverter
from ankismart.core.config import LLMProviderConfig
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft, GenerateRequest, MarkdownResult
from ankismart.core.models import BatchConvertResult, ConvertedDocument

logger = get_logger(__name__)


class ConvertWorker(QThread):
    """Worker thread for file conversion."""

    progress = pyqtSignal(str)  # Progress message
    finished = pyqtSignal(object)  # MarkdownResult
    error = pyqtSignal(str)  # Error message
    cancelled = pyqtSignal()

    def __init__(self, converter: DocumentConverter, file_path: Path) -> None:
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

        try:
            self._start_time = time.time()
            documents: list[ConvertedDocument] = []
            errors: list[str] = []
            total = len(self._file_paths)

            for index, file_path in enumerate(self._file_paths, 1):
                if self._cancelled:
                    self.cancelled.emit()
                    return

                self.file_progress.emit(file_path.name, index, total)

                converted = self._convert_with_retry(file_path)
                if converted is None:
                    continue

                documents.append(
                    ConvertedDocument(result=converted, file_name=file_path.name)
                )

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

    def _convert_with_retry(self, file_path: Path) -> MarkdownResult | None:
        last_error: Exception | None = None

        for _ in range(2):
            if self._cancelled:
                return None

            try:
                converter = DocumentConverter()

                # Create progress callback that emits page progress
                def progress_callback(current_page: int, total_pages: int, message: str):
                    self.page_progress.emit(file_path.name, current_page, total_pages)
                    self.ocr_progress.emit(message)

                return converter.convert(file_path, progress_callback=progress_callback)
            except Exception as exc:
                last_error = exc

        message = f"{file_path.name}: {last_error}" if last_error else f"{file_path.name}: unknown error"
        self.file_error.emit(message)
        return None


class BatchGenerateWorker(QThread):
    """Worker thread for batch card generation with strategy mix support."""

    progress = pyqtSignal(str)
    card_progress = pyqtSignal(int, int)  # current, total
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
        from ankismart.core.config import save_config

        try:
            self._start_time = time.time()

            # Extract configuration
            target_total = self._generation_config.get("target_total", 20)
            strategy_mix = self._generation_config.get("strategy_mix", [])

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

            # Step 3: Generate cards for each document with allocated strategies
            all_cards: list[CardDraft] = []
            total_cards_to_generate = sum(strategy_counts.values())
            cards_generated = 0

            generator = CardGenerator(self._llm_client)

            for doc_idx, document in enumerate(self._documents):
                if self._cancelled:
                    self.cancelled.emit()
                    return

                allocation = per_doc_allocations[doc_idx]
                if not allocation:
                    continue

                self.progress.emit(
                    f"Generating cards for {document.file_name} ({doc_idx + 1}/{len(self._documents)})"
                )

                # Generate cards for each strategy in this document's allocation
                for strategy, count in allocation.items():
                    if self._cancelled:
                        self.cancelled.emit()
                        return

                    if count <= 0:
                        continue

                    self.progress.emit(
                        f"Generating {count} {strategy} cards from {document.file_name}"
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
                        all_cards.extend(cards)
                        cards_generated += len(cards)

                        # Emit progress
                        self.card_progress.emit(cards_generated, total_cards_to_generate)

                    except Exception as e:
                        # Log error but continue with other strategies
                        self.progress.emit(
                            f"Error generating {strategy} cards from {document.file_name}: {str(e)}"
                        )

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
            return

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
