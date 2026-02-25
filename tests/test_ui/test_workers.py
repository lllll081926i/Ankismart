from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ankismart.core.config import LLMProviderConfig
from ankismart.core.errors import CardGenError, ErrorCode
from ankismart.core.models import ConvertedDocument, MarkdownResult
from ankismart.ui.workers import (
    BatchConvertWorker,
    BatchGenerateWorker,
    ConnectionCheckWorker,
    ConvertWorker,
    ExportWorker,
    GenerateWorker,
    ProviderConnectionWorker,
    PushWorker,
    _format_error_for_ui,
)


def test_format_error_for_ui_preserves_error_code() -> None:
    error = CardGenError("invalid token", code=ErrorCode.E_LLM_AUTH_ERROR, trace_id="t-1")
    assert _format_error_for_ui(error) == "[E_LLM_AUTH_ERROR] invalid token"


def test_convert_worker_success_emits_progress_and_finished() -> None:
    messages: list[str] = []
    results: list[MarkdownResult] = []

    class _FakeConverter:
        def convert(self, path, *, progress_callback=None):
            if progress_callback:
                progress_callback("正在处理内容")
            return MarkdownResult(
                content="# ok",
                source_path=str(path),
                source_format="markdown",
                trace_id="trace-c1",
            )

    worker = ConvertWorker(_FakeConverter(), Path("demo.md"))
    worker.progress.connect(messages.append)
    worker.finished.connect(results.append)
    worker.run()

    assert any("正在转换文件" in msg for msg in messages)
    assert any("正在处理内容" in msg for msg in messages)
    assert len(results) == 1
    assert results[0].trace_id == "trace-c1"


def test_convert_worker_error_emits_structured_message() -> None:
    errors: list[str] = []

    class _FailConverter:
        def convert(self, *_args, **_kwargs):
            raise CardGenError("boom", code=ErrorCode.E_LLM_AUTH_ERROR, trace_id="trace-c2")

    worker = ConvertWorker(_FailConverter(), Path("bad.md"))
    worker.error.connect(errors.append)
    worker.run()

    assert errors == ["[E_LLM_AUTH_ERROR] boom"]


def test_generate_worker_success_emits_finished() -> None:
    events: list[str] = []
    finished: list[list] = []

    class _FakeGenerator:
        def generate(self, request):
            events.append(request.strategy)
            return []

    markdown = MarkdownResult(
        content="content",
        source_path="demo.md",
        source_format="markdown",
        trace_id="trace-g1",
    )
    worker = GenerateWorker(
        _FakeGenerator(),
        markdown,
        deck_name="Default",
        tags=["tag1"],
        strategy="basic",
        target_count=3,
    )
    worker.finished.connect(finished.append)
    worker.run()

    assert events == ["basic"]
    assert finished == [[]]


def test_generate_worker_error_emits_structured_message() -> None:
    errors: list[str] = []

    class _FailGenerator:
        def generate(self, _request):
            raise CardGenError(
                "provider down",
                code=ErrorCode.E_LLM_AUTH_ERROR,
                trace_id="trace-g2",
            )

    markdown = MarkdownResult(
        content="content",
        source_path="demo.md",
        source_format="markdown",
        trace_id="trace-g2",
    )
    worker = GenerateWorker(
        _FailGenerator(),
        markdown,
        deck_name="Default",
        tags=[],
        strategy="basic",
    )
    worker.error.connect(errors.append)
    worker.run()

    assert errors == ["[E_LLM_AUTH_ERROR] provider down"]


def test_push_worker_cancelled_before_run_emits_cancelled() -> None:
    called = {"push": False}
    cancelled: list[bool] = []

    class _Gateway:
        def push(self, _cards, *, update_mode):
            called["push"] = True
            return SimpleNamespace(succeeded=1, failed=0)

    worker = PushWorker(_Gateway(), [])
    worker.cancelled.connect(lambda: cancelled.append(True))
    worker.cancel()
    worker.run()

    assert cancelled == [True]
    assert called["push"] is False


def test_push_worker_success_emits_finished() -> None:
    finished = []

    class _Gateway:
        def push(self, _cards, *, update_mode):
            assert update_mode == "create_only"
            return SimpleNamespace(succeeded=2, failed=0)

    worker = PushWorker(_Gateway(), [])
    worker.finished.connect(finished.append)
    worker.run()

    assert len(finished) == 1
    assert finished[0].succeeded == 2


def test_push_worker_error_emits_structured_message() -> None:
    errors: list[str] = []

    class _FailGateway:
        def push(self, _cards, *, update_mode):
            raise CardGenError("push failed", code=ErrorCode.E_LLM_AUTH_ERROR, trace_id="trace-p1")

    worker = PushWorker(_FailGateway(), [])
    worker.error.connect(errors.append)
    worker.run()

    assert errors == ["[E_LLM_AUTH_ERROR] push failed"]


def test_export_worker_success_emits_output_path(tmp_path) -> None:
    finished: list[str] = []
    output_path = tmp_path / "cards.apkg"

    class _Exporter:
        def export(self, _cards, path):
            return path

    worker = ExportWorker(_Exporter(), [], output_path)
    worker.finished.connect(finished.append)
    worker.run()

    assert finished == [str(output_path)]


def test_export_worker_error_emits_message(tmp_path) -> None:
    errors: list[str] = []

    class _FailExporter:
        def export(self, _cards, _path):
            raise RuntimeError("export failed")

    worker = ExportWorker(_FailExporter(), [], tmp_path / "cards.apkg")
    worker.error.connect(errors.append)
    worker.run()

    assert errors == ["export failed"]


def test_connection_check_worker_success(monkeypatch) -> None:
    results: list[bool] = []

    class _Client:
        def __init__(self, url, key, proxy_url):
            self.url = url
            self.key = key
            self.proxy_url = proxy_url

        def check_connection(self):
            return True

    monkeypatch.setattr("ankismart.ui.workers.AnkiConnectClient", _Client)

    worker = ConnectionCheckWorker("http://127.0.0.1:8765", "k", proxy_url="")
    worker.finished.connect(results.append)
    worker.run()

    assert results == [True]


def test_connection_check_worker_exception_returns_false(monkeypatch) -> None:
    results: list[bool] = []

    class _BrokenClient:
        def __init__(self, *args, **kwargs):
            raise OSError("socket error")

    monkeypatch.setattr("ankismart.ui.workers.AnkiConnectClient", _BrokenClient)

    worker = ConnectionCheckWorker("http://127.0.0.1:8765", "k", proxy_url="")
    worker.finished.connect(results.append)
    worker.run()

    assert results == [False]


def test_provider_connection_worker_success(monkeypatch) -> None:
    finished: list[tuple[bool, str]] = []
    captured: dict[str, object] = {}

    class _FakeLLMClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def validate_connection(self):
            return True

    monkeypatch.setattr("ankismart.card_gen.llm_client.LLMClient", _FakeLLMClient)

    provider = LLMProviderConfig(
        name="OpenAI",
        api_key="k",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        rpm_limit=5,
    )
    worker = ProviderConnectionWorker(provider, proxy_url="http://127.0.0.1:7890", temperature=0.2)
    worker.finished.connect(lambda ok, message: finished.append((ok, message)))
    worker.run()

    assert finished == [(True, "")]
    assert captured["model"] == "gpt-4o-mini"
    assert captured["proxy_url"] == "http://127.0.0.1:7890"


def test_provider_connection_worker_error_emits_structured_message(monkeypatch) -> None:
    finished: list[tuple[bool, str]] = []

    class _BrokenLLMClient:
        def __init__(self, **kwargs):
            raise CardGenError(
                "not reachable",
                code=ErrorCode.E_LLM_AUTH_ERROR,
                trace_id="trace-p2",
            )

    monkeypatch.setattr("ankismart.card_gen.llm_client.LLMClient", _BrokenLLMClient)

    provider = LLMProviderConfig(name="OpenAI", api_key="k", model="gpt-4o-mini")
    worker = ProviderConnectionWorker(provider)
    worker.finished.connect(lambda ok, message: finished.append((ok, message)))
    worker.run()

    assert finished == [(False, "[E_LLM_AUTH_ERROR] not reachable")]


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


def test_batch_generate_worker_zero_concurrency_uses_document_count(monkeypatch) -> None:
    import concurrent.futures
    from types import SimpleNamespace

    docs = [
        ConvertedDocument(
            result=MarkdownResult(
                content="demo",
                source_path=f"{i}.md",
                source_format="markdown",
                trace_id=f"trace-{i}",
            ),
            file_name=f"{i}.md",
        )
        for i in range(3)
    ]

    captured = {"max_workers": None}

    class _FakeExecutor:
        def __init__(self, max_workers=None, **kwargs):
            captured["max_workers"] = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args, **kwargs):
            future = concurrent.futures.Future()
            try:
                future.set_result(fn(*args, **kwargs))
            except Exception as exc:  # pragma: no cover - defensive for test helper
                future.set_exception(exc)
            return future

    monkeypatch.setattr("concurrent.futures.ThreadPoolExecutor", _FakeExecutor)
    monkeypatch.setattr("ankismart.ui.workers.CardGenerator.generate", lambda _self, _request: [])

    worker = BatchGenerateWorker(
        documents=docs,
        generation_config={"target_total": 3, "strategy_mix": [{"strategy": "basic", "ratio": 1}]},
        llm_client=object(),
        deck_name="Default",
        tags=[],
        config=SimpleNamespace(llm_concurrency=0),
    )
    worker.run()

    assert captured["max_workers"] == len(docs)


def test_batch_generate_worker_emits_structured_error_when_all_failed(monkeypatch) -> None:
    doc = ConvertedDocument(
        result=MarkdownResult(
            content="demo",
            source_path="a.md",
            source_format="markdown",
            trace_id="trace-1",
        ),
        file_name="a.md",
    )

    def _always_fail_generate(_self, _request):
        raise CardGenError(
            "auth failed",
            code=ErrorCode.E_LLM_AUTH_ERROR,
            trace_id="trace-1",
        )

    monkeypatch.setattr("ankismart.ui.workers.CardGenerator.generate", _always_fail_generate)

    worker = BatchGenerateWorker(
        documents=[doc],
        generation_config={"target_total": 1, "strategy_mix": [{"strategy": "basic", "ratio": 1}]},
        llm_client=object(),
        deck_name="Default",
        tags=[],
    )

    errors: list[str] = []
    worker.error.connect(errors.append)
    worker.run()

    assert len(errors) == 1
    assert errors[0].startswith("[E_LLM_AUTH_ERROR]")


def test_batch_generate_worker_adaptive_concurrency_reduces_on_throttle() -> None:
    doc = ConvertedDocument(
        result=MarkdownResult(
            content="demo",
            source_path="a.md",
            source_format="markdown",
            trace_id="trace-adapt-down",
        ),
        file_name="a.md",
    )
    config = SimpleNamespace(
        llm_concurrency=3,
        llm_adaptive_concurrency=True,
        llm_concurrency_max=6,
    )
    worker = BatchGenerateWorker(
        documents=[doc],
        generation_config={"target_total": 1, "strategy_mix": [{"strategy": "basic", "ratio": 1}]},
        llm_client=object(),
        deck_name="Default",
        tags=[],
        config=config,
    )
    messages: list[str] = []
    worker.progress.connect(messages.append)

    worker._throttle_events = 1
    worker._apply_adaptive_concurrency(configured_workers=3, had_error=True)

    assert config.llm_concurrency == 2
    assert any("自动将并发从 3 调整为 2" in message for message in messages)


def test_batch_generate_worker_adaptive_concurrency_increases_when_stable() -> None:
    doc = ConvertedDocument(
        result=MarkdownResult(
            content="demo",
            source_path="a.md",
            source_format="markdown",
            trace_id="trace-adapt-up",
        ),
        file_name="a.md",
    )
    config = SimpleNamespace(
        llm_concurrency=2,
        llm_adaptive_concurrency=True,
        llm_concurrency_max=3,
    )
    worker = BatchGenerateWorker(
        documents=[doc],
        generation_config={"target_total": 1, "strategy_mix": [{"strategy": "basic", "ratio": 1}]},
        llm_client=object(),
        deck_name="Default",
        tags=[],
        config=config,
    )
    messages: list[str] = []
    worker.progress.connect(messages.append)

    worker._throttle_events = 0
    worker._timeout_events = 0
    worker._apply_adaptive_concurrency(configured_workers=2, had_error=False)

    assert config.llm_concurrency == 3
    assert any("自动将并发从 2 调整为 3" in message for message in messages)
