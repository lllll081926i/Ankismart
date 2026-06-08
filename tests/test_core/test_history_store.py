from __future__ import annotations

from pathlib import Path

from ankismart.core.history_store import SQLiteHistoryStore
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


def test_history_store_lists_batches_newest_first_with_pagination(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1)], batch_id="old", title="旧批次")
    store.save_generation_batch([_card(2)], batch_id="new", title="新批次")

    page = store.list_generation_batches(limit=1, offset=0)
    next_page = store.list_generation_batches(limit=1, offset=1)

    assert [item.batch_id for item in page] == ["new"]
    assert [item.batch_id for item in next_page] == ["old"]


def test_history_store_replaces_existing_batch_cards(tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1), _card(2)], batch_id="same", title="第一次")
    store.save_generation_batch([_card(3)], batch_id="same", title="第二次")

    loaded = store.get_generation_batch("same")

    assert loaded is not None
    assert loaded.summary.title == "第二次"
    assert [card.fields["Front"] for card in loaded.cards] == ["Question 3"]
