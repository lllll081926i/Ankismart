from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_EXCLUDED_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "created",
    "relativeCreated",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "pathname",
    "filename",
    "module",
    "levelno",
    "levelname",
    "thread",
    "threadName",
    "process",
    "processName",
    "message",
    "msecs",
    "taskName",
    "trace_id",
}


def _collect_extra_fields(record: logging.LogRecord) -> dict[str, object]:
    extras: dict[str, object] = {}
    for key, value in record.__dict__.items():
        if key not in _EXCLUDED_RECORD_FIELDS:
            extras[key] = value
    return extras


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _is_portable_mode() -> bool:
    root = _resolve_project_root()
    portable_flag = root / ".portable"
    return portable_flag.exists()


def _resolve_app_dir() -> Path:
    env_app_dir = os.getenv("ANKISMART_APP_DIR", "").strip()
    if env_app_dir:
        return Path(env_app_dir).expanduser().resolve()

    root = _resolve_project_root()
    if _is_portable_mode():
        return root / "config"

    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            app_data = Path(os.getenv("LOCALAPPDATA", "~/.local"))
        else:
            app_data = Path.home() / ".local" / "share"
        return (app_data / "ankismart").expanduser().resolve()

    return root / ".local" / "ankismart"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from ankismart.core.tracing import get_trace_id

        trace_id = getattr(record, "trace_id", None) or get_trace_id()
        entry: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "trace_id": trace_id,
        }

        extras = _collect_extra_fields(record)
        if extras:
            event = extras.pop("event", None)
            if event is not None:
                entry["event"] = event
            if extras:
                entry["context"] = extras

        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from ankismart.core.tracing import get_trace_id

        ts = datetime.now().strftime("%H:%M:%S")
        module = record.name.replace("ankismart.", "")
        trace_id = getattr(record, "trace_id", None) or get_trace_id()
        trace_short = str(trace_id).split("-", 1)[0][:8]
        extras = _collect_extra_fields(record)
        event = extras.pop("event", None)

        line = f"[{ts}] {record.levelname:<7} {module} [{trace_short}]"
        if event:
            line = f"{line} {event}"
        if record.levelno >= logging.WARNING:
            line = f"{line} @{record.funcName}:{record.lineno}"

        line = f"{line}: {record.getMessage()}"

        if extras:
            keys = sorted(extras)
            preview = ", ".join(f"{key}={extras[key]}" for key in keys[:4])
            if len(keys) > 4:
                preview = f"{preview}, ..."
            line = f"{line} | {preview}"

        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            line = f"{line} | exc={exc.__class__.__name__}: {exc}"

        return line


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


def set_log_level(level: str) -> None:
    """Dynamically change the log level for all ankismart loggers.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR)
    """
    level_name = level.upper()
    level_int = getattr(logging, level_name, logging.INFO)

    # Update root ankismart logger
    root_logger = logging.getLogger("ankismart")
    root_logger.setLevel(level_int)

    # Update all handlers
    for handler in root_logger.handlers:
        # Only update file handler level, keep console handler as configured
        if isinstance(handler, logging.FileHandler):
            handler.setLevel(level_int)

    logger = get_logger("logging")
    logger.info(f"Log level changed to: {level_name}")


def get_log_directory() -> Path:
    """Get the directory where log files are stored.

    Returns:
        Path to the log directory.
    """
    return _resolve_app_dir() / "logs"
