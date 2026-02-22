"""Tests for ankismart.converter.docx_converter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ankismart.converter.docx_converter import (
    _convert_table,
    _is_list_style,
    _render_paragraph_runs,
    convert,
)
from ankismart.core.errors import ConvertError, ErrorCode

# ---------------------------------------------------------------------------
# _is_list_style
# ---------------------------------------------------------------------------

class TestIsListStyle:
    def test_bullet_list(self) -> None:
        is_list, is_numbered = _is_list_style("List Bullet")
        assert is_list is True
        assert is_numbered is False

    def test_numbered_list(self) -> None:
        is_list, is_numbered = _is_list_style("List Number")
        assert is_list is True
        assert is_numbered is True

    def test_normal_style(self) -> None:
        is_list, is_numbered = _is_list_style("Normal")
        assert is_list is False
        assert is_numbered is False

    def test_case_insensitive_bullet(self) -> None:
        is_list, is_numbered = _is_list_style("list bullet 2")
        assert is_list is True
        assert is_numbered is False

    def test_case_insensitive_number(self) -> None:
        is_list, is_numbered = _is_list_style("LIST NUMBER 3")
        assert is_list is True
        assert is_numbered is True

    def test_heading_style(self) -> None:
        is_list, _ = _is_list_style("Heading 1")
        assert is_list is False


# ---------------------------------------------------------------------------
# _convert_table
# ---------------------------------------------------------------------------

class TestConvertTable:
    def _make_table(self, rows_data: list[list[str]]) -> MagicMock:
        table = MagicMock()
        rows = []
        for row_data in rows_data:
            row = MagicMock()
            cells = []
            for text in row_data:
                cell = MagicMock()
                cell.text = text
                cells.append(cell)
            row.cells = cells
            rows.append(row)
        table.rows = rows
        return table

    def test_simple_table(self) -> None:
        table = self._make_table([["Name", "Age"], ["Alice", "30"]])
        result = _convert_table(table)
        assert "| Name | Age |" in result
        assert "| --- | --- |" in result
        assert "| Alice | 30 |" in result

    def test_empty_table(self) -> None:
        table = self._make_table([])
        result = _convert_table(table)
        assert result == ""

    def test_pipe_escaped(self) -> None:
        table = self._make_table([["A|B", "C"], ["D", "E"]])
        result = _convert_table(table)
        assert "A\\|B" in result

    def test_uneven_rows_padded(self) -> None:
        table = self._make_table([["A", "B", "C"], ["D"]])
        result = _convert_table(table)
        lines = result.strip().split("\n")
        # Header has 3 columns
        assert lines[0].count("|") == 4  # | A | B | C |
        # Data row should also have 3 columns (padded)
        assert lines[2].count("|") == 4

    def test_single_row_table(self) -> None:
        table = self._make_table([["Header1", "Header2"]])
        result = _convert_table(table)
        assert "| Header1 | Header2 |" in result
        assert "| --- | --- |" in result


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------

class TestConvert:
    def _make_paragraph_element(self, text: str, style_name: str, tag: str = "p") -> MagicMock:
        elem = MagicMock()
        elem.tag = f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{tag}"
        elem._text = text
        elem._style_name = style_name
        return elem

    def test_convert_file_not_found(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.docx"
        with patch("ankismart.converter.docx_converter.Document", side_effect=FileNotFoundError("not found")):
            with pytest.raises(ConvertError) as exc_info:
                convert(f, trace_id="d1")
            assert exc_info.value.code == ErrorCode.E_FILE_NOT_FOUND

    def test_convert_generic_open_error(self, tmp_path: Path) -> None:
        f = tmp_path / "corrupt.docx"
        f.write_bytes(b"not a docx")
        with patch("ankismart.converter.docx_converter.Document", side_effect=ValueError("bad format")):
            with pytest.raises(ConvertError) as exc_info:
                convert(f, trace_id="d2")
            assert "Failed to open docx" in exc_info.value.message

    def test_convert_simple_paragraphs(self, tmp_path: Path) -> None:
        """Test conversion with mocked Document containing simple paragraphs."""
        f = tmp_path / "test.docx"
        f.write_bytes(b"fake")

        mock_doc = MagicMock()

        # Create paragraph elements
        p1_elem = MagicMock()
        p1_elem.tag = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
        p2_elem = MagicMock()
        p2_elem.tag = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"

        mock_doc.element.body.__iter__ = MagicMock(return_value=iter([p1_elem, p2_elem]))
        mock_doc.tables = []

        # We need to mock the Paragraph class
        mock_para1 = MagicMock()
        mock_para1.text = "Hello World"
        mock_para1.style.name = "Normal"

        mock_para2 = MagicMock()
        mock_para2.text = "Second paragraph"
        mock_para2.style.name = "Normal"

        para_calls = iter([mock_para1, mock_para2])

        with patch("ankismart.converter.docx_converter.Document", return_value=mock_doc):
            with patch("docx.text.paragraph.Paragraph", side_effect=lambda el, doc: next(para_calls)):
                result = convert(f, trace_id="d3")

        assert result.source_format == "docx"
        assert result.trace_id == "d3"
        assert "Hello World" in result.content
        assert "Second paragraph" in result.content

    def test_convert_heading_paragraph(self, tmp_path: Path) -> None:
        f = tmp_path / "heading.docx"
        f.write_bytes(b"fake")

        mock_doc = MagicMock()
        p_elem = MagicMock()
        p_elem.tag = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
        mock_doc.element.body.__iter__ = MagicMock(return_value=iter([p_elem]))
        mock_doc.tables = []

        mock_para = MagicMock()
        mock_para.text = "Chapter One"
        mock_para.style.name = "Heading 1"

        with patch("ankismart.converter.docx_converter.Document", return_value=mock_doc):
            with patch("docx.text.paragraph.Paragraph", return_value=mock_para):
                result = convert(f, trace_id="d4")

        assert "# Chapter One" in result.content

    def test_convert_bullet_list(self, tmp_path: Path) -> None:
        f = tmp_path / "bullets.docx"
        f.write_bytes(b"fake")

        mock_doc = MagicMock()
        p_elem = MagicMock()
        p_elem.tag = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
        mock_doc.element.body.__iter__ = MagicMock(return_value=iter([p_elem]))
        mock_doc.tables = []

        mock_para = MagicMock()
        mock_para.text = "Bullet item"
        mock_para.style.name = "List Bullet"

        with patch("ankismart.converter.docx_converter.Document", return_value=mock_doc):
            with patch("docx.text.paragraph.Paragraph", return_value=mock_para):
                result = convert(f, trace_id="d5")

        assert "- Bullet item" in result.content

    def test_convert_numbered_list(self, tmp_path: Path) -> None:
        f = tmp_path / "numbered.docx"
        f.write_bytes(b"fake")

        mock_doc = MagicMock()
        p1 = MagicMock()
        p1.tag = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
        p2 = MagicMock()
        p2.tag = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
        mock_doc.element.body.__iter__ = MagicMock(return_value=iter([p1, p2]))
        mock_doc.tables = []

        mock_para1 = MagicMock()
        mock_para1.text = "First"
        mock_para1.style.name = "List Number"

        mock_para2 = MagicMock()
        mock_para2.text = "Second"
        mock_para2.style.name = "List Number"

        paras = iter([mock_para1, mock_para2])

        with patch("ankismart.converter.docx_converter.Document", return_value=mock_doc):
            with patch("docx.text.paragraph.Paragraph", side_effect=lambda el, doc: next(paras)):
                result = convert(f, trace_id="d6")

        assert "1. First" in result.content
        assert "2. Second" in result.content

    def test_convert_table_element(self, tmp_path: Path) -> None:
        f = tmp_path / "table.docx"
        f.write_bytes(b"fake")

        mock_doc = MagicMock()
        tbl_elem = MagicMock()
        tbl_elem.tag = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl"

        mock_doc.element.body.__iter__ = MagicMock(return_value=iter([tbl_elem]))

        mock_table = MagicMock()
        mock_table._element = tbl_elem
        cell1 = MagicMock()
        cell1.text = "H1"
        cell2 = MagicMock()
        cell2.text = "H2"
        row1 = MagicMock()
        row1.cells = [cell1, cell2]
        cell3 = MagicMock()
        cell3.text = "V1"
        cell4 = MagicMock()
        cell4.text = "V2"
        row2 = MagicMock()
        row2.cells = [cell3, cell4]
        mock_table.rows = [row1, row2]
        mock_doc.tables = [mock_table]

        with patch("ankismart.converter.docx_converter.Document", return_value=mock_doc):
            result = convert(f, trace_id="d7")

        assert "| H1 | H2 |" in result.content
        assert "| V1 | V2 |" in result.content

    def test_convert_auto_trace_id(self, tmp_path: Path) -> None:
        f = tmp_path / "auto.docx"
        f.write_bytes(b"fake")

        mock_doc = MagicMock()
        mock_doc.element.body.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.tables = []

        with patch("ankismart.converter.docx_converter.Document", return_value=mock_doc):
            result = convert(f)

        assert result.trace_id != ""

    def test_convert_empty_paragraph_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "empty_para.docx"
        f.write_bytes(b"fake")

        mock_doc = MagicMock()
        p_elem = MagicMock()
        p_elem.tag = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
        mock_doc.element.body.__iter__ = MagicMock(return_value=iter([p_elem]))
        mock_doc.tables = []

        mock_para = MagicMock()
        mock_para.text = "   "  # whitespace only
        mock_para.style.name = "Normal"

        with patch("ankismart.converter.docx_converter.Document", return_value=mock_doc):
            with patch("docx.text.paragraph.Paragraph", return_value=mock_para):
                result = convert(f, trace_id="d8")

        # Empty paragraph should not appear in output
        assert result.content.strip() == ""


class TestRenderParagraphRuns:
    def test_keeps_latex_runs_without_markdown_emphasis(self) -> None:
        paragraph = MagicMock()
        paragraph.text = r"$\frac{a_b}{c}$"
        run = MagicMock()
        run.text = r"$\frac{a_b}{c}$"
        run.bold = True
        run.italic = True
        paragraph.runs = [run]

        rendered = _render_paragraph_runs(paragraph)
        assert rendered == r"$\frac{a_b}{c}$"
