from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ankismart.core.models import CardDraft, CardPushStatus, GenerateRequest, MarkdownResult, PushResult


class IConverter(Protocol):
    """Convert a document file to Markdown."""

    def convert(self, file_path: Path) -> MarkdownResult: ...


class ICardGenerator(Protocol):
    """Generate Anki card drafts from Markdown content."""

    def generate(self, request: GenerateRequest) -> list[CardDraft]: ...


class IAnkiGateway(Protocol):
    """Communicate with Anki via AnkiConnect."""

    def check_connection(self) -> bool: ...

    def get_deck_names(self) -> list[str]: ...

    def get_model_names(self) -> list[str]: ...

    def get_model_field_names(self, model_name: str) -> list[str]: ...

    def find_notes(self, query: str) -> list[int]: ...

    def update_note(self, note_id: int, fields: dict[str, str]) -> None: ...

    def create_or_update_note(self, card: CardDraft) -> CardPushStatus: ...

    def push(self, cards: list[CardDraft], update_mode: str = "create_only") -> PushResult: ...


class IApkgExporter(Protocol):
    """Export card drafts to an .apkg file."""

    def export(self, cards: list[CardDraft], output_path: Path) -> Path: ...
