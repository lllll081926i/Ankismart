from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    E_DECK_NOT_FOUND = "E_DECK_NOT_FOUND"
    E_MODEL_NOT_FOUND = "E_MODEL_NOT_FOUND"
    E_REQUIRED_FIELD_MISSING = "E_REQUIRED_FIELD_MISSING"
    E_CLOZE_SYNTAX_INVALID = "E_CLOZE_SYNTAX_INVALID"
    E_MEDIA_INVALID = "E_MEDIA_INVALID"
    E_ANKICONNECT_ERROR = "E_ANKICONNECT_ERROR"
    E_CONVERT_FAILED = "E_CONVERT_FAILED"
    E_OCR_FAILED = "E_OCR_FAILED"
    E_LLM_ERROR = "E_LLM_ERROR"
    E_LLM_PARSE_ERROR = "E_LLM_PARSE_ERROR"
    E_CONFIG_INVALID = "E_CONFIG_INVALID"
    E_FILE_NOT_FOUND = "E_FILE_NOT_FOUND"
    E_FILE_TYPE_UNSUPPORTED = "E_FILE_TYPE_UNSUPPORTED"
    E_UNKNOWN = "E_UNKNOWN"


class AnkiSmartError(Exception):
    def __init__(
        self,
        code: ErrorCode = ErrorCode.E_UNKNOWN,
        message: str = "",
        trace_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.trace_id = trace_id
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        return {
            "code": str(self.code),
            "message": self.message,
            "traceId": self.trace_id or "",
        }


class ConvertError(AnkiSmartError):
    def __init__(
        self,
        message: str = "Document conversion failed",
        *,
        code: ErrorCode = ErrorCode.E_CONVERT_FAILED,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(code=code, message=message, trace_id=trace_id)


class CardGenError(AnkiSmartError):
    def __init__(
        self,
        message: str = "Card generation failed",
        *,
        code: ErrorCode = ErrorCode.E_LLM_ERROR,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(code=code, message=message, trace_id=trace_id)


class AnkiGatewayError(AnkiSmartError):
    def __init__(
        self,
        message: str = "AnkiConnect communication error",
        *,
        code: ErrorCode = ErrorCode.E_ANKICONNECT_ERROR,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(code=code, message=message, trace_id=trace_id)


class ConfigError(AnkiSmartError):
    def __init__(
        self,
        message: str = "Configuration validation failed",
        *,
        code: ErrorCode = ErrorCode.E_CONFIG_INVALID,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(code=code, message=message, trace_id=trace_id)
