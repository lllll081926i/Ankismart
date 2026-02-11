from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

logger = logging.getLogger("ankismart.tracing")


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
        logger.info(
            "stage completed",
            extra={
                "stage_name": name,
                "duration_ms": round(duration_ms, 2),
                "trace_id": get_trace_id(),
            },
        )
