"""Tests for ankismart.core.tracing module."""
from __future__ import annotations

import re
import time
from unittest.mock import patch

import pytest

from ankismart.core.tracing import (
    _trace_id_var,
    export_metrics_prometheus,
    export_metrics_snapshot,
    generate_trace_id,
    get_trace_id,
    metrics,
    set_trace_id,
    timed,
    timed_async,
    trace_context,
)

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class TestGenerateTraceId:
    def test_returns_uuid_string(self):
        tid = generate_trace_id()
        assert UUID_RE.match(tid)

    def test_unique_each_call(self):
        ids = {generate_trace_id() for _ in range(50)}
        assert len(ids) == 50


class TestGetSetTraceId:
    def test_get_creates_id_when_none(self):
        # Reset context var
        token = _trace_id_var.set(None)
        try:
            tid = get_trace_id()
            assert UUID_RE.match(tid)
            # Subsequent call returns the same id
            assert get_trace_id() == tid
        finally:
            _trace_id_var.reset(token)

    def test_set_then_get(self):
        token = _trace_id_var.set(None)
        try:
            set_trace_id("custom-trace-id")
            assert get_trace_id() == "custom-trace-id"
        finally:
            _trace_id_var.reset(token)


class TestTraceContext:
    def test_provides_trace_id(self):
        with trace_context("my-trace") as tid:
            assert tid == "my-trace"
            assert get_trace_id() == "my-trace"

    def test_auto_generates_when_none(self):
        with trace_context() as tid:
            assert UUID_RE.match(tid)

    def test_restores_previous_value(self):
        token = _trace_id_var.set("outer")
        try:
            with trace_context("inner") as tid:
                assert tid == "inner"
            # After exiting, the outer value is restored
            assert _trace_id_var.get() == "outer"
        finally:
            _trace_id_var.reset(token)

    def test_restores_none(self):
        token = _trace_id_var.set(None)
        try:
            with trace_context("temp"):
                pass
            assert _trace_id_var.get() is None
        finally:
            _trace_id_var.reset(token)


class TestTimed:
    def test_logs_duration(self):
        with patch("ankismart.core.tracing.logger") as mock_logger:
            with timed("test_stage"):
                time.sleep(0.01)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "stage completed"
            extra = call_args[1]["extra"]
            assert extra["stage_name"] == "test_stage"
            assert extra["duration_ms"] >= 0
            assert "trace_id" in extra

    def test_logs_even_on_exception(self):
        with patch("ankismart.core.tracing.logger") as mock_logger:
            with pytest.raises(ValueError, match="boom"):
                with timed("failing_stage"):
                    raise ValueError("boom")

            mock_logger.info.assert_called_once()
            extra = mock_logger.info.call_args[1]["extra"]
            assert extra["stage_name"] == "failing_stage"


class TestTimedAsync:
    def test_logs_duration(self):
        import asyncio

        async def _run():
            with patch("ankismart.core.tracing.logger") as mock_logger:
                async with timed_async("async_stage"):
                    pass

                mock_logger.info.assert_called_once()
                extra = mock_logger.info.call_args[1]["extra"]
                assert extra["stage_name"] == "async_stage"
                assert extra["duration_ms"] >= 0

        asyncio.run(_run())


class TestMetricsCollector:
    def test_counter_and_gauge_snapshot_export(self):
        metrics.reset()
        metrics.increment("llm_requests_total")
        metrics.increment("llm_requests_failed_total", labels={"code": "E_LLM_ERROR"})
        metrics.set_gauge("anki_push_success_ratio", 0.75)
        metrics.record_cache_hit()
        metrics.record_cache_miss()

        snapshot = export_metrics_snapshot()
        counters = snapshot["counters"]
        gauges = snapshot["gauges"]

        assert counters["llm_requests_total"] == 1.0
        assert counters["llm_requests_failed_total[code=E_LLM_ERROR]"] == 1.0
        assert gauges["anki_push_success_ratio"] == 0.75
        assert snapshot["cache_hits"] == 1
        assert snapshot["cache_misses"] == 1

    def test_export_prometheus_contains_expected_metrics(self):
        metrics.reset()
        metrics.increment("convert_success_total", 2)
        metrics.set_gauge("convert_cache_hit_ratio", 0.5)

        payload = export_metrics_prometheus()

        assert "ankismart_convert_success_total 2.0" in payload
        assert "ankismart_convert_cache_hit_ratio 0.5" in payload
        assert "ankismart_cache_hits_total" in payload

    def test_records_metrics(self):
        import asyncio

        metrics.reset()

        async def _run():
            with patch("ankismart.core.tracing.logger"):
                async with timed_async("async_metric_stage"):
                    pass

        asyncio.run(_run())

        snapshot = metrics.snapshot()
        assert "async_metric_stage" in snapshot
        assert snapshot["async_metric_stage"].count == 1
        assert snapshot["async_metric_stage"].total_ms >= 0

    def test_logs_even_on_exception(self):
        import asyncio

        async def _run():
            with patch("ankismart.core.tracing.logger") as mock_logger:
                with pytest.raises(RuntimeError):
                    async with timed_async("fail_async"):
                        raise RuntimeError("async boom")

                mock_logger.info.assert_called_once()

        asyncio.run(_run())
