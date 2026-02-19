from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pytest
from PyQt6.QtWidgets import QApplication

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.core.models import (
    BatchConvertResult,
    CardDraft,
    CardPushStatus,
    ConvertedDocument,
    MarkdownResult,
    PushResult,
)
from ankismart.ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _SignalStub:
    def __init__(self) -> None:
        self._callbacks: list[Callable] = []

    def connect(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs) -> None:
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _ClosableStub:
    def close(self) -> None:
        return None


class _InfoBarStub:
    @staticmethod
    def success(*args, **kwargs):
        return _ClosableStub()

    @staticmethod
    def warning(*args, **kwargs):
        return _ClosableStub()

    @staticmethod
    def error(*args, **kwargs):
        return _ClosableStub()

    @staticmethod
    def info(*args, **kwargs):
        return _ClosableStub()


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def patch_infobar(monkeypatch) -> None:
    monkeypatch.setattr("ankismart.ui.import_page.InfoBar", _InfoBarStub)
    monkeypatch.setattr("ankismart.ui.preview_page.InfoBar", _InfoBarStub)
    monkeypatch.setattr("ankismart.ui.card_preview_page.InfoBar", _InfoBarStub)
    monkeypatch.setattr("ankismart.ui.result_page.InfoBar", _InfoBarStub)
    monkeypatch.setattr("ankismart.ui.settings_page.InfoBar", _InfoBarStub)


@pytest.fixture(autouse=True)
def patch_deck_loader_worker(monkeypatch) -> None:
    class _DeckLoaderWorker:
        def __init__(self, anki_url: str, anki_key: str = "") -> None:
            self.finished = _SignalStub()
            self.error = _SignalStub()

        def start(self) -> None:
            self.finished.emit(["Default", "E2EDeck"])

        def isRunning(self) -> bool:
            return False

        def wait(self, timeout: int = 0) -> None:
            return None

        def terminate(self) -> None:
            return None

        def deleteLater(self) -> None:
            return None

    monkeypatch.setattr("ankismart.ui.import_page.DeckLoaderWorker", _DeckLoaderWorker)


@pytest.fixture
def e2e_config() -> AppConfig:
    provider_openai = LLMProviderConfig(
        id="p-openai",
        name="OpenAI",
        api_key="e2e-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        rpm_limit=60,
    )
    provider_ollama = LLMProviderConfig(
        id="p-ollama",
        name="Ollama (本地)",
        api_key="",
        base_url="http://localhost:11434/v1",
        model="llama3.1",
        rpm_limit=0,
    )
    return AppConfig(
        llm_providers=[provider_openai, provider_ollama],
        active_provider_id=provider_openai.id,
        default_deck="Default",
        default_tags=["ankismart", "e2e"],
        language="zh",
        theme="light",
        anki_connect_url="http://127.0.0.1:8765",
    )


@pytest.fixture
def e2e_files(tmp_path: Path) -> dict[str, Path]:
    fixture_md = Path(__file__).parent / "fixtures" / "files" / "text" / "sample.md"
    md_path = tmp_path / "sample.md"
    md_path.write_text(fixture_md.read_text(encoding="utf-8"), encoding="utf-8")

    docx_pkg = pytest.importorskip("docx")
    docx_path = tmp_path / "sample.docx"
    doc = docx_pkg.Document()
    doc.add_heading("E2E DOCX 文档", 1)
    doc.add_paragraph("这是用于端到端测试的 DOCX 输入。")
    doc.save(docx_path)

    pdf_path = tmp_path / "image_based.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )

    return {"md": md_path, "docx": docx_path, "pdf": pdf_path}


@pytest.fixture
def window(monkeypatch, qapp: QApplication, e2e_config: AppConfig):
    monkeypatch.setattr("ankismart.ui.import_page.save_config", lambda _cfg: None)
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)
    monkeypatch.setattr("ankismart.ui.settings_page.save_config", lambda _cfg: None)

    app_window = MainWindow(e2e_config.model_copy(deep=True))
    app_window.show()
    qapp.processEvents()
    yield app_window
    app_window.close()
    qapp.processEvents()


def _resolve_source_format(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".md":
        return "markdown"
    if suffix == ".txt":
        return "text"
    if suffix == ".docx":
        return "docx"
    if suffix == ".pptx":
        return "pptx"
    if suffix == ".pdf":
        return "pdf"
    return "markdown"


@pytest.fixture
def patch_batch_convert_worker(monkeypatch):
    def _patch(*, fail_files: set[str] | None = None):
        failing = fail_files or set()

        class _BatchConvertWorker:
            def __init__(self, file_paths: list[Path], config=None) -> None:
                self._file_paths = list(file_paths)
                self._cancelled = False
                self.file_progress = _SignalStub()
                self.page_progress = _SignalStub()
                self.file_completed = _SignalStub()
                self.finished = _SignalStub()
                self.error = _SignalStub()
                self.cancelled = _SignalStub()

            def start(self) -> None:
                total = len(self._file_paths)
                docs: list[ConvertedDocument] = []
                errors: list[str] = []
                for index, file_path in enumerate(self._file_paths, 1):
                    if self._cancelled:
                        self.cancelled.emit()
                        return

                    self.file_progress.emit(file_path.name, index, total)
                    if file_path.name in failing:
                        errors.append(f"{file_path.name}: conversion failed")
                        continue

                    source_format = _resolve_source_format(file_path)
                    if source_format in {"markdown", "text"} and file_path.exists():
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                    elif source_format == "docx":
                        content = f"# DOCX Converted\n\n{file_path.stem} converted"
                    elif source_format == "pdf":
                        content = f"# OCR Converted\n\n{file_path.stem} OCR text"
                        self.page_progress.emit(file_path.name, 1, 1)
                    else:
                        content = f"# Converted\n\n{file_path.stem}"

                    doc = ConvertedDocument(
                        result=MarkdownResult(
                            content=content,
                            source_path=str(file_path),
                            source_format=source_format,
                            trace_id=f"e2e-convert-{index}",
                        ),
                        file_name=file_path.name,
                    )
                    docs.append(doc)
                    self.file_completed.emit(file_path.name, doc)

                self.finished.emit(BatchConvertResult(documents=docs, errors=errors))

            def cancel(self) -> None:
                self._cancelled = True

            def isRunning(self) -> bool:
                return False

            def deleteLater(self) -> None:
                return None

        monkeypatch.setattr("ankismart.ui.import_page.BatchConvertWorker", _BatchConvertWorker)
        return _BatchConvertWorker

    return _patch


@pytest.fixture
def patch_batch_generate_worker(monkeypatch):
    def _patch(*, cards_per_document: int = 2):
        class _BatchGenerateWorker:
            def __init__(
                self,
                documents: list[ConvertedDocument],
                generation_config: dict,
                llm_client,
                deck_name: str,
                tags: list[str],
                enable_auto_split: bool = False,
                split_threshold: int = 70000,
                config=None,
            ) -> None:
                self._documents = list(documents)
                self._generation_config = generation_config
                self._deck_name = deck_name
                self._tags = tags
                self.progress = _SignalStub()
                self.card_progress = _SignalStub()
                self.document_completed = _SignalStub()
                self.finished = _SignalStub()
                self.error = _SignalStub()
                self.cancelled = _SignalStub()

            def start(self) -> None:
                strategy_mix = self._generation_config.get("strategy_mix", [])
                if not self._documents or not strategy_mix:
                    self.error.emit("no documents or no strategy")
                    return

                cards: list[CardDraft] = []
                total = len(self._documents) * cards_per_document
                progress_index = 0
                for doc_index, document in enumerate(self._documents):
                    self.progress.emit(f"generating {document.file_name}")
                    for item_index in range(cards_per_document):
                        strategy = strategy_mix[(doc_index + item_index) % len(strategy_mix)]["strategy"]
                        note_type = "Cloze" if strategy == "cloze" else "Basic"
                        if note_type == "Cloze":
                            fields = {
                                "Text": f"{document.file_name} {{c1::重点}} 内容",
                                "Extra": f"{strategy} extra",
                            }
                        else:
                            fields = {
                                "Front": f"{document.file_name} - {strategy} - Q{item_index + 1}",
                                "Back": f"{document.file_name} - {strategy} - A{item_index + 1}",
                            }
                        cards.append(
                            CardDraft(
                                trace_id=document.result.trace_id,
                                deck_name=self._deck_name,
                                note_type=note_type,
                                fields=fields,
                                tags=list(self._tags),
                            )
                        )
                        progress_index += 1
                        self.card_progress.emit(progress_index, total)
                    self.document_completed.emit(document.file_name, cards_per_document)

                self.finished.emit(cards)

            def cancel(self) -> None:
                self.cancelled.emit()

            def isRunning(self) -> bool:
                return False

            def deleteLater(self) -> None:
                return None

        monkeypatch.setattr("ankismart.ui.preview_page.BatchGenerateWorker", _BatchGenerateWorker)
        return _BatchGenerateWorker

    return _patch


@pytest.fixture
def patch_push_worker(monkeypatch):
    def _patch(*, fail: bool = False, error_message: str = "AnkiConnect unavailable"):
        class _PushWorker:
            def __init__(self, gateway, cards: list[CardDraft], update_mode: str = "create_only") -> None:
                self._cards = list(cards)
                self.progress = _SignalStub()
                self.finished = _SignalStub()
                self.error = _SignalStub()
                self.cancelled = _SignalStub()

            def start(self) -> None:
                self.progress.emit("pushing cards")
                statuses: list[CardPushStatus] = []
                if fail:
                    for index in range(len(self._cards)):
                        statuses.append(CardPushStatus(index=index, success=False, error=error_message))
                    result = PushResult(
                        total=len(self._cards),
                        succeeded=0,
                        failed=len(self._cards),
                        results=statuses,
                        trace_id="e2e-push-failed",
                    )
                else:
                    for index in range(len(self._cards)):
                        statuses.append(CardPushStatus(index=index, success=True, note_id=10000 + index))
                    result = PushResult(
                        total=len(self._cards),
                        succeeded=len(self._cards),
                        failed=0,
                        results=statuses,
                        trace_id="e2e-push-ok",
                    )
                self.finished.emit(result)

            def cancel(self) -> None:
                self.cancelled.emit()

            def isRunning(self) -> bool:
                return False

            def deleteLater(self) -> None:
                return None

        monkeypatch.setattr("ankismart.ui.workers.PushWorker", _PushWorker)
        monkeypatch.setattr("ankismart.ui.preview_page.PushWorker", _PushWorker)
        return _PushWorker

    return _patch
