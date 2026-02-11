from __future__ import annotations

from pathlib import Path

from ankismart.converter import (
    docx_converter,
    markdown_converter,
    ocr_converter,
    pptx_converter,
    text_converter,
)
from ankismart.converter.cache import (
    get_cached_by_hash,
    get_file_hash,
    save_cache,
    save_cache_by_hash,
)
from ankismart.converter.detector import detect_file_type
from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult
from ankismart.core.tracing import timed, trace_context

logger = get_logger("converter")

# Map file types to their converter functions
_CONVERTERS: dict[str, ...] = {
    "markdown": markdown_converter.convert,
    "text": text_converter.convert,
    "docx": docx_converter.convert,
    "pptx": pptx_converter.convert,
    "pdf": ocr_converter.convert,
    "image": ocr_converter.convert_image,
}


class DocumentConverter:
    """Main converter that dispatches to format-specific converters."""

    def convert(self, file_path: Path) -> MarkdownResult:
        with trace_context() as trace_id:
            with timed("convert_total"):
                # Check file-hash cache first
                file_hash = get_file_hash(file_path)
                cached = get_cached_by_hash(file_hash)
                if cached is not None:
                    logger.info(
                        "Cache hit (file hash)",
                        extra={"path": str(file_path), "trace_id": trace_id},
                    )
                    cached.trace_id = trace_id
                    return cached

                file_type = detect_file_type(file_path)
                logger.info(
                    "Starting conversion",
                    extra={"file_type": file_type, "path": str(file_path), "trace_id": trace_id},
                )

                converter_fn = _CONVERTERS.get(file_type)
                if converter_fn is None:
                    raise ConvertError(
                        f"No converter for type: {file_type}",
                        code=ErrorCode.E_FILE_TYPE_UNSUPPORTED,
                        trace_id=trace_id,
                    )

                try:
                    result = converter_fn(file_path, trace_id)
                except ConvertError:
                    raise
                except Exception as exc:
                    raise ConvertError(
                        f"Conversion failed: {exc}",
                        code=ErrorCode.E_CONVERT_FAILED,
                        trace_id=trace_id,
                    ) from exc

                save_cache(result)
                save_cache_by_hash(file_hash, result)
                logger.info(
                    "Conversion completed",
                    extra={"trace_id": trace_id, "content_length": len(result.content)},
                )
                return result
