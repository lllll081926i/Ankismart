from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ankismart.core import config as config_module
from ankismart.core.models import CardDraft

_SCHEMA_VERSION = 1


def resolve_history_db_path() -> Path:
    """Resolve generated-card history cache under the application install directory."""
    env_path = os.getenv("ANKISMART_HISTORY_DB_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    return (config_module._resolve_project_root() / "cache" / "history.sqlite3").resolve()


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


@dataclass(frozen=True)
class HistoryCachePruneResult:
    deleted_batches: int
    deleted_cards: int
    deleted_batch_ids: list[str] = field(default_factory=list)


class SQLiteHistoryStore:
    """SQLite-backed generated-card history storage."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else resolve_history_db_path()

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
        now = datetime.now().astimezone().isoformat(timespec="microseconds")
        resolved_batch_id = batch_id or uuid.uuid4().hex
        resolved_title = title.strip() or f"生成 {len(cards)} 张卡片"
        resolved_metadata = self._enrich_metadata(cards, metadata)
        metadata_json = json.dumps(resolved_metadata, ensure_ascii=False, default=str)

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
            metadata=resolved_metadata,
        )

    def list_generation_batches(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[GenerationBatchSummary]:
        if not self.path.exists():
            return []
        self.initialize()
        safe_limit = max(1, int(limit))
        safe_offset = max(0, int(offset))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM generation_batches
                ORDER BY created_at DESC, rowid DESC
                LIMIT ? OFFSET ?
                """,
                (safe_limit, safe_offset),
            ).fetchall()
        return [self._summary_from_row(row) for row in rows]

    def get_generation_batch(self, batch_id: str) -> GenerationBatch | None:
        if not self.path.exists():
            return None
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
        if not self.path.exists():
            return False
        self.initialize()
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM generation_batches WHERE batch_id = ?", (batch_id,))
        return cursor.rowcount > 0

    def delete_generation_batches(self, batch_ids: list[str]) -> int:
        if not self.path.exists():
            return 0
        self.initialize()
        normalized_ids = [str(batch_id).strip() for batch_id in batch_ids if str(batch_id).strip()]
        if not normalized_ids:
            return 0
        with self._connect() as conn:
            cursor = conn.executemany(
                "DELETE FROM generation_batches WHERE batch_id = ?",
                [(batch_id,) for batch_id in normalized_ids],
            )
            return cursor.rowcount if cursor.rowcount >= 0 else 0

    def clear_generation_history(self) -> int:
        if not self.path.exists():
            return 0
        self.initialize()
        with self._connect() as conn:
            count_row = conn.execute(
                "SELECT COUNT(*) AS batch_count FROM generation_batches"
            ).fetchone()
            deleted = int(count_row["batch_count"] if count_row is not None else 0)
            conn.execute("DELETE FROM generation_batches")
        if deleted:
            self._vacuum()
        return deleted

    def get_cache_stats(self) -> dict[str, float | int | str]:
        if not self.path.exists():
            return {
                "path": str(self.path),
                "size_bytes": 0,
                "size_mb": 0.0,
                "batch_count": 0,
                "card_count": 0,
            }
        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS batch_count,
                    COALESCE(SUM(card_count), 0) AS card_count
                FROM generation_batches
                """
            ).fetchone()

        size_bytes = self._database_size_bytes()
        return {
            "path": str(self.path),
            "size_bytes": size_bytes,
            "size_mb": size_bytes / (1024 * 1024),
            "batch_count": int(row["batch_count"] if row is not None else 0),
            "card_count": int(row["card_count"] if row is not None else 0),
        }

    def prune_cache(self, *, max_size_mb: int | float, max_records: int) -> HistoryCachePruneResult:
        """Delete oldest batches until both cache limits are satisfied."""
        if not self.path.exists():
            return HistoryCachePruneResult(deleted_batches=0, deleted_cards=0)
        self.initialize()
        max_bytes = max(0, int(float(max_size_mb) * 1024 * 1024))
        max_count = max(0, int(max_records))
        deleted_batch_ids: list[str] = []
        deleted_cards = 0

        while True:
            stats = self.get_cache_stats()
            batch_count = int(stats["batch_count"])
            size_bytes = int(stats["size_bytes"])
            count_exceeded = batch_count > max_count
            size_exceeded = size_bytes > max_bytes
            if not count_exceeded and not size_exceeded:
                break
            if batch_count <= 0:
                break

            oldest = self._oldest_batch()
            if oldest is None:
                break
            batch_id, card_count = oldest
            if not self.delete_generation_batch(batch_id):
                break
            deleted_batch_ids.append(batch_id)
            deleted_cards += card_count
            self._vacuum()

        return HistoryCachePruneResult(
            deleted_batches=len(deleted_batch_ids),
            deleted_cards=deleted_cards,
            deleted_batch_ids=deleted_batch_ids,
        )

    def _oldest_batch(self) -> tuple[str, int] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT batch_id, card_count
                FROM generation_batches
                ORDER BY created_at ASC, rowid ASC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return str(row["batch_id"]), int(row["card_count"])

    def _database_size_bytes(self) -> int:
        total = 0
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{self.path}{suffix}")
            try:
                if path.exists():
                    total += path.stat().st_size
            except OSError:
                continue
        return total

    def _vacuum(self) -> None:
        with self._connect() as conn:
            conn.execute("VACUUM")

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
    def _enrich_metadata(cards: list[CardDraft], metadata: dict[str, Any] | None) -> dict[str, Any]:
        enriched = dict(metadata or {})
        source_documents = sorted(
            {
                str(getattr(card.metadata, "source_document", "") or "").strip()
                for card in cards
                if str(getattr(card.metadata, "source_document", "") or "").strip()
            }
        )
        strategy_ids = sorted(
            {
                str(getattr(card.metadata, "strategy_id", "") or "").strip()
                for card in cards
                if str(getattr(card.metadata, "strategy_id", "") or "").strip()
            }
        )
        if source_documents and not enriched.get("source_documents"):
            enriched["source_documents"] = source_documents
        if strategy_ids and not enriched.get("strategy_ids"):
            enriched["strategy_ids"] = strategy_ids
        return enriched

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
    return SQLiteHistoryStore(resolve_history_db_path())
