from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ankismart.anki_gateway.apkg_exporter import ApkgExporter
from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.gateway import AnkiGateway, UpdateMode
from ankismart.card_gen.generator import CardGenerator
from ankismart.card_gen.llm_client import LLMClient
from ankismart.converter.converter import DocumentConverter
from ankismart.core.config import LLMProviderConfig
from ankismart.core.models import CardDraft, GenerateRequest, MarkdownResult


class ConvertWorker(QThread):
    """Worker thread for file conversion."""

    progress = Signal(str)  # Progress message
    finished = Signal(object)  # MarkdownResult
    error = Signal(str)  # Error message

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

    progress = Signal(str)  # Progress message
    finished = Signal(list)  # list[CardDraft]
    error = Signal(str)  # Error message

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

    progress = Signal(str)  # Progress message
    finished = Signal(object)  # PushResult
    error = Signal(str)  # Error message

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

    def run(self) -> None:
        try:
            self.progress.emit(f"正在推送 {len(self._cards)} 张卡片到 Anki")
            result = self._gateway.push(self._cards, update_mode=self._update_mode)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ExportWorker(QThread):
    """Worker thread for exporting cards to APKG."""

    progress = Signal(str)  # Progress message
    finished = Signal(str)  # Output path
    error = Signal(str)  # Error message

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

    finished = Signal(bool)

    def __init__(self, url: str, key: str, proxy_url: str = "") -> None:
        super().__init__()
        self._url = url
        self._key = key
        self._proxy_url = proxy_url

    def run(self) -> None:
        try:
            client = AnkiConnectClient(url=self._url, key=self._key, proxy_url=self._proxy_url)
            self.finished.emit(client.check_connection())
        except Exception:
            self.finished.emit(False)


class ProviderConnectionWorker(QThread):
    """Worker thread for checking LLM provider connectivity."""

    finished = Signal(bool, str)

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
