from __future__ import annotations

import concurrent.futures
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ankismart.anki_gateway.apkg_exporter import ApkgExporter
from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.gateway import AnkiGateway
from ankismart.card_gen.generator import CardGenerator
from ankismart.card_gen.llm_client import LLMClient
from ankismart.card_gen.prompts import OCR_CORRECTION_PROMPT
from ankismart.converter.converter import DocumentConverter
from ankismart.core.models import (
    BatchConvertResult,
    CardDraft,
    ConvertedDocument,
    GenerateRequest,
    MarkdownResult,
    PushResult,
)


def _build_ocr_correction_fn(config) -> object:
    """Build an OCR correction callable from config, or return None."""
    if not getattr(config, "ocr_correction", False):
        return None
    llm = LLMClient.from_config(config)
    return lambda text: llm.chat(OCR_CORRECTION_PROMPT, text)


class ConvertWorker(QThread):
    finished = Signal(MarkdownResult)
    error = Signal(str)

    def __init__(self, file_path: Path, config=None) -> None:
        super().__init__()
        self._file_path = file_path
        self._config = config

    def run(self) -> None:
        try:
            ocr_fn = _build_ocr_correction_fn(self._config)
            converter = DocumentConverter(ocr_correction_fn=ocr_fn)
            result = converter.convert(self._file_path)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class GenerateWorker(QThread):
    finished = Signal(list)  # list[CardDraft]
    error = Signal(str)

    def __init__(self, request: GenerateRequest, config) -> None:
        super().__init__()
        self._request = request
        self._config = config

    def run(self) -> None:
        try:
            llm_client = LLMClient.from_config(self._config)
            generator = CardGenerator(llm_client)
            cards = generator.generate(self._request)
            self.finished.emit(cards)
        except Exception as exc:
            self.error.emit(str(exc))


class PushWorker(QThread):
    finished = Signal(PushResult)
    error = Signal(str)

    def __init__(
        self,
        cards: list[CardDraft],
        url: str,
        key: str,
        *,
        update_mode: str = "create_only",
        proxy_url: str = "",
    ) -> None:
        super().__init__()
        self._cards = cards
        self._url = url
        self._key = key
        self._update_mode = update_mode
        self._proxy_url = proxy_url

    def run(self) -> None:
        try:
            client = AnkiConnectClient(url=self._url, key=self._key, proxy_url=self._proxy_url)
            gateway = AnkiGateway(client)
            result = gateway.push(self._cards, update_mode=self._update_mode)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class ExportWorker(QThread):
    finished = Signal(Path)
    error = Signal(str)

    def __init__(self, cards: list[CardDraft], output_path: Path) -> None:
        super().__init__()
        self._cards = cards
        self._output_path = output_path

    def run(self) -> None:
        try:
            exporter = ApkgExporter()
            result = exporter.export(self._cards, self._output_path)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class ConnectionCheckWorker(QThread):
    finished = Signal(bool)

    def __init__(self, url: str, key: str, proxy_url: str = "") -> None:
        super().__init__()
        self._url = url
        self._key = key
        self._proxy_url = proxy_url

    def run(self) -> None:
        client = AnkiConnectClient(url=self._url, key=self._key, proxy_url=self._proxy_url)
        self.finished.emit(client.check_connection())


class DeckListWorker(QThread):
    finished = Signal(list)  # list[str]
    error = Signal(str)

    def __init__(self, url: str, key: str, proxy_url: str = "") -> None:
        super().__init__()
        self._url = url
        self._key = key
        self._proxy_url = proxy_url

    def run(self) -> None:
        try:
            client = AnkiConnectClient(url=self._url, key=self._key, proxy_url=self._proxy_url)
            decks = client.get_deck_names()
            self.finished.emit(decks)
        except Exception as exc:
            self.error.emit(str(exc))


_IO_EXTENSIONS = {".md", ".txt", ".docx", ".pptx"}


class BatchConvertWorker(QThread):
    finished = Signal(BatchConvertResult)
    file_progress = Signal(int, int, str)  # current, total, filename
    file_error = Signal(str)  # per-file error message
    ocr_progress = Signal(str)
    error = Signal(str)

    _MAX_RETRIES = 1

    def __init__(self, file_paths: list[Path], config=None) -> None:
        super().__init__()
        self._file_paths = file_paths
        self._config = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _convert_with_retry(
        self, converter, path: Path, *, progress_callback=None
    ) -> ConvertedDocument:
        """Try converting a file, retrying once on failure."""
        last_exc: Exception | None = None
        for _attempt in range(1 + self._MAX_RETRIES):
            try:
                result = converter.convert(path, progress_callback=progress_callback)
                return ConvertedDocument(result=result, file_name=path.name)
            except Exception as exc:
                last_exc = exc
        raise last_exc  # type: ignore[misc]

    def run(self) -> None:
        try:
            ocr_fn = _build_ocr_correction_fn(self._config)
            converter = DocumentConverter(ocr_correction_fn=ocr_fn)
            documents: list[ConvertedDocument] = []
            errors: list[str] = []
            total = len(self._file_paths)

            # Split files by type
            io_files: list[tuple[int, Path]] = []
            cpu_files: list[tuple[int, Path]] = []
            for idx, path in enumerate(self._file_paths):
                if path.suffix.lower() in _IO_EXTENSIONS:
                    io_files.append((idx, path))
                else:
                    cpu_files.append((idx, path))

            completed = 0
            results_by_idx: dict[int, ConvertedDocument | str] = {}

            # I/O-bound files: parallel with ThreadPoolExecutor
            if io_files and not self._cancelled:
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    future_map = {
                        pool.submit(self._convert_with_retry, converter, path): (idx, path)
                        for idx, path in io_files
                    }
                    for future in concurrent.futures.as_completed(future_map):
                        if self._cancelled:
                            for f in future_map:
                                f.cancel()
                            break
                        idx, path = future_map[future]
                        completed += 1
                        self.file_progress.emit(completed, total, path.name)
                        try:
                            results_by_idx[idx] = future.result()
                        except Exception as exc:
                            err_msg = f"{path.name}: {exc}"
                            results_by_idx[idx] = err_msg
                            self.file_error.emit(err_msg)

            # CPU-bound files: sequential (OCR saturates CPU)
            for idx, path in cpu_files:
                if self._cancelled:
                    break
                completed += 1
                self.file_progress.emit(completed, total, path.name)
                try:
                    results_by_idx[idx] = self._convert_with_retry(
                        converter, path, progress_callback=self.ocr_progress.emit
                    )
                except Exception as exc:
                    err_msg = f"{path.name}: {exc}"
                    results_by_idx[idx] = err_msg
                    self.file_error.emit(err_msg)

            # Collect results in original order
            for idx in sorted(results_by_idx):
                item = results_by_idx[idx]
                if isinstance(item, ConvertedDocument):
                    documents.append(item)
                else:
                    errors.append(item)

            self.finished.emit(
                BatchConvertResult(documents=documents, errors=errors)
            )
        except Exception as exc:
            self.error.emit(str(exc))


class BatchGenerateWorker(QThread):
    finished = Signal(list)  # list[CardDraft]
    file_progress = Signal(int, int, str)  # current, total, filename
    error = Signal(str)

    def __init__(
        self,
        documents: list[ConvertedDocument],
        requests_config: dict,
        config,
    ) -> None:
        super().__init__()
        self._documents = documents
        self._requests_config = requests_config
        self._config = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @staticmethod
    def _allocate_mix_counts(target_total: int, ratio_items: list[dict]) -> dict[str, int]:
        if target_total <= 0 or not ratio_items:
            return {}

        valid_items: list[tuple[str, int]] = []
        for item in ratio_items:
            strategy = str(item.get("strategy", "")).strip()
            try:
                ratio = int(item.get("ratio", 0) or 0)
            except (TypeError, ValueError):
                ratio = 0
            if strategy and ratio > 0:
                valid_items.append((strategy, ratio))

        if not valid_items:
            return {}

        total_ratio = sum(r for _, r in valid_items)
        if total_ratio <= 0:
            return {}

        base: dict[str, int] = {}
        remainders: list[tuple[str, float]] = []
        assigned = 0

        for strategy, ratio in valid_items:
            exact = target_total * ratio / total_ratio
            count = int(exact)
            base[strategy] = count
            assigned += count
            remainders.append((strategy, exact - count))

        remaining = target_total - assigned
        remainders.sort(key=lambda item: item[1], reverse=True)
        for i in range(remaining):
            strategy = remainders[i % len(remainders)][0]
            base[strategy] = base.get(strategy, 0) + 1

        return base

    @staticmethod
    def _distribute_counts_per_document(
        total_docs: int, strategy_counts: dict[str, int]
    ) -> list[dict[str, int]]:
        if total_docs <= 0:
            return []

        per_doc: list[dict[str, int]] = [dict() for _ in range(total_docs)]
        for strategy, total_count in strategy_counts.items():
            if total_count <= 0:
                continue
            base = total_count // total_docs
            remainder = total_count % total_docs
            for doc_idx in range(total_docs):
                count = base + (1 if doc_idx < remainder else 0)
                if count > 0:
                    per_doc[doc_idx][strategy] = count

        return per_doc

    def run(self) -> None:
        try:
            llm_client = LLMClient.from_config(self._config)
            generator = CardGenerator(llm_client)
            all_cards: list[CardDraft] = []
            total = len(self._documents)
            mode = self._requests_config.get("mode", "single")
            target_total = int(self._requests_config.get("target_total", 0) or 0)
            ratio_items = self._requests_config.get("strategy_mix", [])

            mix_counts: dict[str, int] = {}
            per_doc_mix: list[dict[str, int]] = []
            if mode == "mixed":
                mix_counts = self._allocate_mix_counts(target_total, ratio_items)
                if not mix_counts:
                    mix_counts = {"basic": max(1, target_total or total)}
                per_doc_mix = self._distribute_counts_per_document(total, mix_counts)

            for i, doc in enumerate(self._documents):
                if self._cancelled:
                    break
                self.file_progress.emit(
                    i + 1, total, doc.file_name
                )

                if mode != "mixed":
                    request = GenerateRequest(
                        markdown=doc.result.content,
                        strategy=self._requests_config.get("strategy", "basic"),
                        deck_name=self._requests_config.get("deck_name", "Default"),
                        tags=self._requests_config.get("tags", ["ankismart"]),
                        trace_id=doc.result.trace_id,
                        source_path=doc.result.source_path,
                    )
                    cards = generator.generate(request)
                    all_cards.extend(cards)
                    continue

                active_counts = per_doc_mix[i] if i < len(per_doc_mix) else {}
                if not active_counts:
                    continue

                for strategy, count in active_counts.items():
                    request = GenerateRequest(
                        markdown=doc.result.content,
                        strategy=strategy,
                        deck_name=self._requests_config.get("deck_name", "Default"),
                        tags=self._requests_config.get("tags", ["ankismart"]),
                        trace_id=doc.result.trace_id,
                        source_path=doc.result.source_path,
                        target_count=count,
                    )
                    cards = generator.generate(request)
                    all_cards.extend(cards)

            self.finished.emit(all_cards)
        except Exception as exc:
            self.error.emit(str(exc))
