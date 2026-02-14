"""Tests for ankismart.core.errors module."""
from __future__ import annotations

import pytest

from ankismart.core.errors import (
    AnkiGatewayError,
    AnkiSmartError,
    CardGenError,
    ConfigError,
    ConvertError,
    ErrorCode,
)
from ankismart.core.interfaces import IAnkiGateway, IApkgExporter, ICardGenerator, IConverter


class TestErrorCode:
    def test_all_codes_are_strings(self):
        for code in ErrorCode:
            assert isinstance(code, str)
            assert code.startswith("E_")

    def test_specific_codes_exist(self):
        assert ErrorCode.E_DECK_NOT_FOUND == "E_DECK_NOT_FOUND"
        assert ErrorCode.E_UNKNOWN == "E_UNKNOWN"
        assert ErrorCode.E_LLM_ERROR == "E_LLM_ERROR"
        assert ErrorCode.E_LLM_AUTH_ERROR == "E_LLM_AUTH_ERROR"
        assert ErrorCode.E_LLM_PERMISSION_ERROR == "E_LLM_PERMISSION_ERROR"


class TestAnkiSmartError:
    def test_defaults(self):
        err = AnkiSmartError()
        assert err.code == ErrorCode.E_UNKNOWN
        assert err.message == ""
        assert err.trace_id is None

    def test_custom_values(self):
        err = AnkiSmartError(
            code=ErrorCode.E_DECK_NOT_FOUND,
            message="deck missing",
            trace_id="abc-123",
        )
        assert err.code == ErrorCode.E_DECK_NOT_FOUND
        assert err.message == "deck missing"
        assert err.trace_id == "abc-123"

    def test_to_dict(self):
        err = AnkiSmartError(
            code=ErrorCode.E_LLM_ERROR,
            message="timeout",
            trace_id="t-1",
        )
        d = err.to_dict()
        assert d == {"code": "E_LLM_ERROR", "message": "timeout", "traceId": "t-1"}

    def test_to_dict_no_trace_id(self):
        err = AnkiSmartError(code=ErrorCode.E_UNKNOWN, message="oops")
        d = err.to_dict()
        assert d["traceId"] == ""

    def test_is_exception(self):
        err = AnkiSmartError(message="boom")
        assert isinstance(err, Exception)
        with pytest.raises(AnkiSmartError):
            raise err


class TestConvertError:
    def test_defaults(self):
        err = ConvertError()
        assert err.code == ErrorCode.E_CONVERT_FAILED
        assert err.message == "Document conversion failed"

    def test_custom_message(self):
        err = ConvertError("pdf broke", code=ErrorCode.E_FILE_NOT_FOUND, trace_id="t")
        assert err.message == "pdf broke"
        assert err.code == ErrorCode.E_FILE_NOT_FOUND
        assert err.trace_id == "t"

    def test_inherits_ankismart_error(self):
        assert issubclass(ConvertError, AnkiSmartError)


class TestCardGenError:
    def test_defaults(self):
        err = CardGenError()
        assert err.code == ErrorCode.E_LLM_ERROR
        assert err.message == "Card generation failed"

    def test_custom(self):
        err = CardGenError("parse fail", code=ErrorCode.E_LLM_PARSE_ERROR)
        assert err.code == ErrorCode.E_LLM_PARSE_ERROR


class TestAnkiGatewayError:
    def test_defaults(self):
        err = AnkiGatewayError()
        assert err.code == ErrorCode.E_ANKICONNECT_ERROR
        assert err.message == "AnkiConnect communication error"


class TestConfigError:
    def test_defaults(self):
        err = ConfigError()
        assert err.code == ErrorCode.E_CONFIG_INVALID
        assert err.message == "Configuration validation failed"

    def test_to_dict_chain(self):
        err = ConfigError("bad yaml", trace_id="x")
        d = err.to_dict()
        assert d["code"] == "E_CONFIG_INVALID"
        assert d["traceId"] == "x"


class TestInterfaces:
    def test_protocol_symbols_exist(self):
        assert IConverter is not None
        assert ICardGenerator is not None
        assert IAnkiGateway is not None
        assert IApkgExporter is not None
