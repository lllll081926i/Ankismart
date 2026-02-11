from __future__ import annotations

from ankismart.ui.workers import BatchGenerateWorker


def test_allocate_mix_counts_distributes_total() -> None:
    counts = BatchGenerateWorker._allocate_mix_counts(
        target_total=20,
        ratio_items=[
            {"strategy": "basic", "ratio": 40},
            {"strategy": "cloze", "ratio": 60},
        ],
    )

    assert sum(counts.values()) == 20
    assert counts["basic"] == 8
    assert counts["cloze"] == 12


def test_distribute_counts_per_document_keeps_sum() -> None:
    per_doc = BatchGenerateWorker._distribute_counts_per_document(
        total_docs=3,
        strategy_counts={"basic": 5, "cloze": 4},
    )

    assert len(per_doc) == 3
    assert sum(item.get("basic", 0) for item in per_doc) == 5
    assert sum(item.get("cloze", 0) for item in per_doc) == 4


def test_allocate_mix_counts_handles_invalid_ratio_items() -> None:
    counts = BatchGenerateWorker._allocate_mix_counts(
        target_total=10,
        ratio_items=[
            {"strategy": "basic", "ratio": "x"},
            {"strategy": "", "ratio": 50},
        ],
    )

    assert counts == {}

