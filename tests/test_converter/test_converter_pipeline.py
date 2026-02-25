from __future__ import annotations

from pathlib import Path

import pytest

from ankismart.converter.converter import DocumentConverter
from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.models import MarkdownResult
from ankismart.core.tracing import metrics


def test_docx_parse_failure_raises_convert_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    converter = DocumentConverter()
    file_path = tmp_path / "sample.docx"
    file_path.write_bytes(b"docx")

    monkeypatch.setattr(
        "ankismart.converter.converter.detect_file_type",
        lambda _: "docx",
    )

    def fake_docx_convert(_: Path, __: str) -> MarkdownResult:
        raise RuntimeError("docx parser failure")

    converter_module = __import__("ankismart.converter.converter", fromlist=["_CONVERTERS"])
    monkeypatch.setitem(converter_module._CONVERTERS, "docx", fake_docx_convert)

    with pytest.raises(ConvertError) as exc_info:
        converter.convert(file_path)

    assert exc_info.value.code == ErrorCode.E_CONVERT_FAILED
    assert "docx parser failure" in exc_info.value.message


def test_convert_doc_is_not_supported(tmp_path: Path) -> None:
    file_path = tmp_path / "legacy.doc"
    file_path.write_bytes(b"doc")

    with pytest.raises(ConvertError) as exc_info:
        DocumentConverter().convert(file_path)

    assert exc_info.value.code == ErrorCode.E_FILE_TYPE_UNSUPPORTED


def test_convert_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    metrics.reset()
    file_path = tmp_path / "missing.md"

    with pytest.raises(ConvertError) as exc_info:
        DocumentConverter().convert(file_path)

    assert exc_info.value.code == ErrorCode.E_FILE_NOT_FOUND
    assert (
        metrics.get_counter(
            "convert_failures_total", labels={"code": ErrorCode.E_FILE_NOT_FOUND.value}
        )
        == 1.0
    )


def test_convert_pdf_progress_callback_accepts_three_args(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"%PDF")

    monkeypatch.setattr("ankismart.converter.converter.get_cached_by_hash", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache_by_hash", lambda *_: None)
    monkeypatch.setattr("ankismart.converter.converter.detect_file_type", lambda _: "pdf")

    def fake_pdf_convert(_: Path, __: str, *, progress_callback=None, **___) -> MarkdownResult:
        if progress_callback is not None:
            progress_callback(1, 2, "正在识别第 1/2 页")
        return MarkdownResult(content="ok", source_path="sample.pdf", source_format="pdf")

    monkeypatch.setattr(
        DocumentConverter, "_resolve_converter", staticmethod(lambda *_: fake_pdf_convert)
    )

    progress_events: list[tuple[int, int, str]] = []
    converter = DocumentConverter()
    result = converter.convert(
        file_path, progress_callback=lambda c, t, m: progress_events.append((c, t, m))
    )

    assert result.content == "ok"
    assert progress_events == [(1, 2, "正在识别第 1/2 页")]


def test_convert_pdf_progress_callback_falls_back_to_message_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"%PDF")

    monkeypatch.setattr("ankismart.converter.converter.get_cached_by_hash", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache_by_hash", lambda *_: None)
    monkeypatch.setattr("ankismart.converter.converter.detect_file_type", lambda _: "pdf")

    def fake_pdf_convert(_: Path, __: str, *, progress_callback=None, **___) -> MarkdownResult:
        if progress_callback is not None:
            progress_callback(2, 3, "OCR 识别完成，共 3 页")
        return MarkdownResult(content="ok", source_path="sample.pdf", source_format="pdf")

    monkeypatch.setattr(
        DocumentConverter, "_resolve_converter", staticmethod(lambda *_: fake_pdf_convert)
    )

    progress_messages: list[str] = []
    converter = DocumentConverter()
    result = converter.convert(
        file_path, progress_callback=lambda msg: progress_messages.append(msg)
    )

    assert result.content == "ok"
    assert progress_messages == ["OCR 识别完成，共 3 页"]
