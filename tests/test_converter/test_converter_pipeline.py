from __future__ import annotations

import builtins
from pathlib import Path
from types import SimpleNamespace

import pytest

from ankismart.converter.converter import DocumentConverter
from ankismart.converter.markitdown_converter import convert as markitdown_convert
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


def test_convert_pdf_cache_key_includes_runtime_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"%PDF")
    requested_keys: list[str] = []

    monkeypatch.setattr("ankismart.converter.converter.save_cache", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache_by_hash", lambda *_: None)
    monkeypatch.setattr("ankismart.converter.converter.detect_file_type", lambda _: "pdf")
    monkeypatch.setattr(
        "ankismart.converter.converter.get_cached_by_hash",
        lambda key: requested_keys.append(key) or None,
    )

    def fake_pdf_convert(_: Path, trace_id: str, **__) -> MarkdownResult:
        return MarkdownResult(content=trace_id, source_path="sample.pdf", source_format="pdf")

    monkeypatch.setattr(
        DocumentConverter, "_resolve_converter", staticmethod(lambda *_: fake_pdf_convert)
    )

    DocumentConverter(ocr_mode="local").convert(file_path)
    DocumentConverter(
        ocr_mode="cloud",
        ocr_cloud_provider="mineru",
        ocr_cloud_endpoint="https://mineru.net",
    ).convert(file_path)

    assert len(requested_keys) == 2
    assert requested_keys[0] != requested_keys[1]


def test_convert_pdf_cache_key_ignores_doc_backend_setting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"%PDF")
    requested_keys: list[str] = []

    monkeypatch.setattr("ankismart.converter.converter.save_cache", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache_by_hash", lambda *_: None)
    monkeypatch.setattr("ankismart.converter.converter.detect_file_type", lambda _: "pdf")
    monkeypatch.setattr(
        "ankismart.converter.converter.get_cached_by_hash",
        lambda key: requested_keys.append(key) or None,
    )

    def fake_pdf_convert(_: Path, trace_id: str, **__) -> MarkdownResult:
        return MarkdownResult(content=trace_id, source_path="sample.pdf", source_format="pdf")

    monkeypatch.setattr(
        DocumentConverter, "_resolve_converter", staticmethod(lambda *_: fake_pdf_convert)
    )

    DocumentConverter(doc_convert_backend="native").convert(file_path)
    DocumentConverter(doc_convert_backend="markitdown").convert(file_path)

    assert len(requested_keys) == 2
    assert requested_keys[0] == requested_keys[1]


def test_convert_docx_uses_native_converter_when_backend_is_native(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    file_path = tmp_path / "sample.docx"
    file_path.write_bytes(b"docx")

    monkeypatch.setattr("ankismart.converter.converter.get_cached_by_hash", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache_by_hash", lambda *_: None)
    monkeypatch.setattr("ankismart.converter.converter.detect_file_type", lambda _: "docx")

    called = {"native": 0}

    def fake_docx_convert(_: Path, __: str) -> MarkdownResult:
        called["native"] += 1
        return MarkdownResult(content="native", source_path="sample.docx", source_format="docx")

    converter_module = __import__("ankismart.converter.converter", fromlist=["_CONVERTERS"])
    monkeypatch.setitem(converter_module._CONVERTERS, "docx", fake_docx_convert)

    result = DocumentConverter(doc_convert_backend="native").convert(file_path)

    assert result.content == "native"
    assert called["native"] == 1


def test_convert_docx_uses_markitdown_converter_when_backend_is_markitdown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    file_path = tmp_path / "sample.docx"
    file_path.write_bytes(b"docx")

    monkeypatch.setattr("ankismart.converter.converter.get_cached_by_hash", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache_by_hash", lambda *_: None)
    monkeypatch.setattr("ankismart.converter.converter.detect_file_type", lambda _: "docx")

    called = {"markitdown": 0}

    def fake_markitdown_convert(_: Path, __: str) -> MarkdownResult:
        called["markitdown"] += 1
        return MarkdownResult(
            content="markitdown", source_path="sample.docx", source_format="docx"
        )

    monkeypatch.setattr(
        "ankismart.converter.converter._convert_with_markitdown",
        fake_markitdown_convert,
        raising=False,
    )

    result = DocumentConverter(doc_convert_backend="markitdown").convert(file_path)

    assert result.content == "markitdown"
    assert called["markitdown"] == 1


def test_convert_pdf_ignores_markitdown_backend_and_keeps_ocr_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"%PDF")

    monkeypatch.setattr("ankismart.converter.converter.get_cached_by_hash", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache", lambda _: None)
    monkeypatch.setattr("ankismart.converter.converter.save_cache_by_hash", lambda *_: None)
    monkeypatch.setattr("ankismart.converter.converter.detect_file_type", lambda _: "pdf")

    called = {"ocr": 0}

    def fake_pdf_convert(_: Path, __: str, **___) -> MarkdownResult:
        called["ocr"] += 1
        return MarkdownResult(content="ocr", source_path="sample.pdf", source_format="pdf")

    monkeypatch.setattr(
        DocumentConverter, "_resolve_converter", staticmethod(lambda *_: fake_pdf_convert)
    )

    result = DocumentConverter(doc_convert_backend="markitdown").convert(file_path)

    assert result.content == "ocr"
    assert called["ocr"] == 1


def test_markitdown_converter_maps_text_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    file_path = tmp_path / "sample.docx"
    file_path.write_bytes(b"docx")

    class _FakeMarkItDown:
        def convert(self, source):
            assert source == str(file_path)
            return SimpleNamespace(text_content="# Converted")

    original_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "markitdown":
            return SimpleNamespace(MarkItDown=_FakeMarkItDown)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    result = markitdown_convert(file_path, "trace-md")

    assert result.content == "# Converted"
    assert result.source_path == str(file_path)
    assert result.source_format == "docx"
    assert result.trace_id == "trace-md"


def test_markitdown_converter_raises_clear_error_when_dependency_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    file_path = tmp_path / "sample.docx"
    file_path.write_bytes(b"docx")
    original_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "markitdown":
            raise ImportError("missing dependency")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    with pytest.raises(ConvertError) as exc_info:
        markitdown_convert(file_path, "trace-md-missing")

    assert exc_info.value.code == ErrorCode.E_CONVERT_FAILED
    assert "MarkItDown backend is not available" in exc_info.value.message
