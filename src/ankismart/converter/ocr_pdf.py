from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.logging import get_logger

logger = get_logger("ocr_pdf")


def count_pdf_pages(file_path: Path, *, pdfium_module=pdfium) -> int:
    pdf = None
    try:
        pdf = pdfium_module.PdfDocument(str(file_path))
        return len(pdf)
    finally:
        if pdf is not None:
            close_pdf = getattr(pdf, "close", None)
            if callable(close_pdf):
                close_pdf()


def _pdf_to_images(file_path: Path, *, pdfium_module=pdfium) -> Iterator[Image.Image]:
    pdf = None
    try:
        pdf = pdfium_module.PdfDocument(str(file_path))
        render_scale = float(os.getenv("ANKISMART_OCR_PDF_RENDER_SCALE", str(300 / 72)))
        for i in range(len(pdf)):
            page = None
            bitmap = None
            try:
                page = pdf[i]
                bitmap = page.render(scale=render_scale)
                image = bitmap.to_pil().copy()
                yield image
            finally:
                if bitmap is not None:
                    close_bitmap = getattr(bitmap, "close", None)
                    if callable(close_bitmap):
                        close_bitmap()
                if page is not None:
                    close_page = getattr(page, "close", None)
                    if callable(close_page):
                        close_page()
    except ConvertError:
        raise
    except Exception as exc:
        raise ConvertError(
            f"Failed to convert PDF to images: {exc}",
            code=ErrorCode.E_OCR_FAILED,
        ) from exc
    finally:
        if pdf is not None:
            close_pdf = getattr(pdf, "close", None)
            if callable(close_pdf):
                close_pdf()


def _is_meaningful_text(content: str) -> bool:
    normalized = "".join(ch for ch in content if not ch.isspace())
    if len(normalized) < 10:
        return False
    alnum_count = sum(1 for ch in normalized if ch.isalnum())
    return alnum_count >= max(6, int(len(normalized) * 0.2))


def _extract_pdf_text(file_path: Path, *, pdfium_module=pdfium) -> str | None:
    pdf = None
    try:
        pdf = pdfium_module.PdfDocument(str(file_path))
        sections: list[str] = []
        for i in range(len(pdf)):
            page = None
            text_page = None
            page_text = ""
            try:
                page = pdf[i]
                text_page = page.get_textpage()
                page_text = text_page.get_text_range().strip()
            finally:
                if text_page is not None:
                    close_text_page = getattr(text_page, "close", None)
                    if callable(close_text_page):
                        close_text_page()
                if page is not None:
                    close_page = getattr(page, "close", None)
                    if callable(close_page):
                        close_page()

            if page_text:
                sections.append(f"## Page {i + 1}\n\n{page_text}")

        if sections:
            content = "\n\n---\n\n".join(sections)
            if _is_meaningful_text(content):
                return content
        return None
    except Exception as exc:
        logger.debug(f"Failed to extract PDF text layer: {exc}")
        return None
    finally:
        if pdf is not None:
            close_pdf = getattr(pdf, "close", None)
            if callable(close_pdf):
                close_pdf()
