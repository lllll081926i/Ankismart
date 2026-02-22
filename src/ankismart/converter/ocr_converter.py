from __future__ import annotations

import gc
import os
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from ankismart.converter import ocr_device as _device
from ankismart.converter import ocr_models as _models
from ankismart.converter import ocr_pdf as _pdf
from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult
from ankismart.core.tracing import get_trace_id, timed

if TYPE_CHECKING:
    from paddleocr import PaddleOCR

logger = get_logger("ocr_converter")

# Keep this env setup in facade for compatibility with existing runtime behavior.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "1")

# Backward-compatible symbol exposed for tests/patches.
pdfium = _pdf.pdfium

# Re-export presets for existing callers.
OCR_MODEL_PRESETS = _models.OCR_MODEL_PRESETS
OCR_MODEL_SOURCE_MAP = _models.OCR_MODEL_SOURCE_MAP

# Test-friendly hook for monkeypatching OCR class without importing heavy deps.
PaddleOCR = None

# OCR engine singleton state
_ocr_instance: "PaddleOCR | None" = None
_ocr_lock = threading.Lock()
_mkldnn_fallback_applied = False
_gpu_fallback_applied = False
_ocr_runtime_device: str | None = None
_ocr_users_lock = threading.Lock()
_ocr_active_users = 0
_ocr_release_deferred = False

_PAGE_MARKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^[\s\-—–_·.。]*第\s*\d{1,4}\s*[页頁][\s\-—–_·.。]*$", re.IGNORECASE),
    re.compile(r"^[\s\-—–_·.。]*(?:page|p\.?)\s*\d{1,4}[\s\-—–_·.。]*$", re.IGNORECASE),
    re.compile(r"^[\s\-—–_·.。]*\d{1,4}\s*/\s*\d{1,4}[\s\-—–_·.。]*$"),
)


def _normalize_marker_candidate(line: str) -> str:
    candidate = " ".join(line.strip().split())
    return candidate.strip("()[]{}（）【】")


def _is_page_marker_line(line: str) -> bool:
    candidate = _normalize_marker_candidate(line)
    if not candidate:
        return False

    for pattern in _PAGE_MARKER_PATTERNS:
        if not pattern.fullmatch(candidate):
            continue
        if "/" in candidate:
            parts = [part.strip() for part in candidate.split("/", maxsplit=1)]
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                return False
            left = int(parts[0])
            right = int(parts[1])
            return 1 <= left <= right
        return True

    return False


def _remove_page_marker_lines(text: str) -> str:
    if not text:
        return text
    lines = [line for line in text.splitlines() if not _is_page_marker_line(line)]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _reset_ocr_runtime_state() -> None:
    release_ocr_runtime(reason="runtime_reset")


def release_ocr_runtime(*, reason: str = "manual", force_gc: bool = True) -> bool:
    """Release global OCR runtime instance and return whether an instance existed."""
    global _ocr_instance, _mkldnn_fallback_applied, _gpu_fallback_applied
    global _ocr_runtime_device, _ocr_release_deferred

    with _ocr_users_lock:
        if _ocr_active_users > 0:
            _ocr_release_deferred = True
            logger.info(
                "OCR runtime release deferred until active tasks finish",
                extra={
                    "event": "ocr.engine.release_deferred",
                    "reason": reason,
                    "active_users": _ocr_active_users,
                },
            )
            return False

    with _ocr_lock:
        instance = _ocr_instance
        _ocr_instance = None
        _mkldnn_fallback_applied = False
        _gpu_fallback_applied = False
        _ocr_runtime_device = None

    if instance is None:
        return False

    close_fn = getattr(instance, "close", None)
    if callable(close_fn):
        try:
            close_fn()
        except Exception as exc:
            logger.debug(f"Failed to close OCR runtime gracefully: {exc}")

    del instance

    if force_gc:
        gc.collect()

    logger.info(
        "Released PaddleOCR runtime",
        extra={"event": "ocr.engine.released", "reason": reason},
    )
    return True


def _mark_ocr_user_enter() -> None:
    global _ocr_active_users
    with _ocr_users_lock:
        _ocr_active_users += 1


def _mark_ocr_user_leave() -> None:
    global _ocr_active_users, _ocr_release_deferred
    should_release = False

    with _ocr_users_lock:
        _ocr_active_users = max(0, _ocr_active_users - 1)
        if _ocr_active_users == 0 and _ocr_release_deferred:
            _ocr_release_deferred = False
            should_release = True

    if should_release:
        release_ocr_runtime(reason="deferred_release")


@contextmanager
def _borrow_ocr():
    _mark_ocr_user_enter()
    try:
        yield _get_ocr()
    finally:
        _mark_ocr_user_leave()


def get_ocr_model_presets() -> dict[str, dict[str, str]]:
    return _models.get_ocr_model_presets()


def resolve_ocr_model_pair(model_tier: str | None = None) -> tuple[str, str]:
    return _models.resolve_ocr_model_pair(model_tier)


def resolve_ocr_model_source(model_source: str | None = None) -> str:
    return _models.resolve_ocr_model_source(model_source)


def configure_ocr_runtime(
    *,
    model_tier: str | None = None,
    model_source: str | None = None,
    reset_ocr_instance: bool = False,
) -> dict[str, str]:
    return _models.configure_ocr_runtime(
        model_tier=model_tier,
        model_source=model_source,
        reset_ocr_instance=reset_ocr_instance,
        on_reset_runtime=_reset_ocr_runtime_state,
    )


def _resolve_project_root() -> Path:
    return _models._resolve_project_root()


def _ensure_local_dependency_env() -> None:
    _models._ensure_local_dependency_env()


def _has_paddlex_model_files(model_dir: Path) -> bool:
    return _models._has_paddlex_model_files(model_dir)


def _model_candidates(model_name: str, env_var_name: str, model_root: Path) -> list[Path]:
    return _models._model_candidates(model_name, env_var_name, model_root)


def _find_existing_model_dir(model_name: str, env_var_name: str, model_root: Path) -> str | None:
    return _models._find_existing_model_dir(model_name, env_var_name, model_root)


def get_missing_ocr_models(
    *,
    model_tier: str | None = None,
    model_source: str | None = None,
) -> list[str]:
    return _models.get_missing_ocr_models(
        model_tier=model_tier,
        model_source=model_source,
        configure_runtime_fn=configure_ocr_runtime,
    )


def download_missing_ocr_models(
    progress_callback=None,
    *,
    model_tier: str | None = None,
    model_source: str | None = None,
) -> list[str]:
    return _models.download_missing_ocr_models(
        progress_callback=progress_callback,
        model_tier=model_tier,
        model_source=model_source,
        configure_runtime_fn=configure_ocr_runtime,
        get_missing_fn=get_missing_ocr_models,
        on_models_ready=_reset_ocr_runtime_state,
    )


def _choose_model_dir(
    model_name: str,
    env_var_name: str,
    model_root: Path,
    role: str,
) -> str | None:
    return _models._choose_model_dir(model_name, env_var_name, model_root, role)


def _resolve_model_root() -> Path:
    return _models._resolve_model_root()


def _cuda_devices_visible() -> bool:
    return _device._cuda_devices_visible()


def _has_nvidia_smi_gpu() -> bool:
    return _device._has_nvidia_smi_gpu()


def _perform_cuda_detection() -> bool:
    return _device._perform_cuda_detection()


def detect_cuda_environment(*, force_refresh: bool = False) -> bool:
    return _device.detect_cuda_environment(force_refresh=force_refresh)


def _cuda_available() -> bool:
    return _device._cuda_available()


def is_cuda_available(*, force_refresh: bool = False) -> bool:
    if _cuda_available():
        return True
    if _has_nvidia_smi_gpu():
        return True
    return detect_cuda_environment(force_refresh=force_refresh)


def preload_cuda_detection() -> None:
    _device.preload_cuda_detection()


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_env_int(name: str, default: int, *, min_value: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        value = default
    else:
        text = raw.strip()
        if not text:
            value = default
        else:
            try:
                value = int(text)
            except ValueError:
                logger.warning(
                    "Invalid integer environment variable, fallback to default",
                    extra={"env_var": name, "raw_value": raw, "default_value": default},
                )
                value = default

    if min_value is not None and value < min_value:
        logger.warning(
            "Integer environment variable below minimum, clamp to minimum",
            extra={
                "env_var": name,
                "resolved_value": value,
                "minimum": min_value,
            },
        )
        return min_value
    return value


def _resolve_ocr_device() -> str:
    requested = os.getenv("ANKISMART_OCR_DEVICE", "auto").strip().lower()
    has_cuda = _cuda_available()

    if requested in {"gpu", "gpu:0"}:
        if has_cuda:
            return "gpu:0"
        logger.warning("CUDA unavailable, fallback to CPU", extra={"requested_device": requested})
        return "cpu"

    if requested == "cpu":
        return "cpu"

    if requested not in {"auto", ""}:
        logger.warning(
            "Unknown ANKISMART_OCR_DEVICE, using auto mode",
            extra={"requested": requested},
        )

    return "gpu:0" if has_cuda else "cpu"


def _build_ocr_kwargs(device: str) -> dict[str, object]:
    det_model = os.getenv("ANKISMART_OCR_DET_MODEL", OCR_MODEL_PRESETS["lite"]["det"])
    rec_model = os.getenv("ANKISMART_OCR_REC_MODEL", OCR_MODEL_PRESETS["lite"]["rec"])
    model_root = _resolve_model_root()
    model_root.mkdir(parents=True, exist_ok=True)

    det_model_dir = _choose_model_dir(
        model_name=det_model,
        env_var_name="ANKISMART_OCR_DET_MODEL_DIR",
        model_root=model_root,
        role="det",
    )
    rec_model_dir = _choose_model_dir(
        model_name=rec_model,
        env_var_name="ANKISMART_OCR_REC_MODEL_DIR",
        model_root=model_root,
        role="rec",
    )

    kwargs: dict[str, object] = {
        "text_detection_model_name": det_model,
        "text_recognition_model_name": rec_model,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        "text_det_limit_type": os.getenv("ANKISMART_OCR_DET_LIMIT_TYPE", "max"),
        "text_det_limit_side_len": _get_env_int(
            "ANKISMART_OCR_DET_LIMIT_SIDE_LEN",
            640,
            min_value=1,
        ),
        "text_recognition_batch_size": _get_env_int(
            "ANKISMART_OCR_REC_BATCH_SIZE",
            1,
            min_value=1,
        ),
        "device": device,
    }

    if det_model_dir is not None:
        kwargs["text_detection_model_dir"] = det_model_dir
    if rec_model_dir is not None:
        kwargs["text_recognition_model_dir"] = rec_model_dir

    if device == "cpu":
        kwargs["enable_mkldnn"] = _get_env_bool("ANKISMART_OCR_CPU_MKLDNN", True)
        kwargs["cpu_threads"] = _get_env_int(
            "ANKISMART_OCR_CPU_THREADS",
            min(4, os.cpu_count() or 1),
            min_value=1,
        )

    return kwargs


def _is_onednn_unimplemented_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "onednn" in message
        and (
            "unimplemented" in message
            or "convertpirattribute2runtimeattribute" in message
        )
    )


def _is_gpu_runtime_error(exc: Exception) -> bool:
    message = str(exc).lower()
    gpu_markers = (
        "cuda",
        "cudnn",
        "cublas",
        "gpu",
        "out of memory",
        "memory alloc",
        "device-side assert",
        "driver",
    )
    return any(marker in message for marker in gpu_markers)


def _get_runtime_device_for_retry() -> str:
    runtime_device = _ocr_runtime_device
    if runtime_device:
        return runtime_device
    return _resolve_ocr_device()


def _should_retry_without_mkldnn(exc: Exception) -> bool:
    if _mkldnn_fallback_applied:
        return False
    if _get_runtime_device_for_retry() != "cpu":
        return False
    if not _get_env_bool("ANKISMART_OCR_CPU_MKLDNN", True):
        return False
    return _is_onednn_unimplemented_error(exc)


def _should_retry_with_cpu(exc: Exception) -> bool:
    runtime_device = _get_runtime_device_for_retry()
    if not runtime_device.startswith("gpu"):
        return False
    return _is_gpu_runtime_error(exc)


def _reload_ocr_on_cpu(*, reason: str, original_error: Exception | None = None) -> "PaddleOCR":
    global _ocr_instance, _gpu_fallback_applied, _ocr_runtime_device

    with _ocr_lock:
        kwargs = _build_ocr_kwargs("cpu")
        logger.warning(
            "Retrying OCR on CPU after CUDA runtime failure",
            extra={
                "reason": reason,
                "error": str(original_error) if original_error is not None else "",
                "det_model": kwargs.get("text_detection_model_name"),
                "rec_model": kwargs.get("text_recognition_model_name"),
            },
        )
        _ocr_instance = _load_paddle_ocr_class()(**kwargs)
        _gpu_fallback_applied = True
        _ocr_runtime_device = "cpu"
        return _ocr_instance


def _load_paddle_ocr_class():
    global PaddleOCR
    if PaddleOCR is None:
        from paddleocr import PaddleOCR as PaddleOCRClass

        PaddleOCR = PaddleOCRClass
    return PaddleOCR


def _reload_ocr_without_mkldnn() -> "PaddleOCR":
    global _ocr_instance, _mkldnn_fallback_applied, _ocr_runtime_device

    with _ocr_lock:
        os.environ["ANKISMART_OCR_CPU_MKLDNN"] = "0"
        kwargs = _build_ocr_kwargs("cpu")
        kwargs["enable_mkldnn"] = False
        logger.warning(
            "Retrying OCR with MKLDNN disabled due to oneDNN runtime error",
            extra={
                "det_model": kwargs.get("text_detection_model_name"),
                "rec_model": kwargs.get("text_recognition_model_name"),
            },
        )
        _ocr_instance = _load_paddle_ocr_class()(**kwargs)
        _mkldnn_fallback_applied = True
        _ocr_runtime_device = "cpu"
        return _ocr_instance


def _get_ocr() -> "PaddleOCR":
    global _ocr_instance, _gpu_fallback_applied, _ocr_runtime_device
    if _ocr_instance is not None:
        return _ocr_instance

    with _ocr_lock:
        if _ocr_instance is None:
            device = _resolve_ocr_device()
            if _gpu_fallback_applied and device.startswith("gpu"):
                device = "cpu"
            kwargs = _build_ocr_kwargs(device)
            logger.info(
                "Initializing PaddleOCR",
                extra={
                    "event": "ocr.engine.init",
                    "device": device,
                    "det_model": kwargs.get("text_detection_model_name"),
                    "det_model_dir": kwargs.get("text_detection_model_dir"),
                    "rec_model": kwargs.get("text_recognition_model_name"),
                    "rec_model_dir": kwargs.get("text_recognition_model_dir"),
                    "det_limit_side_len": kwargs.get("text_det_limit_side_len"),
                    "det_limit_type": kwargs.get("text_det_limit_type"),
                },
            )
            try:
                _ocr_instance = _load_paddle_ocr_class()(**kwargs)
                _ocr_runtime_device = device
            except Exception as exc:
                if not device.startswith("gpu"):
                    raise
                logger.warning(
                    "Failed to initialize PaddleOCR on CUDA, fallback to CPU runtime",
                    extra={"error": str(exc), "requested_device": device},
                )
                cpu_kwargs = _build_ocr_kwargs("cpu")
                _ocr_instance = _load_paddle_ocr_class()(**cpu_kwargs)
                _ocr_runtime_device = "cpu"
                _gpu_fallback_applied = True

    return _ocr_instance


def preload_ocr() -> None:
    thread = threading.Thread(target=_get_ocr, daemon=True)
    thread.start()


def _pdf_to_images(file_path: Path):
    return _pdf._pdf_to_images(file_path, pdfium_module=pdfium)


def _extract_pdf_text(file_path: Path) -> str | None:
    return _pdf._extract_pdf_text(file_path, pdfium_module=pdfium)


def _is_meaningful_text(content: str) -> bool:
    return _pdf._is_meaningful_text(content)


def _ocr_image(ocr: "PaddleOCR", image: Image.Image) -> str:
    img_array = np.array(image)
    try:
        result = ocr.predict(img_array, use_textline_orientation=False)
    except Exception as exc:
        if _should_retry_with_cpu(exc):
            logger.warning(
                "CUDA OCR error detected, fallback to CPU OCR runtime",
                extra={"error": str(exc)},
            )
            retry_ocr = _reload_ocr_on_cpu(reason="predict_failure", original_error=exc)
            result = retry_ocr.predict(img_array, use_textline_orientation=False)
        elif not _should_retry_without_mkldnn(exc):
            raise
        else:
            logger.warning(
                "oneDNN error detected, fallback to non-MKLDNN OCR runtime",
                extra={"error": str(exc)},
            )
            retry_ocr = _reload_ocr_without_mkldnn()
            result = retry_ocr.predict(img_array, use_textline_orientation=False)
    finally:
        del img_array

    if not result:
        return ""

    page_result = result[0]
    if not page_result:
        return ""

    rec_texts = None
    if hasattr(page_result, "get"):
        rec_texts = page_result.get("rec_texts")

    if not rec_texts and hasattr(page_result, "json"):
        try:
            rec_texts = page_result.json.get("res", {}).get("rec_texts")
        except (AttributeError, TypeError, KeyError) as exc:
            logger.warning(f"Failed to extract rec_texts from page_result.json: {exc}")
            rec_texts = None

    if not rec_texts:
        return ""

    lines: list[str] = []
    for text in rec_texts:
        line = str(text).strip()
        if not line:
            continue
        if _is_page_marker_line(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def convert(
    file_path: Path,
    trace_id: str = "",
    *,
    ocr_correction_fn=None,
    progress_callback=None,
) -> MarkdownResult:
    trace_id = trace_id or get_trace_id()

    if not file_path.exists():
        raise ConvertError(
            f"File not found: {file_path}",
            code=ErrorCode.E_FILE_NOT_FOUND,
            trace_id=trace_id,
        )

    if progress_callback is not None:
        progress_callback(0, 1, "检测 PDF 文字层...")

    extracted_text = _extract_pdf_text(file_path)
    if extracted_text is not None:
        extracted_text = _remove_page_marker_lines(extracted_text)
    if extracted_text:
        logger.info(
            "PDF has text layer, using direct extraction",
            extra={"trace_id": trace_id, "event": "ocr.pdf.text_layer"},
        )
        if progress_callback is not None:
            progress_callback(1, 1, "文字提取完成")
        return MarkdownResult(
            content=extracted_text,
            source_path=str(file_path),
            source_format="pdf",
            trace_id=trace_id,
        )

    logger.info(
        "PDF has no text layer, using OCR",
        extra={"trace_id": trace_id, "event": "ocr.pdf.fallback_to_image"},
    )

    with timed("ocr_convert"):
        try:
            total_pages = _pdf.count_pdf_pages(file_path, pdfium_module=pdfium)
        except (OSError, RuntimeError, ValueError) as exc:
            logger.warning(f"Failed to get PDF page count: {exc}", extra={"trace_id": trace_id})
            total_pages = 0

        sections: list[str] = []
        page_count = 0
        for i, image in enumerate(_pdf_to_images(file_path), 1):
            try:
                page_count += 1
                if progress_callback is not None:
                    progress_callback(i, total_pages, f"正在识别第 {i}/{total_pages} 页")

                with timed(f"ocr_page_{i}"):
                    with _borrow_ocr() as ocr:
                        page_text = _ocr_image(ocr, image)

                if page_text.strip():
                    sections.append(f"## Page {i}\n\n{page_text}")
                else:
                    logger.warning(
                        "Empty OCR result for page",
                        extra={"page": i, "trace_id": trace_id},
                    )
            finally:
                close_fn = getattr(image, "close", None)
                if callable(close_fn):
                    close_fn()

        if page_count == 0:
            raise ConvertError(
                "PDF contains no pages",
                code=ErrorCode.E_OCR_FAILED,
                trace_id=trace_id,
            )

        if progress_callback is not None:
            progress_callback(page_count, page_count, f"OCR 识别完成，共 {page_count} 页")

        content = "\n\n---\n\n".join(sections) if sections else ""
        if content.strip() and ocr_correction_fn is not None:
            try:
                with timed("ocr_correction"):
                    content = ocr_correction_fn(content)
            except (ValueError, RuntimeError, OSError) as exc:
                logger.warning(
                    f"OCR correction failed, using raw text: {exc}",
                    extra={"trace_id": trace_id},
                )
        content = _remove_page_marker_lines(content)

        if not content.strip():
            logger.warning(
                "OCR produced no text from PDF",
                extra={"trace_id": trace_id},
            )

    return MarkdownResult(
        content=content,
        source_path=str(file_path),
        source_format="pdf",
        trace_id=trace_id,
    )


def convert_image(
    file_path: Path,
    trace_id: str = "",
    *,
    ocr_correction_fn=None,
    progress_callback=None,
) -> MarkdownResult:
    trace_id = trace_id or get_trace_id()

    if not file_path.exists():
        raise ConvertError(
            f"File not found: {file_path}",
            code=ErrorCode.E_FILE_NOT_FOUND,
            trace_id=trace_id,
        )

    with timed("ocr_image_convert"):
        with Image.open(file_path) as image:
            with _borrow_ocr() as ocr:
                if progress_callback is not None:
                    progress_callback("OCR 正在识别图片...")
                text = _ocr_image(ocr, image)
                if progress_callback is not None:
                    progress_callback("OCR 图片识别完成")

        if text.strip() and ocr_correction_fn is not None:
            try:
                with timed("ocr_correction"):
                    text = ocr_correction_fn(text)
            except (ValueError, RuntimeError, OSError) as exc:
                logger.warning(
                    f"OCR correction failed, using raw text: {exc}",
                    extra={"trace_id": trace_id},
                )
        text = _remove_page_marker_lines(text)

    return MarkdownResult(
        content=text,
        source_path=str(file_path),
        source_format="image",
        trace_id=trace_id,
    )
