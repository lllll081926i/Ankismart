from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator, Generator, Mapping
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

logger = logging.getLogger("ankismart.tracing")


# ---------------------------------------------------------------------------
# Metrics collector
# ---------------------------------------------------------------------------

@dataclass
class StageMetrics:
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0


class MetricsCollector:
    """Thread-safe collector for stage timing metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stages: dict[str, StageMetrics] = defaultdict(StageMetrics)
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}

    @staticmethod
    def _normalize_labels(labels: Mapping[str, object] | None) -> tuple[tuple[str, str], ...]:
        if not labels:
            return ()
        normalized: list[tuple[str, str]] = []
        for key, value in labels.items():
            normalized.append((str(key), str(value)))
        normalized.sort(key=lambda item: item[0])
        return tuple(normalized)

    @staticmethod
    def _sanitize_metric_name(name: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip())
        safe = safe.strip("_")
        return safe or "metric"

    @staticmethod
    def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return ""
        parts = [f'{k}="{v}"' for k, v in labels]
        return "{" + ",".join(parts) + "}"

    @staticmethod
    def _format_snapshot_key(name: str, labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return name
        joined = ",".join(f"{k}={v}" for k, v in labels)
        return f"{name}[{joined}]"

    def record(self, stage_name: str, duration_ms: float) -> None:
        with self._lock:
            m = self._stages[stage_name]
            m.count += 1
            m.total_ms += duration_ms
            m.min_ms = min(m.min_ms, duration_ms)
            m.max_ms = max(m.max_ms, duration_ms)

    def record_cache_hit(self) -> None:
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self._cache_misses += 1

    def increment(self, name: str, value: float = 1.0, labels: Mapping[str, object] | None = None) -> None:
        if value == 0:
            return
        key = (name, self._normalize_labels(labels))
        with self._lock:
            self._counters[key] += float(value)

    def set_gauge(self, name: str, value: float, labels: Mapping[str, object] | None = None) -> None:
        key = (name, self._normalize_labels(labels))
        with self._lock:
            self._gauges[key] = float(value)

    def get_counter(self, name: str, labels: Mapping[str, object] | None = None) -> float:
        key = (name, self._normalize_labels(labels))
        with self._lock:
            return self._counters.get(key, 0.0)

    def get_gauge(self, name: str, labels: Mapping[str, object] | None = None) -> float:
        key = (name, self._normalize_labels(labels))
        with self._lock:
            return self._gauges.get(key, 0.0)

    def snapshot(self) -> dict[str, StageMetrics]:
        with self._lock:
            return {
                name: StageMetrics(
                    count=metric.count,
                    total_ms=metric.total_ms,
                    min_ms=metric.min_ms,
                    max_ms=metric.max_ms,
                )
                for name, metric in self._stages.items()
            }

    def snapshot_export(self) -> dict[str, object]:
        with self._lock:
            stages = {
                name: {
                    "count": metric.count,
                    "total_ms": round(metric.total_ms, 4),
                    "avg_ms": round(metric.avg_ms, 4),
                    "min_ms": round(0.0 if metric.count == 0 else metric.min_ms, 4),
                    "max_ms": round(metric.max_ms, 4),
                }
                for name, metric in self._stages.items()
            }
            counters = {
                self._format_snapshot_key(name, labels): value
                for (name, labels), value in self._counters.items()
            }
            gauges = {
                self._format_snapshot_key(name, labels): value
                for (name, labels), value in self._gauges.items()
            }
            return {
                "stages": stages,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "counters": counters,
                "gauges": gauges,
            }

    def export_prometheus(self) -> str:
        with self._lock:
            cache_hits = self._cache_hits
            cache_misses = self._cache_misses
            stage_items = sorted(self._stages.items(), key=lambda item: item[0])
            counter_items = sorted(self._counters.items(), key=lambda item: (item[0][0], item[0][1]))
            gauge_items = sorted(self._gauges.items(), key=lambda item: (item[0][0], item[0][1]))

        lines: list[str] = [
            "# TYPE ankismart_cache_hits_total counter",
            f"ankismart_cache_hits_total {cache_hits}",
            "# TYPE ankismart_cache_misses_total counter",
            f"ankismart_cache_misses_total {cache_misses}",
        ]

        for stage_name, metric in stage_items:
            labels = f'{{stage="{stage_name}"}}'
            lines.append(f"ankismart_stage_duration_count{labels} {metric.count}")
            lines.append(f"ankismart_stage_duration_sum_ms{labels} {metric.total_ms}")
            lines.append(f"ankismart_stage_duration_avg_ms{labels} {metric.avg_ms}")
            min_ms = 0.0 if metric.count == 0 else metric.min_ms
            lines.append(f"ankismart_stage_duration_min_ms{labels} {min_ms}")
            lines.append(f"ankismart_stage_duration_max_ms{labels} {metric.max_ms}")

        for (name, labels), value in counter_items:
            metric_name = f"ankismart_{self._sanitize_metric_name(name)}"
            lines.append(f"{metric_name}{self._format_labels(labels)} {value}")

        for (name, labels), value in gauge_items:
            metric_name = f"ankismart_{self._sanitize_metric_name(name)}"
            lines.append(f"{metric_name}{self._format_labels(labels)} {value}")

        return "\n".join(lines) + "\n"

    @property
    def cache_hits(self) -> int:
        with self._lock:
            return self._cache_hits

    @property
    def cache_misses(self) -> int:
        with self._lock:
            return self._cache_misses

    def reset(self) -> None:
        with self._lock:
            self._stages.clear()
            self._cache_hits = 0
            self._cache_misses = 0
            self._counters.clear()
            self._gauges.clear()


metrics = MetricsCollector()


def export_metrics_snapshot() -> dict[str, object]:
    return metrics.snapshot_export()


def export_metrics_prometheus() -> str:
    return metrics.export_prometheus()


# ---------------------------------------------------------------------------
# Trace ID management
# ---------------------------------------------------------------------------


def generate_trace_id() -> str:
    return str(uuid.uuid4())


def get_trace_id() -> str:
    trace_id = _trace_id_var.get()
    if trace_id is None:
        trace_id = generate_trace_id()
        _trace_id_var.set(trace_id)
    return trace_id


def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)


@contextmanager
def trace_context(trace_id: str | None = None) -> Generator[str, None, None]:
    token: Token[str | None] = _trace_id_var.set(trace_id or generate_trace_id())
    try:
        yield _trace_id_var.get()  # type: ignore[arg-type]
    finally:
        _trace_id_var.reset(token)


@contextmanager
def timed(name: str) -> Generator[None, None, None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        metrics.record(name, duration_ms)
        logger.info(
            "stage completed",
            extra={
                "stage_name": name,
                "duration_ms": round(duration_ms, 2),
                "trace_id": get_trace_id(),
            },
        )


@asynccontextmanager
async def timed_async(name: str) -> AsyncGenerator[None, None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        metrics.record(name, duration_ms)
        logger.info(
            "stage completed",
            extra={
                "stage_name": name,
                "duration_ms": round(duration_ms, 2),
                "trace_id": get_trace_id(),
            },
        )
