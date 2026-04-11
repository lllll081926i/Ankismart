from __future__ import annotations

from pathlib import Path

from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.models import MarkdownResult


def convert(file_path: Path, trace_id: str) -> MarkdownResult:
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise ConvertError(
            "MarkItDown backend is not available. Please install the `markitdown` dependency.",
            code=ErrorCode.E_CONVERT_FAILED,
            trace_id=trace_id,
        ) from exc

    try:
        result = MarkItDown().convert(str(file_path))
    except Exception as exc:
        raise ConvertError(
            f"MarkItDown conversion failed: {exc}",
            code=ErrorCode.E_CONVERT_FAILED,
            trace_id=trace_id,
        ) from exc

    content = str(getattr(result, "text_content", "") or "").strip()
    if not content:
        raise ConvertError(
            "MarkItDown conversion returned empty content",
            code=ErrorCode.E_CONVERT_FAILED,
            trace_id=trace_id,
        )

    return MarkdownResult(
        content=content,
        source_path=str(file_path),
        source_format=file_path.suffix.lstrip(".").lower(),
        trace_id=trace_id,
    )
