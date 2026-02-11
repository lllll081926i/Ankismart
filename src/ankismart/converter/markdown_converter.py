from __future__ import annotations

from pathlib import Path

import chardet

from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult
from ankismart.core.tracing import get_trace_id, timed

logger = get_logger("converter.markdown")


def _detect_encoding(raw: bytes) -> str:
    result = chardet.detect(raw)
    return result.get("encoding") or "utf-8"


def _normalize(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines) + "\n"


def convert(file_path: Path, trace_id: str = "") -> MarkdownResult:
    tid = trace_id or get_trace_id()
    with timed("markdown_convert"):
        try:
            raw = file_path.read_bytes()
        except FileNotFoundError as exc:
            raise ConvertError(
                f"File not found: {file_path}",
                code=ErrorCode.E_FILE_NOT_FOUND,
                trace_id=tid,
            ) from exc
        except OSError as exc:
            raise ConvertError(
                f"Cannot read file: {file_path}: {exc}",
                trace_id=tid,
            ) from exc

        encoding = _detect_encoding(raw)
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError) as exc:
            raise ConvertError(
                f"Encoding detection failed for {file_path}: {exc}",
                trace_id=tid,
            ) from exc

        content = _normalize(text)
        logger.info("Converted markdown file", extra={"path": str(file_path), "trace_id": tid})

        return MarkdownResult(
            content=content,
            source_path=str(file_path),
            source_format="markdown",
            trace_id=tid,
        )
