"""Tests for ankismart.converter.markdown_converter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ankismart.converter.markdown_converter import (
    _detect_encoding,
    _normalize,
    convert,
)
from ankismart.core.errors import ConvertError, ErrorCode

# ---------------------------------------------------------------------------
# _detect_encoding
# ---------------------------------------------------------------------------


class TestDetectEncoding:
    def test_utf8_detected(self) -> None:
        raw = "# Hello".encode("utf-8")
        enc = _detect_encoding(raw)
        assert enc.lower().replace("-", "") in ("utf8", "ascii")

    def test_none_encoding_falls_back_to_utf8(self) -> None:
        with patch(
            "ankismart.converter.markdown_converter.chardet.detect", return_value={"encoding": None}
        ):
            assert _detect_encoding(b"data") == "utf-8"


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_preserves_trailing_spaces(self) -> None:
        text = "line1   \nline2  \n"
        result = _normalize(text)
        assert result == "line1   \nline2  \n"

    def test_preserves_content(self) -> None:
        text = "# Title\n\nParagraph"
        result = _normalize(text)
        assert "# Title" in result
        assert "Paragraph" in result

    def test_ends_with_newline(self) -> None:
        result = _normalize("hello")
        assert result.endswith("\n")

    def test_empty_string(self) -> None:
        result = _normalize("")
        assert result == "\n"

    def test_multiple_lines(self) -> None:
        text = "a  \nb  \nc  "
        result = _normalize(text)
        assert result == "a  \nb  \nc  \n"

    def test_normalize_crlf_to_lf(self) -> None:
        text = "a\r\nb\r\n"
        result = _normalize(text)
        assert result == "a\nb\n"


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


class TestConvert:
    def test_convert_simple_markdown(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("# Hello\n\nWorld\n", encoding="utf-8")
        result = convert(f, trace_id="md1")
        assert result.source_format == "markdown"
        assert result.trace_id == "md1"
        assert result.source_path == str(f)
        assert "# Hello" in result.content
        assert "World" in result.content

    def test_convert_preserves_trailing_whitespace(self, tmp_path: Path) -> None:
        f = tmp_path / "spaces.md"
        f.write_text("line1   \nline2   \n", encoding="utf-8")
        result = convert(f, trace_id="md2")
        assert "line1   \n" in result.content
        assert "line2   \n" in result.content

    def test_convert_file_not_found(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.md"
        with pytest.raises(ConvertError) as exc_info:
            convert(f, trace_id="md3")
        assert exc_info.value.code == ErrorCode.E_FILE_NOT_FOUND

    def test_convert_os_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.md"
        f.write_text("x")
        with patch.object(Path, "read_bytes", side_effect=OSError("permission denied")):
            with pytest.raises(ConvertError) as exc_info:
                convert(f, trace_id="md4")
            assert "Cannot read file" in exc_info.value.message

    def test_convert_encoding_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad_enc.md"
        f.write_bytes(b"\xff\xfe")
        with patch("ankismart.converter.markdown_converter._detect_encoding", return_value="utf-8"):
            with pytest.raises(ConvertError) as exc_info:
                convert(f, trace_id="md5")
            assert "Encoding detection failed" in exc_info.value.message

    def test_convert_lookup_error(self, tmp_path: Path) -> None:
        f = tmp_path / "lookup.md"
        f.write_bytes(b"hello")
        with patch(
            "ankismart.converter.markdown_converter._detect_encoding", return_value="bogus-codec"
        ):
            with pytest.raises(ConvertError):
                convert(f, trace_id="md6")

    def test_convert_auto_trace_id(self, tmp_path: Path) -> None:
        f = tmp_path / "auto.md"
        f.write_text("content", encoding="utf-8")
        result = convert(f)
        assert result.trace_id != ""

    def test_convert_result_ends_with_newline(self, tmp_path: Path) -> None:
        f = tmp_path / "nl.md"
        f.write_text("no trailing newline", encoding="utf-8")
        result = convert(f, trace_id="md7")
        assert result.content.endswith("\n")
