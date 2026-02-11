from __future__ import annotations

from pathlib import Path

import chardet

from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult
from ankismart.core.tracing import get_trace_id, timed

logger = get_logger("converter.text")


def _detect_encoding(raw: bytes) -> str:
    result = chardet.detect(raw)
    return result.get("encoding") or "utf-8"


def _is_heading(line: str, avg_length: float) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.isupper() and len(stripped) > 1:
        return True
    if avg_length > 0 and len(stripped) < avg_length * 0.4 and not stripped.endswith("."):
        return True
    return False


def _structure_as_markdown(text: str) -> str:
    paragraphs = text.split("\n\n")
    all_lines: list[str] = []
    for para in paragraphs:
        lines = [line.strip() for line in para.strip().splitlines() if line.strip()]
        all_lines.extend(lines)

    avg_length = sum(len(line) for line in all_lines) / max(len(all_lines), 1)

    output_parts: list[str] = []
    for para in paragraphs:
        lines = [line.strip() for line in para.strip().splitlines() if line.strip()]
        if not lines:
            continue

        if len(lines) == 1 and _is_heading(lines[0], avg_length):
            output_parts.append(f"## {lines[0]}")
        else:
            output_parts.append(" ".join(lines))

    return "\n\n".join(output_parts) + "\n"


def convert(file_path: Path, trace_id: str = "") -> MarkdownResult:
    tid = trace_id or get_trace_id()
    with timed("text_convert"):
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

        content = _structure_as_markdown(text)
        logger.info("Converted text file", extra={"path": str(file_path), "trace_id": tid})

        return MarkdownResult(
            content=content,
            source_path=str(file_path),
            source_format="text",
            trace_id=tid,
        )
