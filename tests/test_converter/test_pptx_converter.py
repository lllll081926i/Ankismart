"""Tests for ankismart.converter.pptx_converter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ankismart.converter.pptx_converter import (
    _extract_slide_text,
    _get_slide_title,
    convert,
)
from ankismart.core.errors import ConvertError, ErrorCode

# ---------------------------------------------------------------------------
# _get_slide_title
# ---------------------------------------------------------------------------


class TestGetSlideTitle:
    def test_returns_title_text(self) -> None:
        slide = MagicMock()
        slide.shapes.title.text = "My Title"
        assert _get_slide_title(slide) == "My Title"

    def test_returns_none_when_no_title_shape(self) -> None:
        slide = MagicMock()
        slide.shapes.title = None
        assert _get_slide_title(slide) is None

    def test_returns_none_when_title_empty(self) -> None:
        slide = MagicMock()
        slide.shapes.title.text = "   "
        assert _get_slide_title(slide) is None

    def test_strips_whitespace(self) -> None:
        slide = MagicMock()
        slide.shapes.title.text = "  Trimmed  "
        assert _get_slide_title(slide) == "Trimmed"


# ---------------------------------------------------------------------------
# _extract_slide_text
# ---------------------------------------------------------------------------


class TestExtractSlideText:
    def test_extracts_text_from_shapes(self) -> None:
        slide = MagicMock()
        shape1 = MagicMock()
        shape1.has_text_frame = True
        para1 = MagicMock()
        para1.text = "Hello"
        shape1.text_frame.paragraphs = [para1]

        shape2 = MagicMock()
        shape2.has_text_frame = True
        para2 = MagicMock()
        para2.text = "World"
        shape2.text_frame.paragraphs = [para2]

        slide.shapes = [shape1, shape2]
        result = _extract_slide_text(slide)
        assert result == ["Hello", "World"]

    def test_skips_shapes_without_text_frame(self) -> None:
        slide = MagicMock()
        shape = MagicMock()
        shape.has_text_frame = False
        slide.shapes = [shape]
        assert _extract_slide_text(slide) == []

    def test_skips_empty_paragraphs(self) -> None:
        slide = MagicMock()
        shape = MagicMock()
        shape.has_text_frame = True
        para1 = MagicMock()
        para1.text = "Content"
        para2 = MagicMock()
        para2.text = "   "
        shape.text_frame.paragraphs = [para1, para2]
        slide.shapes = [shape]
        assert _extract_slide_text(slide) == ["Content"]

    def test_empty_slide(self) -> None:
        slide = MagicMock()
        slide.shapes = []
        assert _extract_slide_text(slide) == []


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


class TestConvert:
    def test_convert_file_not_found(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.pptx"
        with patch(
            "ankismart.converter.pptx_converter.Presentation", side_effect=FileNotFoundError
        ):
            with pytest.raises(ConvertError) as exc_info:
                convert(f, trace_id="p1")
            assert exc_info.value.code == ErrorCode.E_FILE_NOT_FOUND

    def test_convert_generic_open_error(self, tmp_path: Path) -> None:
        f = tmp_path / "corrupt.pptx"
        f.write_bytes(b"not pptx")
        with patch(
            "ankismart.converter.pptx_converter.Presentation", side_effect=ValueError("bad")
        ):
            with pytest.raises(ConvertError) as exc_info:
                convert(f, trace_id="p2")
            assert "Failed to open pptx" in exc_info.value.message

    def test_convert_single_slide_with_title(self, tmp_path: Path) -> None:
        f = tmp_path / "test.pptx"
        f.write_bytes(b"fake")

        mock_prs = MagicMock()
        slide = MagicMock()
        slide.shapes.title.text = "Slide Title"

        shape = MagicMock()
        shape.has_text_frame = True
        para = MagicMock()
        para.text = "Body text"
        shape.text_frame.paragraphs = [para]
        slide.shapes.__iter__ = MagicMock(return_value=iter([shape]))

        mock_prs.slides = [slide]

        with patch("ankismart.converter.pptx_converter.Presentation", return_value=mock_prs):
            result = convert(f, trace_id="p3")

        assert result.source_format == "pptx"
        assert result.trace_id == "p3"
        assert "## Slide Title" in result.content
        assert "Body text" in result.content

    def test_convert_slide_without_title_uses_index(self, tmp_path: Path) -> None:
        f = tmp_path / "notitle.pptx"
        f.write_bytes(b"fake")

        mock_prs = MagicMock()
        slide = MagicMock()
        slide.shapes.title = None
        slide.shapes.__iter__ = MagicMock(return_value=iter([]))
        mock_prs.slides = [slide]

        with patch("ankismart.converter.pptx_converter.Presentation", return_value=mock_prs):
            result = convert(f, trace_id="p4")

        assert "## Slide 1" in result.content

    def test_convert_multiple_slides_separated_by_hr(self, tmp_path: Path) -> None:
        f = tmp_path / "multi.pptx"
        f.write_bytes(b"fake")

        mock_prs = MagicMock()
        slide1 = MagicMock()
        slide1.shapes.title.text = "First"
        slide1.shapes.__iter__ = MagicMock(return_value=iter([]))

        slide2 = MagicMock()
        slide2.shapes.title.text = "Second"
        slide2.shapes.__iter__ = MagicMock(return_value=iter([]))

        mock_prs.slides = [slide1, slide2]

        with patch("ankismart.converter.pptx_converter.Presentation", return_value=mock_prs):
            result = convert(f, trace_id="p5")

        assert "---" in result.content
        assert "## First" in result.content
        assert "## Second" in result.content

    def test_convert_slide_body_only_no_title(self, tmp_path: Path) -> None:
        f = tmp_path / "bodyonly.pptx"
        f.write_bytes(b"fake")

        mock_prs = MagicMock()
        slide = MagicMock()
        slide.shapes.title = None

        shape = MagicMock()
        shape.has_text_frame = True
        para = MagicMock()
        para.text = "Only body"
        shape.text_frame.paragraphs = [para]
        slide.shapes.__iter__ = MagicMock(return_value=iter([shape]))

        mock_prs.slides = [slide]

        with patch("ankismart.converter.pptx_converter.Presentation", return_value=mock_prs):
            result = convert(f, trace_id="p6")

        assert "## Slide 1" in result.content
        assert "Only body" in result.content

    def test_convert_empty_presentation(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.pptx"
        f.write_bytes(b"fake")

        mock_prs = MagicMock()
        mock_prs.slides = []

        with patch("ankismart.converter.pptx_converter.Presentation", return_value=mock_prs):
            result = convert(f, trace_id="p7")

        assert result.content == "\n"

    def test_convert_auto_trace_id(self, tmp_path: Path) -> None:
        f = tmp_path / "auto.pptx"
        f.write_bytes(b"fake")

        mock_prs = MagicMock()
        mock_prs.slides = []

        with patch("ankismart.converter.pptx_converter.Presentation", return_value=mock_prs):
            result = convert(f)

        assert result.trace_id != ""

    def test_convert_result_ends_with_newline(self, tmp_path: Path) -> None:
        f = tmp_path / "nl.pptx"
        f.write_bytes(b"fake")

        mock_prs = MagicMock()
        slide = MagicMock()
        slide.shapes.title.text = "T"
        slide.shapes.__iter__ = MagicMock(return_value=iter([]))
        mock_prs.slides = [slide]

        with patch("ankismart.converter.pptx_converter.Presentation", return_value=mock_prs):
            result = convert(f, trace_id="p8")

        assert result.content.endswith("\n")
