from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from ankismart.core.history_store import SQLiteHistoryStore, resolve_history_db_path
from ankismart.core.models import CardDraft, CardMetadata


def _card(index: int, *, source_document: str = "lesson.md") -> CardDraft:
    return CardDraft(
        trace_id=f"trace-{index}",
        deck_name="Default",
        note_type="Basic",
        fields={
            "Front": f"Question {index}",
            "Back": f"答案: Answer {index}\n解析:\nReason {index}",
        },
        tags=["ankismart", "history"],
        metadata=CardMetadata(
            source_document=source_document,
            strategy_id="basic",
            quality_flags=[],
        ),
    )


def test_history_store_saves_and_reads_generation_batch(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    cards = [_card(1), _card(2, source_document="chapter.md")]

    summary = store.save_generation_batch(
        cards,
        batch_id="batch-1",
        title="交通控制制卡",
        status="success",
        target_total=2,
        low_quality_count=0,
        duration_seconds=1.5,
        metadata={"task_id": "task-1"},
    )

    assert summary.batch_id == "batch-1"
    assert summary.card_count == 2
    assert summary.metadata["task_id"] == "task-1"

    loaded = store.get_generation_batch("batch-1")

    assert loaded is not None
    assert loaded.summary.title == "交通控制制卡"
    assert [card.fields["Front"] for card in loaded.cards] == ["Question 1", "Question 2"]
    assert loaded.cards[1].metadata.source_document == "chapter.md"


def test_history_store_records_local_timezone_timestamp(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")

    summary = store.save_generation_batch([_card(1)], batch_id="batch-local-time")

    parsed = datetime.fromisoformat(summary.created_at)
    local_now = datetime.now().astimezone()
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == local_now.utcoffset()


def test_history_store_lists_batches_newest_first_with_pagination(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1)], batch_id="old", title="旧批次")
    store.save_generation_batch([_card(2)], batch_id="new", title="新批次")

    page = store.list_generation_batches(limit=1, offset=0)
    next_page = store.list_generation_batches(limit=1, offset=1)

    assert [item.batch_id for item in page] == ["new"]
    assert [item.batch_id for item in next_page] == ["old"]


def test_history_store_uses_insert_order_when_timestamps_match(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite3"
    store = SQLiteHistoryStore(db_path)
    store.save_generation_batch([_card(1)], batch_id="old", title="旧批次")
    store.save_generation_batch([_card(2)], batch_id="middle", title="中间批次")
    store.save_generation_batch([_card(3)], batch_id="new", title="新批次")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE generation_batches SET created_at = ?",
            ("2026-06-09T12:00:00.000000+08:00",),
        )

    assert [item.batch_id for item in store.list_generation_batches(limit=10)] == [
        "new",
        "middle",
        "old",
    ]

    pruned = store.prune_cache(max_size_mb=500, max_records=2)

    assert pruned.deleted_batch_ids == ["old"]
    assert [item.batch_id for item in store.list_generation_batches(limit=10)] == ["new", "middle"]


def test_history_store_replaces_existing_batch_cards(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1), _card(2)], batch_id="same", title="第一次")
    store.save_generation_batch([_card(3)], batch_id="same", title="第二次")

    loaded = store.get_generation_batch("same")

    assert loaded is not None
    assert loaded.summary.title == "第二次"
    assert [card.fields["Front"] for card in loaded.cards] == ["Question 3"]


def test_resolve_history_db_path_defaults_to_install_cache_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ANKISMART_HISTORY_DB_PATH", raising=False)
    monkeypatch.setattr("ankismart.core.config._resolve_project_root", lambda: tmp_path)

    path = resolve_history_db_path()

    assert path == tmp_path / "cache" / "history.sqlite3"


def test_history_store_reports_cache_stats(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1), _card(2)], batch_id="batch-1", title="第一批")

    stats = store.get_cache_stats()

    assert stats["batch_count"] == 1
    assert stats["card_count"] == 2
    assert stats["size_bytes"] > 0
    assert stats["size_mb"] > 0


def test_history_store_empty_reads_do_not_create_database(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"
    store = SQLiteHistoryStore(path)

    assert store.get_cache_stats()["batch_count"] == 0
    assert store.list_generation_batches() == []
    assert store.get_generation_batch("missing") is None
    assert store.delete_generation_batch("missing") is False
    assert path.exists() is False


def test_history_store_deletes_multiple_batches(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1)], batch_id="batch-1", title="第一批")
    store.save_generation_batch([_card(2)], batch_id="batch-2", title="第二批")

    deleted = store.delete_generation_batches(["batch-1", "missing", "batch-2"])

    assert deleted == 2
    assert store.list_generation_batches() == []


def test_history_store_clears_all_batches(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1)], batch_id="batch-1", title="第一批")
    store.save_generation_batch([_card(2)], batch_id="batch-2", title="第二批")

    deleted = store.clear_generation_history()

    assert deleted == 2
    assert store.get_cache_stats()["batch_count"] == 0
    assert store.get_cache_stats()["card_count"] == 0


def test_history_store_prunes_oldest_batches_by_count(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1)], batch_id="old", title="旧批次")
    store.save_generation_batch([_card(2)], batch_id="middle", title="中间批次")
    store.save_generation_batch([_card(3)], batch_id="new", title="新批次")

    pruned = store.prune_cache(max_size_mb=500, max_records=2)

    assert pruned.deleted_batches == 1
    assert pruned.deleted_batch_ids == ["old"]
    assert [item.batch_id for item in store.list_generation_batches(limit=10)] == ["new", "middle"]


def test_history_store_prunes_oldest_batches_by_size(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1)], batch_id="old", title="旧批次")
    store.save_generation_batch([_card(2)], batch_id="new", title="新批次")

    stats_before = store.get_cache_stats()
    pruned = store.prune_cache(max_size_mb=0, max_records=100)

    assert stats_before["batch_count"] == 2
    assert pruned.deleted_batch_ids == ["old", "new"]
    assert store.get_cache_stats()["batch_count"] == 0
