from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator, Generator
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

    def snapshot(self) -> dict[str, StageMetrics]:
        with self._lock:
            return dict(self._stages)

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


metrics = MetricsCollector()


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
