from __future__ import annotations

from pathlib import Path

import pytest

from ankismart.converter.detector import detect_file_type
from ankismart.core.errors import ConvertError, ErrorCode


def test_detect_docx_type(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.docx"
    file_path.write_bytes(b"docx")

    assert detect_file_type(file_path) == "docx"


def test_detect_pptx_type(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.pptx"
    file_path.write_bytes(b"pptx")

    assert detect_file_type(file_path) == "pptx"


def test_detect_unsupported_type_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.xyz"
    file_path.write_bytes(b"unknown")

    with pytest.raises(ConvertError) as exc_info:
        detect_file_type(file_path)

    assert exc_info.value.code == ErrorCode.E_FILE_TYPE_UNSUPPORTED
