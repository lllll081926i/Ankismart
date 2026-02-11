"""Tests for ankismart.core.logging module."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

from ankismart.core.logging import JsonFormatter, get_logger, setup_logging


class TestJsonFormatter:
    def _make_record(self, msg: str = "hello", level: int = logging.INFO, **extra) -> logging.LogRecord:
        record = logging.LogRecord(
            name="ankismart.test",
            level=level,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return record

    def test_output_is_valid_json(self):
        fmt = JsonFormatter()
        record = self._make_record("test message")
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "test message"

    def test_contains_required_fields(self):
        fmt = JsonFormatter()
        record = self._make_record("msg")
        parsed = json.loads(fmt.format(record))
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "module" in parsed
        assert "message" in parsed
        assert "trace_id" in parsed

    def test_level_name(self):
        fmt = JsonFormatter()
        record = self._make_record("warn", level=logging.WARNING)
        parsed = json.loads(fmt.format(record))
        assert parsed["level"] == "WARNING"

    def test_extra_fields_included(self):
        fmt = JsonFormatter()
        record = self._make_record("with extra", custom_field="custom_value")
        parsed = json.loads(fmt.format(record))
        assert parsed["custom_field"] == "custom_value"

    def test_exception_info_included(self):
        fmt = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="ankismart.test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]

    def test_no_exception_when_exc_info_none(self):
        fmt = JsonFormatter()
        record = self._make_record("no exc")
        parsed = json.loads(fmt.format(record))
        assert "exception" not in parsed

    def test_trace_id_from_context(self):
        from ankismart.core.tracing import _trace_id_var

        token = _trace_id_var.set("log-trace-123")
        try:
            fmt = JsonFormatter()
            record = self._make_record("traced")
            parsed = json.loads(fmt.format(record))
            assert parsed["trace_id"] == "log-trace-123"
        finally:
            _trace_id_var.reset(token)

    def test_internal_fields_excluded(self):
        fmt = JsonFormatter()
        record = self._make_record("check exclusions")
        parsed = json.loads(fmt.format(record))
        # These internal LogRecord fields should NOT appear as top-level keys
        for excluded in ("name", "msg", "args", "created", "lineno", "funcName", "pathname"):
            assert excluded not in parsed


class TestSetupLogging:
    def test_sets_level_and_adds_handlers(self):
        with patch("ankismart.core.logging.Path.home") as mock_home, \
             patch("ankismart.core.logging.logging.FileHandler") as mock_fh:
            mock_home.return_value = Path("/fake/home")
            mock_fh_instance = mock_fh.return_value
            mock_fh_instance.setFormatter = lambda f: None

            setup_logging(logging.DEBUG)

        root = logging.getLogger("ankismart")
        assert root.level == logging.DEBUG
        # At least the stream handler should be present
        assert len(root.handlers) >= 1

    def test_clears_existing_handlers(self):
        root = logging.getLogger("ankismart")
        root.addHandler(logging.StreamHandler())
        root.addHandler(logging.StreamHandler())

        with patch("ankismart.core.logging.Path.home") as mock_home, \
             patch("ankismart.core.logging.logging.FileHandler") as mock_fh:
            mock_home.return_value = Path("/fake/home")
            mock_fh_instance = mock_fh.return_value
            mock_fh_instance.setFormatter = lambda f: None

            setup_logging()

        # Handlers were cleared and re-added (stream + file = 2)
        assert len(root.handlers) <= 2

    def test_file_handler_oserror_is_silent(self):
        """If FileHandler raises OSError, setup_logging should not raise."""
        with patch("ankismart.core.logging.logging.FileHandler", side_effect=OSError("disk full")):
            setup_logging()

        root = logging.getLogger("ankismart")
        # Only the stream handler should be present (file handler failed)
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_default_level_is_info(self):
        with patch("ankismart.core.logging.Path.home") as mock_home, \
             patch("ankismart.core.logging.logging.FileHandler") as mock_fh:
            mock_home.return_value = Path("/fake/home")
            mock_fh_instance = mock_fh.return_value
            mock_fh_instance.setFormatter = lambda f: None

            setup_logging()

        root = logging.getLogger("ankismart")
        assert root.level == logging.INFO


class TestGetLogger:
    def test_returns_child_logger(self):
        lg = get_logger("mymodule")
        assert lg.name == "ankismart.mymodule"
        assert isinstance(lg, logging.Logger)

    def test_different_names_different_loggers(self):
        a = get_logger("aaa")
        b = get_logger("bbb")
        assert a is not b
        assert a.name != b.name
