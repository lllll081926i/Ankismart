from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ankismart.converter import (
    docx_converter,
    markdown_converter,
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
from ankismart.core.tracing import metrics, timed, trace_context

logger = get_logger("converter")

# Map file types to their converter functions
_CONVERTERS: dict[str, Callable[[Path, str], MarkdownResult]] = {
    "markdown": markdown_converter.convert,
    "text": text_converter.convert,
    "docx": docx_converter.convert,
    "pptx": pptx_converter.convert,
}


def _update_cache_hit_ratio_metric() -> None:
    total = metrics.cache_hits + metrics.cache_misses
    ratio = float(metrics.cache_hits / total) if total else 0.0
    metrics.set_gauge("convert_cache_hit_ratio", ratio)


class DocumentConverter:
    """Main converter that dispatches to format-specific converters."""

    def __init__(self, *, ocr_correction_fn: Callable[[str], str] | None = None) -> None:
        self._ocr_correction_fn = ocr_correction_fn

    @staticmethod
    def _resolve_converter(file_type: str, trace_id: str) -> Callable:
        """Resolve converter function lazily.

        OCR converter is imported on demand so packaging can exclude OCR runtime.
        """
        converter_fn = _CONVERTERS.get(file_type)
        if converter_fn is not None:
            return converter_fn

        if file_type in {"pdf", "image"}:
            try:
                from ankismart.converter import ocr_converter
            except Exception as exc:
                raise ConvertError(
                    "OCR runtime is not available in this package",
                    code=ErrorCode.E_FILE_TYPE_UNSUPPORTED,
                    trace_id=trace_id,
                ) from exc

            return ocr_converter.convert if file_type == "pdf" else ocr_converter.convert_image

        raise ConvertError(
            f"No converter for type: {file_type}",
            code=ErrorCode.E_FILE_TYPE_UNSUPPORTED,
            trace_id=trace_id,
        )

    def convert(self, file_path: Path, *, progress_callback: Callable[..., None] | None = None) -> MarkdownResult:
        with trace_context() as trace_id:
            with timed("convert_total"):
                metrics.increment("convert_requests_total")
                if not file_path.exists():
                    metrics.increment(
                        "convert_failures_total",
                        labels={"code": ErrorCode.E_FILE_NOT_FOUND.value},
                    )
                    raise ConvertError(
                        f"File not found: {file_path}",
                        code=ErrorCode.E_FILE_NOT_FOUND,
                        trace_id=trace_id,
                    )

                # Check file-hash cache first
                file_hash = get_file_hash(file_path)
                cached = get_cached_by_hash(file_hash)
                if cached is not None:
                    metrics.record_cache_hit()
                    metrics.increment("convert_cache_hits_total")
                    metrics.increment("convert_success_total")
                    _update_cache_hit_ratio_metric()
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

                converter_fn = self._resolve_converter(file_type, trace_id)

                try:
                    if file_type in ("pdf", "image"):
                        safe_progress_callback = None
                        if progress_callback is not None:

                            def safe_progress_callback(*args) -> None:
                                try:
                                    progress_callback(*args)
                                except TypeError:
                                    # Backward compatibility for callbacks that only accept message text.
                                    if len(args) == 3:
                                        try:
                                            progress_callback(str(args[2]))
                                            return
                                        except Exception as cb_exc:
                                            logger.warning(
                                                "Progress callback failed",
                                                extra={"error": str(cb_exc), "trace_id": trace_id},
                                            )
                                            return
                                    logger.warning(
                                        "Progress callback failed",
                                        extra={
                                            "error": "callback signature mismatch",
                                            "trace_id": trace_id,
                                        },
                                    )
                                except Exception as cb_exc:
                                    logger.warning(
                                        "Progress callback failed",
                                        extra={"error": str(cb_exc), "trace_id": trace_id},
                                    )

                        if self._ocr_correction_fn is not None:
                            result = converter_fn(
                                file_path,
                                trace_id,
                                ocr_correction_fn=self._ocr_correction_fn,
                                progress_callback=safe_progress_callback,
                            )
                        else:
                            result = converter_fn(
                                file_path,
                                trace_id,
                                progress_callback=safe_progress_callback,
                            )
                    else:
                        result = converter_fn(file_path, trace_id)
                except ConvertError as exc:
                    metrics.increment(
                        "convert_failures_total",
                        labels={"code": exc.code.value},
                    )
                    raise
                except Exception as exc:
                    metrics.increment(
                        "convert_failures_total",
                        labels={"code": ErrorCode.E_CONVERT_FAILED.value},
                    )
                    raise ConvertError(
                        f"Conversion failed: {exc}",
                        code=ErrorCode.E_CONVERT_FAILED,
                        trace_id=trace_id,
                    ) from exc

                save_cache(result)
                save_cache_by_hash(file_hash, result)
                metrics.record_cache_miss()
                metrics.increment("convert_cache_misses_total")
                metrics.increment("convert_success_total")
                _update_cache_hit_ratio_metric()
                logger.info(
                    "Conversion completed",
                    extra={"trace_id": trace_id, "content_length": len(result.content)},
                )
                return result
