from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ankismart.anki_gateway.apkg_exporter import ApkgExporter
from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.gateway import AnkiGateway
from ankismart.card_gen.generator import CardGenerator
from ankismart.card_gen.llm_client import LLMClient
from ankismart.converter.converter import DocumentConverter
from ankismart.core.models import (
    BatchConvertResult,
    CardDraft,
    ConvertedDocument,
    GenerateRequest,
    MarkdownResult,
    PushResult,
)


class ConvertWorker(QThread):
    finished = Signal(MarkdownResult)
    error = Signal(str)

    def __init__(self, file_path: Path) -> None:
        super().__init__()
        self._file_path = file_path

    def run(self) -> None:
        try:
            converter = DocumentConverter()
            result = converter.convert(self._file_path)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class GenerateWorker(QThread):
    finished = Signal(list)  # list[CardDraft]
    error = Signal(str)

    def __init__(self, request: GenerateRequest, api_key: str, model: str) -> None:
        super().__init__()
        self._request = request
        self._api_key = api_key
        self._model = model

    def run(self) -> None:
        try:
            llm_client = LLMClient(api_key=self._api_key, model=self._model)
            generator = CardGenerator(llm_client)
            cards = generator.generate(self._request)
            self.finished.emit(cards)
        except Exception as exc:
            self.error.emit(str(exc))


class PushWorker(QThread):
    finished = Signal(PushResult)
    error = Signal(str)

    def __init__(self, cards: list[CardDraft], url: str, key: str) -> None:
        super().__init__()
        self._cards = cards
        self._url = url
        self._key = key

    def run(self) -> None:
        try:
            client = AnkiConnectClient(url=self._url, key=self._key)
            gateway = AnkiGateway(client)
            result = gateway.push(self._cards)
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

    def __init__(self, url: str, key: str) -> None:
        super().__init__()
        self._url = url
        self._key = key

    def run(self) -> None:
        client = AnkiConnectClient(url=self._url, key=self._key)
        self.finished.emit(client.check_connection())


class DeckListWorker(QThread):
    finished = Signal(list)  # list[str]
    error = Signal(str)

    def __init__(self, url: str, key: str) -> None:
        super().__init__()
        self._url = url
        self._key = key

    def run(self) -> None:
        try:
            client = AnkiConnectClient(url=self._url, key=self._key)
            decks = client.get_deck_names()
            self.finished.emit(decks)
        except Exception as exc:
            self.error.emit(str(exc))


class BatchConvertWorker(QThread):
    finished = Signal(BatchConvertResult)
    file_progress = Signal(int, int, str)  # current, total, filename
    error = Signal(str)

    def __init__(self, file_paths: list[Path]) -> None:
        super().__init__()
        self._file_paths = file_paths

    def run(self) -> None:
        try:
            converter = DocumentConverter()
            documents: list[ConvertedDocument] = []
            errors: list[str] = []
            total = len(self._file_paths)

            for i, path in enumerate(self._file_paths):
                self.file_progress.emit(i + 1, total, path.name)
                try:
                    result = converter.convert(path)
                    documents.append(
                        ConvertedDocument(
                            result=result, file_name=path.name
                        )
                    )
                except Exception as exc:
                    errors.append(f"{path.name}: {exc}")

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
        api_key: str,
        model: str,
    ) -> None:
        super().__init__()
        self._documents = documents
        self._config = requests_config  # strategy, deck_name, tags
        self._api_key = api_key
        self._model = model

    def run(self) -> None:
        try:
            llm_client = LLMClient(
                api_key=self._api_key, model=self._model
            )
            generator = CardGenerator(llm_client)
            all_cards: list[CardDraft] = []
            total = len(self._documents)

            for i, doc in enumerate(self._documents):
                self.file_progress.emit(
                    i + 1, total, doc.file_name
                )
                request = GenerateRequest(
                    markdown=doc.result.content,
                    strategy=self._config.get("strategy", "basic"),
                    deck_name=self._config.get("deck_name", "Default"),
                    tags=self._config.get("tags", ["ankismart"]),
                    trace_id=doc.result.trace_id,
                    source_path=doc.result.source_path,
                )
                cards = generator.generate(request)
                all_cards.extend(cards)

            self.finished.emit(all_cards)
        except Exception as exc:
            self.error.emit(str(exc))
