"""File type detection for AnkiSmart converter pipeline."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from ankismart.core.errors import ConvertError, ErrorCode

SUPPORTED_TYPES: set[str] = {
    "markdown",
    "text",
    "docx",
    "pptx",
    "pdf",
    "image",
}

_MIME_MAP: dict[str, str] = {
    "text/markdown": "markdown",
    "text/plain": "text",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/pdf": "pdf",
}

_EXT_MAP: dict[str, str] = {
    ".md": "markdown",
    ".txt": "text",
    ".docx": "docx",
    ".pptx": "pptx",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".bmp": "image",
    ".tiff": "image",
    ".webp": "image",
}


def detect_file_type(file_path: Path) -> str:
    """Detect the standardized file type for *file_path*.

    Uses ``mimetypes`` as the primary check and falls back to the file
    extension when the MIME type is not conclusive.

    Returns one of the strings in :data:`SUPPORTED_TYPES`.

    Raises:
        ConvertError: If the file does not exist or its type is unsupported.
    """
    if not file_path.exists():
        raise ConvertError(
            f"File not found: {file_path}",
            code=ErrorCode.E_FILE_NOT_FOUND,
        )

    # Primary: MIME type lookup
    mime_type, _ = mimetypes.guess_type(str(file_path))

    if mime_type is not None:
        if mime_type in _MIME_MAP:
            return _MIME_MAP[mime_type]
        if mime_type.startswith("image/"):
            return "image"

    # Fallback: extension lookup
    suffix = file_path.suffix.lower()
    if suffix in _EXT_MAP:
        return _EXT_MAP[suffix]

    raise ConvertError(
        f"Unsupported file type: {file_path.suffix or '(no extension)'}",
        code=ErrorCode.E_FILE_TYPE_UNSUPPORTED,
    )
