from __future__ import annotations

from pathlib import Path

from ankismart.core.models import MarkdownResult
from ankismart.ui.workers import BatchGenerateWorker
from ankismart.ui.workers import BatchConvertWorker


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


def test_batch_convert_worker_has_ocr_progress_signal() -> None:
    worker = BatchConvertWorker([Path("demo.pdf")])
    assert hasattr(worker, "ocr_progress")


def test_batch_convert_worker_emits_ocr_progress(monkeypatch) -> None:
    captured_messages: list[str] = []

    class _FakeConverter:
        def __init__(self, *args, **kwargs):
            pass

        def convert(self, path, *, progress_callback=None):
            if progress_callback is not None:
                progress_callback("OCR 正在识别第 1 页...")
            return MarkdownResult(
                content="# ok",
                source_path=str(path),
                source_format="pdf",
                trace_id="t-ocr",
            )

    monkeypatch.setattr("ankismart.ui.workers.DocumentConverter", _FakeConverter)

    worker = BatchConvertWorker([Path("demo.pdf")])
    worker.ocr_progress.connect(captured_messages.append)

    worker.run()

    assert any("OCR" in msg for msg in captured_messages)
