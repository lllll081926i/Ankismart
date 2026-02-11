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


def _get_list_level(paragraph) -> int:
    """Extract the indentation level (ilvl) from a paragraph's numbering properties."""
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        p_pr = paragraph._element.find(f"{ns}pPr")
        if p_pr is None:
            return 0
        num_pr = p_pr.find(f"{ns}numPr")
        if num_pr is None:
            return 0
        ilvl = num_pr.find(f"{ns}ilvl")
        if ilvl is not None:
            return int(ilvl.get(f"{ns}val", "0"))
    except (ValueError, TypeError, AttributeError):
        pass
    return 0


def _render_paragraph_runs(paragraph) -> str:
    """Render paragraph runs with bold/italic Markdown formatting."""
    parts: list[str] = []
    for run in paragraph.runs:
        text = run.text
        if not text:
            continue
        is_bold = run.bold
        is_italic = run.italic
        if is_bold and is_italic:
            parts.append(f"***{text}***")
        elif is_bold:
            parts.append(f"**{text}**")
        elif is_italic:
            parts.append(f"*{text}*")
        else:
            parts.append(text)
    # Fall back to plain text if runs are empty (e.g. field codes)
    return "".join(parts) or paragraph.text or ""


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
        numbered_counters: dict[int, int] = {}  # level -> counter

        body = doc.element.body
        for child in body:
            tag = child.tag.split("}")[-1]

            if tag == "tbl":
                numbered_counters.clear()
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
            style_name = para.style.name if para.style else ""

            heading_prefix = _HEADING_MAP.get(style_name)
            if heading_prefix:
                numbered_counters.clear()
                text = para.text.strip()
                if text:
                    parts.append(f"{heading_prefix}{text}")
                continue

            is_list, is_numbered = _is_list_style(style_name)
            if is_list:
                level = _get_list_level(para)
                indent = "  " * level
                text = _render_paragraph_runs(para).strip()
                if is_numbered:
                    numbered_counters[level] = numbered_counters.get(level, 0) + 1
                    # Reset deeper level counters
                    for k in list(numbered_counters):
                        if k > level:
                            del numbered_counters[k]
                    parts.append(f"{indent}{numbered_counters[level]}. {text}")
                else:
                    parts.append(f"{indent}- {text}")
                continue

            numbered_counters.clear()
            text = _render_paragraph_runs(para).strip()
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
