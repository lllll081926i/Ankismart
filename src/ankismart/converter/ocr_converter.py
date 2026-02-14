from __future__ import annotations

import os
import threading
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


def _reset_ocr_runtime_state() -> None:
    global _ocr_instance, _mkldnn_fallback_applied
    with _ocr_lock:
        _ocr_instance = None
        _mkldnn_fallback_applied = False


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
        "text_det_limit_side_len": int(os.getenv("ANKISMART_OCR_DET_LIMIT_SIDE_LEN", "640")),
        "text_recognition_batch_size": int(os.getenv("ANKISMART_OCR_REC_BATCH_SIZE", "1")),
        "device": device,
    }

    if det_model_dir is not None:
        kwargs["text_detection_model_dir"] = det_model_dir
    if rec_model_dir is not None:
        kwargs["text_recognition_model_dir"] = rec_model_dir

    if device == "cpu":
        kwargs["enable_mkldnn"] = _get_env_bool("ANKISMART_OCR_CPU_MKLDNN", True)
        kwargs["cpu_threads"] = int(
            os.getenv("ANKISMART_OCR_CPU_THREADS", str(min(4, os.cpu_count() or 1)))
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


def _should_retry_without_mkldnn(exc: Exception) -> bool:
    if _mkldnn_fallback_applied:
        return False
    if _resolve_ocr_device() != "cpu":
        return False
    if not _get_env_bool("ANKISMART_OCR_CPU_MKLDNN", True):
        return False
    return _is_onednn_unimplemented_error(exc)


def _load_paddle_ocr_class():
    global PaddleOCR
    if PaddleOCR is None:
        from paddleocr import PaddleOCR as paddle_ocr_cls

        PaddleOCR = paddle_ocr_cls
    return PaddleOCR


def _reload_ocr_without_mkldnn() -> "PaddleOCR":
    global _ocr_instance, _mkldnn_fallback_applied

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
        return _ocr_instance


def _get_ocr() -> "PaddleOCR":
    global _ocr_instance
    if _ocr_instance is not None:
        return _ocr_instance

    with _ocr_lock:
        if _ocr_instance is None:
            device = _resolve_ocr_device()
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
            _ocr_instance = _load_paddle_ocr_class()(**kwargs)

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
        if not _should_retry_without_mkldnn(exc):
            raise
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

    lines = [str(text).strip() for text in rec_texts if str(text).strip()]
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
            page_count += 1
            if progress_callback is not None:
                progress_callback(i, total_pages, f"正在识别第 {i}/{total_pages} 页")

            with timed(f"ocr_page_{i}"):
                ocr = _get_ocr()
                page_text = _ocr_image(ocr, image)

            if page_text.strip():
                sections.append(f"## Page {i}\n\n{page_text}")
            else:
                logger.warning(
                    "Empty OCR result for page",
                    extra={"page": i, "trace_id": trace_id},
                )

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
            ocr = _get_ocr()
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

    return MarkdownResult(
        content=text,
        source_path=str(file_path),
        source_format="image",
        trace_id=trace_id,
    )
