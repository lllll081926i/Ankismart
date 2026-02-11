from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.table import Table as DocxTable

from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult
from ankismart.core.tracing import get_trace_id, timed

logger = get_logger("converter.docx")

_HEADING_MAP = {
    "Heading 1": "# ",
    "Heading 2": "## ",
    "Heading 3": "### ",
    "Heading 4": "#### ",
    "Heading 5": "##### ",
    "Heading 6": "###### ",
}


def _convert_table(table: DocxTable) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
        rows.append(cells)

    if not rows:
        return ""

    col_count = max(len(r) for r in rows)
    for row in rows:
        while len(row) < col_count:
            row.append("")

    lines: list[str] = []
    header = "| " + " | ".join(rows[0]) + " |"
    separator = "| " + " | ".join("---" for _ in range(col_count)) + " |"
    lines.append(header)
    lines.append(separator)
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _is_list_style(style_name: str) -> tuple[bool, bool]:
    name = style_name.lower()
    if "list bullet" in name:
        return True, False
    if "list number" in name:
        return True, True
    return False, False


def convert(file_path: Path, trace_id: str = "") -> MarkdownResult:
    tid = trace_id or get_trace_id()
    with timed("docx_convert"):
        try:
            doc = Document(str(file_path))
        except FileNotFoundError as exc:
            raise ConvertError(
                f"File not found: {file_path}",
                code=ErrorCode.E_FILE_NOT_FOUND,
                trace_id=tid,
            ) from exc
        except Exception as exc:
            raise ConvertError(
                f"Failed to open docx: {file_path}: {exc}",
                trace_id=tid,
            ) from exc

        parts: list[str] = []
        numbered_counter = 0

        body = doc.element.body
        for child in body:
            tag = child.tag.split("}")[-1]

            if tag == "tbl":
                numbered_counter = 0
                table = next(
                    (t for t in doc.tables if t._element is child),
                    None,
                )
                if table is not None:
                    parts.append(_convert_table(table))
                continue

            if tag != "p":
                continue

            from docx.text.paragraph import Paragraph
            para = Paragraph(child, doc)
            text = para.text.strip()
            style_name = para.style.name if para.style else ""

            heading_prefix = _HEADING_MAP.get(style_name)
            if heading_prefix:
                numbered_counter = 0
                if text:
                    parts.append(f"{heading_prefix}{text}")
                continue

            is_list, is_numbered = _is_list_style(style_name)
            if is_list:
                if is_numbered:
                    numbered_counter += 1
                    parts.append(f"{numbered_counter}. {text}")
                else:
                    numbered_counter = 0
                    parts.append(f"- {text}")
                continue

            numbered_counter = 0
            if text:
                parts.append(text)

        content = "\n\n".join(parts) + "\n"
        logger.info("Converted docx file", extra={"path": str(file_path), "trace_id": tid})

        return MarkdownResult(
            content=content,
            source_path=str(file_path),
            source_format="docx",
            trace_id=tid,
        )
