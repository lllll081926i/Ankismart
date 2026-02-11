from __future__ import annotations

from pathlib import Path

import pytest

from ankismart.converter.converter import DocumentConverter
from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.models import MarkdownResult


def test_docx_parse_failure_raises_convert_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
