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


def test_batch_convert_worker_cancel_stops_processing(monkeypatch) -> None:
    convert_count = {"n": 0}

    class _SlowConverter:
        def __init__(self, *a, **kw):
            pass

        def convert(self, path, *, progress_callback=None):
            convert_count["n"] += 1
            return MarkdownResult(
                content="ok",
                source_path=str(path),
                source_format="md",
                trace_id="t",
            )

    monkeypatch.setattr("ankismart.ui.workers.DocumentConverter", _SlowConverter)

    worker = BatchConvertWorker([Path(f"{i}.md") for i in range(10)])
    # Cancel immediately
    worker.cancel()
    worker.run()

    # Should have processed 0 or very few files
    assert convert_count["n"] < 10


def test_batch_convert_worker_retry_on_failure(monkeypatch) -> None:
    call_count = {"n": 0}

    class _FailOnceConverter:
        def __init__(self, *a, **kw):
            pass

        def convert(self, path, *, progress_callback=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("transient error")
            return MarkdownResult(
                content="ok",
                source_path=str(path),
                source_format="pdf",
                trace_id="t",
            )

    monkeypatch.setattr("ankismart.ui.workers.DocumentConverter", _FailOnceConverter)

    worker = BatchConvertWorker([Path("demo.pdf")])
    results: list = []
    worker.finished.connect(results.append)
    worker.run()

    # The retry should have succeeded
    assert len(results) == 1
    assert len(results[0].documents) == 1
    assert call_count["n"] == 2


def test_batch_convert_worker_file_error_emitted_on_final_failure(monkeypatch) -> None:
    class _AlwaysFailConverter:
        def __init__(self, *a, **kw):
            pass

        def convert(self, path, *, progress_callback=None):
            raise RuntimeError("permanent error")

    monkeypatch.setattr("ankismart.ui.workers.DocumentConverter", _AlwaysFailConverter)

    worker = BatchConvertWorker([Path("bad.pdf")])
    file_errors: list[str] = []
    worker.file_error.connect(file_errors.append)
    worker.run()

    assert len(file_errors) == 1
    assert "permanent error" in file_errors[0]


def test_batch_generate_worker_has_cancel() -> None:
    worker = BatchGenerateWorker.__new__(BatchGenerateWorker)
    worker._cancelled = False
    worker.cancel()
    assert worker._cancelled is True
