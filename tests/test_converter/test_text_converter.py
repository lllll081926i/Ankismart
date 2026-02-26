"""Tests for ankismart.converter.text_converter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ankismart.converter.text_converter import (
    _detect_encoding,
    _is_heading,
    _structure_as_markdown,
    convert,
)
from ankismart.core.errors import ConvertError, ErrorCode

# ---------------------------------------------------------------------------
# _detect_encoding
# ---------------------------------------------------------------------------


class TestDetectEncoding:
    def test_utf8_bytes(self) -> None:
        raw = "Hello world".encode("utf-8")
        enc = _detect_encoding(raw)
        assert enc.lower().replace("-", "") in ("utf8", "ascii")

    def test_gb2312_bytes(self) -> None:
        raw = "你好世界，这是一段中文文本用于测试编码检测".encode("gb2312")
        enc = _detect_encoding(raw)
        assert enc is not None
        # Should be decodable with the detected encoding
        raw.decode(enc)

    def test_empty_bytes_returns_utf8(self) -> None:
        enc = _detect_encoding(b"")
        assert enc.lower().replace("-", "") in ("utf8", "ascii")

    def test_chardet_returns_none_encoding(self) -> None:
        with patch(
            "ankismart.converter.text_converter.chardet.detect", return_value={"encoding": None}
        ):
            assert _detect_encoding(b"abc") == "utf-8"


# ---------------------------------------------------------------------------
# _is_heading
# ---------------------------------------------------------------------------


class TestIsHeading:
    def test_all_uppercase_is_heading(self) -> None:
        assert _is_heading("INTRODUCTION", 50.0) is True

    def test_single_char_uppercase_still_heading_by_short_line_heuristic(self) -> None:
        # "A" is short (len=1 < 50*0.4=20) and doesn't end with ".",
        # so short-line heuristic triggers.
        assert _is_heading("A", 50.0) is True

    def test_single_char_not_heading_when_avg_zero(self) -> None:
        # With avg_length=0 the short-line heuristic is disabled, and isupper needs len>1
        assert _is_heading("A", 0.0) is False

    def test_short_line_without_period_is_heading(self) -> None:
        # len("Title") = 5, avg_length=50, 5 < 50*0.4=20 and no period
        assert _is_heading("Title", 50.0) is True

    def test_short_line_with_period_not_heading(self) -> None:
        assert _is_heading("Title.", 50.0) is False

    def test_long_line_not_heading(self) -> None:
        long_line = "This is a very long line that should not be detected as a heading at all."
        assert _is_heading(long_line, 50.0) is False

    def test_empty_line_not_heading(self) -> None:
        assert _is_heading("", 50.0) is False

    def test_whitespace_only_not_heading(self) -> None:
        assert _is_heading("   ", 50.0) is False

    def test_avg_length_zero(self) -> None:
        # avg_length <= 0 means the short-line heuristic is skipped
        assert _is_heading("Title", 0.0) is False

    def test_uppercase_short(self) -> None:
        # "AB" is uppercase and len > 1
        assert _is_heading("AB", 100.0) is True


# ---------------------------------------------------------------------------
# _structure_as_markdown
# ---------------------------------------------------------------------------


class TestStructureAsMarkdown:
    def test_single_paragraph(self) -> None:
        text = "This is a normal paragraph with enough text to not be a heading."
        result = _structure_as_markdown(text)
        assert result.endswith("\n")
        assert "##" not in result

    def test_heading_detection(self) -> None:
        text = (
            "INTRODUCTION\n\nThis is a long paragraph that provides enough average "
            "length for heading detection to work properly."
        )
        result = _structure_as_markdown(text)
        assert "## INTRODUCTION" in result

    def test_multiple_paragraphs(self) -> None:
        text = "First paragraph content here.\n\nSecond paragraph content here."
        result = _structure_as_markdown(text)
        assert "First paragraph content here." in result
        assert "Second paragraph content here." in result

    def test_empty_paragraphs_skipped(self) -> None:
        text = "Hello\n\n\n\nWorld"
        result = _structure_as_markdown(text)
        # Empty paragraphs between should be skipped
        assert result.strip() != ""

    def test_multiline_paragraph_joined(self) -> None:
        text = "Line one of a paragraph.\nLine two of the same paragraph."
        result = _structure_as_markdown(text)
        assert "Line one of a paragraph. Line two of the same paragraph." in result

    def test_empty_input(self) -> None:
        result = _structure_as_markdown("")
        assert result == "\n"


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


class TestConvert:
    def test_convert_utf8_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Hello world\n\nThis is a test file with enough content.", encoding="utf-8")
        result = convert(f, trace_id="t1")
        assert result.source_format == "text"
        assert result.trace_id == "t1"
        assert result.source_path == str(f)
        assert "Hello world" in result.content

    def test_convert_file_not_found(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.txt"
        with pytest.raises(ConvertError) as exc_info:
            convert(f, trace_id="t2")
        assert exc_info.value.code == ErrorCode.E_FILE_NOT_FOUND

    def test_convert_os_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.txt"
        f.write_text("x")
        with patch.object(Path, "read_bytes", side_effect=OSError("disk error")):
            with pytest.raises(ConvertError) as exc_info:
                convert(f, trace_id="t3")
            assert "Cannot read file" in exc_info.value.message

    def test_convert_encoding_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad_enc.txt"
        f.write_bytes(b"\xff\xfe")
        with patch("ankismart.converter.text_converter._detect_encoding", return_value="utf-8"):
            with pytest.raises(ConvertError) as exc_info:
                convert(f, trace_id="t4")
            assert "Encoding detection failed" in exc_info.value.message

    def test_convert_lookup_error(self, tmp_path: Path) -> None:
        f = tmp_path / "lookup.txt"
        f.write_bytes(b"hello")
        with patch(
            "ankismart.converter.text_converter._detect_encoding",
            return_value="nonexistent-encoding",
        ):
            with pytest.raises(ConvertError):
                convert(f, trace_id="t5")

    def test_convert_generates_trace_id_when_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "auto_trace.txt"
        f.write_text("content", encoding="utf-8")
        result = convert(f)
        assert result.trace_id != ""

    def test_convert_result_ends_with_newline(self, tmp_path: Path) -> None:
        f = tmp_path / "newline.txt"
        f.write_text("Some text content", encoding="utf-8")
        result = convert(f, trace_id="t6")
        assert result.content.endswith("\n")
