"""MarkItDown converter backend for fast document conversion."""

from __future__ import annotations

from pathlib import Path

from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult

logger = get_logger("converter.markitdown")


def convert(file_path: Path, trace_id: str) -> MarkdownResult:
    """Convert document to Markdown using Microsoft MarkItDown.

    Fast and lightweight converter, ideal for text-based documents.
    Falls back gracefully if MarkItDown is unavailable.

    Args:
        file_path: Path to the input file
        trace_id: Trace ID for logging

    Returns:
        MarkdownResult with converted content

    Raises:
        ConvertError: If conversion fails
    """
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise ConvertError(
            "MarkItDown is not available. Please install with: uv add markitdown",
            code=ErrorCode.E_CONVERT_FAILED,
            trace_id=trace_id,
        ) from exc

    if not file_path.exists():
        raise ConvertError(
            f"File not found: {file_path}",
            code=ErrorCode.E_FILE_NOT_FOUND,
            trace_id=trace_id,
        )

    try:
        md_converter = MarkItDown()
        result = md_converter.convert(str(file_path))

        if not result or not hasattr(result, "text_content"):
            raise ConvertError(
                "MarkItDown returned invalid result",
                code=ErrorCode.E_CONVERT_FAILED,
                trace_id=trace_id,
            )

        content = result.text_content.strip()

        if not content:
            raise ConvertError(
                "MarkItDown returned empty content",
                code=ErrorCode.E_CONVERT_FAILED,
                trace_id=trace_id,
            )

        logger.info(
            "MarkItDown conversion completed",
            extra={
                "trace_id": trace_id,
                "file": file_path.name,
                "content_length": len(content),
            },
        )

        return MarkdownResult(
            content=content,
            source_path=str(file_path),
            source_format=file_path.suffix.lstrip(".").lower(),
            trace_id=trace_id,
        )

    except ConvertError:
        raise
    except Exception as exc:
        raise ConvertError(
            f"MarkItDown conversion failed: {exc}",
            code=ErrorCode.E_CONVERT_FAILED,
            trace_id=trace_id,
        ) from exc
