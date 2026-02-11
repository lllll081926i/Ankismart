from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


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


def setup_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger("ankismart")
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    formatter = JsonFormatter()

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    try:
        log_dir = Path.home() / ".ankismart" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "ankismart.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except OSError:
        pass


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"ankismart.{name}")
