from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _resolve_app_dir() -> Path:
    env_app_dir = os.getenv("ANKISMART_APP_DIR", "").strip()
    if env_app_dir:
        return Path(env_app_dir).expanduser().resolve()
    return _resolve_project_root() / ".local" / "ankismart"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from ankismart.core.tracing import get_trace_id

        entry: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
            "trace_id": get_trace_id(),
        }

        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "relativeCreated",
                "exc_info", "exc_text", "stack_info", "lineno", "funcName",
                "pathname", "filename", "module", "levelno", "levelname",
                "thread", "threadName", "process", "processName", "message",
                "msecs", "taskName", "trace_id",
            }:
                entry[key] = value

        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        module = record.name.replace("ankismart.", "")
        return f"[{ts}] {record.levelname:<7} {module}: {record.getMessage()}"


class ConsoleNoiseFilter(logging.Filter):
    def __init__(self, *, show_stage_timing: bool) -> None:
        super().__init__()
        self._show_stage_timing = show_stage_timing

    def filter(self, record: logging.LogRecord) -> bool:
        if (
            not self._show_stage_timing
            and record.name == "ankismart.tracing"
            and record.getMessage() == "stage completed"
        ):
            return False
        return True


def _configure_external_loggers() -> None:
    noisy_info_loggers = {
        "httpx",
        "httpcore",
        "openai",
        "paddlex",
        "paddleocr",
        "urllib3",
        "PIL",
    }
    for name in noisy_info_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)


def setup_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger("ankismart")
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.propagate = False

    _configure_external_loggers()

    show_stage_timing = _get_env_bool("ANKISMART_LOG_STAGE_TIMING", False)
    console_level_name = os.getenv("ANKISMART_CONSOLE_LOG_LEVEL", "INFO").upper()
    console_level = getattr(logging, console_level_name, logging.INFO)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(console_level)
    stream_handler.setFormatter(ConsoleFormatter())
    stream_handler.addFilter(ConsoleNoiseFilter(show_stage_timing=show_stage_timing))
    root_logger.addHandler(stream_handler)

    try:
        log_dir = _resolve_app_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "ankismart.log", encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(file_handler)
    except OSError:
        pass


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"ankismart.{name}")
