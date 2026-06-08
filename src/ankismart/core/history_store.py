from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ankismart.core.config import HISTORY_DB_PATH
from ankismart.core.models import CardDraft

_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GenerationBatchSummary:
    batch_id: str
    created_at: str
    title: str
    status: str
    card_count: int
    target_total: int = 0
    low_quality_count: int = 0
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationBatch:
    summary: GenerationBatchSummary
    cards: list[CardDraft]


class SQLiteHistoryStore:
    """SQLite-backed generated-card history storage."""

    def __init__(self, path: Path | str = HISTORY_DB_PATH) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS generation_batches (
                    batch_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    card_count INTEGER NOT NULL,
                    target_total INTEGER NOT NULL DEFAULT 0,
                    low_quality_count INTEGER NOT NULL DEFAULT 0,
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS generated_cards (
                    batch_id TEXT NOT NULL,
                    card_index INTEGER NOT NULL,
                    card_json TEXT NOT NULL,
                    front_text TEXT NOT NULL DEFAULT '',
                    back_text TEXT NOT NULL DEFAULT '',
                    deck_name TEXT NOT NULL DEFAULT '',
                    note_type TEXT NOT NULL DEFAULT '',
                    source_document TEXT NOT NULL DEFAULT '',
                    strategy_id TEXT NOT NULL DEFAULT '',
                    trace_id TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (batch_id, card_index),
                    FOREIGN KEY (batch_id)
                        REFERENCES generation_batches(batch_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_generation_batches_created_at
                    ON generation_batches(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_generated_cards_source_document
                    ON generated_cards(source_document);
                CREATE INDEX IF NOT EXISTS idx_generated_cards_strategy_id
                    ON generated_cards(strategy_id);
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO app_meta(key, value) VALUES ('schema_version', ?)",
                (str(_SCHEMA_VERSION),),
            )

    def save_generation_batch(
        self,
        cards: list[CardDraft],
        *,
        batch_id: str | None = None,
        title: str = "",
        status: str = "success",
        target_total: int = 0,
        low_quality_count: int = 0,
        duration_seconds: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationBatchSummary:
        self.initialize()
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        resolved_batch_id = batch_id or uuid.uuid4().hex
        resolved_title = title.strip() or f"生成 {len(cards)} 张卡片"
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, default=str)

        with self._connect() as conn:
            conn.execute("DELETE FROM generation_batches WHERE batch_id = ?", (resolved_batch_id,))
            conn.execute(
                """
                INSERT INTO generation_batches(
                    batch_id,
                    created_at,
                    title,
                    status,
                    card_count,
                    target_total,
                    low_quality_count,
                    duration_seconds,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_batch_id,
                    now,
                    resolved_title,
                    status,
                    len(cards),
                    int(target_total or 0),
                    int(low_quality_count or 0),
                    float(duration_seconds or 0.0),
                    metadata_json,
                ),
            )
            conn.executemany(
                """
                INSERT INTO generated_cards(
                    batch_id,
                    card_index,
                    card_json,
                    front_text,
                    back_text,
                    deck_name,
                    note_type,
                    source_document,
                    strategy_id,
                    trace_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    self._card_row_values(resolved_batch_id, index, card)
                    for index, card in enumerate(cards)
                ],
            )

        return GenerationBatchSummary(
            batch_id=resolved_batch_id,
            created_at=now,
            title=resolved_title,
            status=status,
            card_count=len(cards),
            target_total=int(target_total or 0),
            low_quality_count=int(low_quality_count or 0),
            duration_seconds=float(duration_seconds or 0.0),
            metadata=dict(metadata or {}),
        )

    def list_generation_batches(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[GenerationBatchSummary]:
        self.initialize()
        safe_limit = max(1, int(limit))
        safe_offset = max(0, int(offset))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM generation_batches
                ORDER BY created_at DESC, batch_id DESC
                LIMIT ? OFFSET ?
                """,
                (safe_limit, safe_offset),
            ).fetchall()
        return [self._summary_from_row(row) for row in rows]

    def get_generation_batch(self, batch_id: str) -> GenerationBatch | None:
        self.initialize()
        with self._connect() as conn:
            summary_row = conn.execute(
                "SELECT * FROM generation_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
            if summary_row is None:
                return None
            card_rows = conn.execute(
                """
                SELECT card_json
                FROM generated_cards
                WHERE batch_id = ?
                ORDER BY card_index ASC
                """,
                (batch_id,),
            ).fetchall()

        cards = [CardDraft.model_validate(json.loads(row["card_json"])) for row in card_rows]
        return GenerationBatch(summary=self._summary_from_row(summary_row), cards=cards)

    def load_generation_cards(self, batch_id: str) -> list[CardDraft]:
        batch = self.get_generation_batch(batch_id)
        return list(batch.cards) if batch is not None else []

    def delete_generation_batch(self, batch_id: str) -> bool:
        self.initialize()
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM generation_batches WHERE batch_id = ?", (batch_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _card_row_values(batch_id: str, index: int, card: CardDraft) -> tuple:
        fields = card.fields or {}
        metadata = card.metadata
        return (
            batch_id,
            index,
            card.model_dump_json(),
            str(fields.get("Front", "") or fields.get("Question", "") or fields.get("Text", "")),
            str(fields.get("Back", "") or fields.get("Answer", "") or fields.get("Extra", "")),
            card.deck_name,
            card.note_type,
            str(getattr(metadata, "source_document", "") or ""),
            str(getattr(metadata, "strategy_id", "") or ""),
            card.trace_id,
        )

    @staticmethod
    def _summary_from_row(row: sqlite3.Row) -> GenerationBatchSummary:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        return GenerationBatchSummary(
            batch_id=str(row["batch_id"]),
            created_at=str(row["created_at"]),
            title=str(row["title"]),
            status=str(row["status"]),
            card_count=int(row["card_count"]),
            target_total=int(row["target_total"]),
            low_quality_count=int(row["low_quality_count"]),
            duration_seconds=float(row["duration_seconds"]),
            metadata=metadata if isinstance(metadata, dict) else {},
        )


def get_default_history_store() -> SQLiteHistoryStore:
    return SQLiteHistoryStore(HISTORY_DB_PATH)
