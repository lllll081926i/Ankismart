from __future__ import annotations

import os
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from paddleocr import PaddleOCR
from PIL import Image

from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult
from ankismart.core.tracing import get_trace_id, timed

logger = get_logger("ocr_converter")

# Ensure PaddleX hoster check is disabled as early as possible
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "1")

# Lazy-initialized singleton to avoid repeated model loading
_ocr_instance: PaddleOCR | None = None
_ocr_lock = threading.Lock()
_mkldnn_fallback_applied = False


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _ensure_local_dependency_env() -> None:
    project_root = _resolve_project_root()
    local_root = Path(
        os.getenv("ANKISMART_LOCAL_DIR", str(project_root / ".local"))
    ).expanduser().resolve()
    model_root = Path(
        os.getenv("ANKISMART_OCR_MODEL_DIR", str(project_root / "model"))
    ).expanduser().resolve()

    defaults = {
        "ANKISMART_LOCAL_DIR": str(local_root),
        "ANKISMART_OCR_MODEL_DIR": str(model_root),
        "PADDLE_HOME": str(local_root / "paddle"),
        "PADDLE_PDX_CACHE_HOME": str(model_root),
        "XDG_CACHE_HOME": str(local_root / "cache"),
        "HF_HOME": str(local_root / "hf"),
        "TMPDIR": str(local_root / "tmp"),
        "TMP": str(local_root / "tmp"),
        "TEMP": str(local_root / "tmp"),
    }

    for key, value in defaults.items():
        os.environ.setdefault(key, value)

    Path(os.environ["ANKISMART_LOCAL_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["ANKISMART_OCR_MODEL_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["PADDLE_HOME"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["HF_HOME"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["TEMP"]).mkdir(parents=True, exist_ok=True)


def _has_paddlex_model_files(model_dir: Path) -> bool:
    return (model_dir / "inference.yml").exists()


def _model_candidates(model_name: str, env_var_name: str, model_root: Path) -> list[Path]:
    explicit_value = os.getenv(env_var_name, "").strip()
    explicit_dir = Path(explicit_value).expanduser() if explicit_value else None
    cache_root = Path(os.getenv("PADDLE_PDX_CACHE_HOME", str(model_root))).expanduser()
    default_dir = model_root / model_name
    official_cache_dir = cache_root / "official_models" / model_name

    candidates: list[Path] = []
    if explicit_dir is not None:
        candidates.append(explicit_dir)
    candidates.extend([default_dir, official_cache_dir])
    return candidates


def _find_existing_model_dir(model_name: str, env_var_name: str, model_root: Path) -> str | None:
    for candidate in _model_candidates(model_name, env_var_name, model_root):
        if _has_paddlex_model_files(candidate):
            return str(candidate)
    return None


def get_missing_ocr_models() -> list[str]:
    model_root = _resolve_model_root()
    det_model = os.getenv("ANKISMART_OCR_DET_MODEL", "PP-OCRv5_mobile_det")
    rec_model = os.getenv("ANKISMART_OCR_REC_MODEL", "PP-OCRv5_mobile_rec")

    missing: list[str] = []
    if _find_existing_model_dir(det_model, "ANKISMART_OCR_DET_MODEL_DIR", model_root) is None:
        missing.append(det_model)
    if _find_existing_model_dir(rec_model, "ANKISMART_OCR_REC_MODEL_DIR", model_root) is None:
        missing.append(rec_model)
    return missing


def download_missing_ocr_models(progress_callback=None) -> list[str]:
    model_root = _resolve_model_root()
    missing = get_missing_ocr_models()
    if not missing:
        return []

    from paddlex.inference.utils.official_models import official_models

    total = len(missing)
    for idx, model_name in enumerate(missing, start=1):
        if progress_callback is not None:
            progress_callback(idx - 1, total, f"正在下载模型 {model_name}...")
        official_models[model_name]
        if progress_callback is not None:
            progress_callback(idx, total, f"模型下载完成：{model_name}")

    remain = get_missing_ocr_models()
    if remain:
        raise ConvertError(
            f"OCR model download failed: {', '.join(remain)}",
            code=ErrorCode.E_OCR_FAILED,
        )

    # Reset OCR singleton to ensure new local model paths are picked up.
    global _ocr_instance
    with _ocr_lock:
        _ocr_instance = None

    # Keep returned list deterministic and aligned with input order.
    return list(missing)


def _choose_model_dir(
    model_name: str,
    env_var_name: str,
    model_root: Path,
    role: str,
) -> str | None:
    explicit_value = os.getenv(env_var_name, "").strip()
    explicit_dir = Path(explicit_value).expanduser() if explicit_value else None
    candidates = _model_candidates(model_name, env_var_name, model_root)
    existing_dir = _find_existing_model_dir(model_name, env_var_name, model_root)
    if existing_dir is not None:
        return existing_dir

    if explicit_dir is not None:
        logger.warning(
            "Configured local OCR model dir is invalid, fallback to auto download",
            extra={
                "role": role,
                "env_var": env_var_name,
                "model_dir": str(explicit_dir),
            },
        )

    logger.info(
        "Local OCR model not found, fallback to auto download",
        extra={
            "role": role,
            "model_name": model_name,
            "searched_dirs": [str(path) for path in candidates],
        },
    )
    return None


def _resolve_model_root() -> Path:
    _ensure_local_dependency_env()
    env_model_root = os.getenv("ANKISMART_OCR_MODEL_DIR", "").strip()
    if env_model_root:
        return Path(env_model_root).expanduser().resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "model"

    return Path(__file__).resolve().parents[3] / "model"


def _cuda_available() -> bool:
    try:
        import paddle

        if not paddle.device.is_compiled_with_cuda():
            return False
        try:
            return paddle.device.cuda.device_count() > 0
        except Exception:
            return True
    except Exception:
        return False


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
    det_model = os.getenv("ANKISMART_OCR_DET_MODEL", "PP-OCRv5_mobile_det")
    rec_model = os.getenv("ANKISMART_OCR_REC_MODEL", "PP-OCRv5_mobile_rec")
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

    det_limit_side_len = int(os.getenv("ANKISMART_OCR_DET_LIMIT_SIDE_LEN", "640"))
    det_limit_type = os.getenv("ANKISMART_OCR_DET_LIMIT_TYPE", "max")
    rec_batch_size = int(os.getenv("ANKISMART_OCR_REC_BATCH_SIZE", "1"))

    kwargs: dict[str, object] = {
        "text_detection_model_name": det_model,
        "text_recognition_model_name": rec_model,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        "text_det_limit_type": det_limit_type,
        "text_det_limit_side_len": det_limit_side_len,
        "text_recognition_batch_size": rec_batch_size,
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


def _reload_ocr_without_mkldnn() -> PaddleOCR:
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
        _ocr_instance = PaddleOCR(**kwargs)
        _mkldnn_fallback_applied = True
        return _ocr_instance


def _get_ocr() -> PaddleOCR:
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
                    "device": device,
                    "det_model": kwargs.get("text_detection_model_name"),
                    "det_model_dir": kwargs.get("text_detection_model_dir"),
                    "rec_model": kwargs.get("text_recognition_model_name"),
                    "rec_model_dir": kwargs.get("text_recognition_model_dir"),
                    "det_limit_side_len": kwargs.get("text_det_limit_side_len"),
                    "det_limit_type": kwargs.get("text_det_limit_type"),
                },
            )
            _ocr_instance = PaddleOCR(**kwargs)
    return _ocr_instance


def preload_ocr() -> None:
    """Pre-warm the OCR singleton in a background thread (non-blocking)."""
    thread = threading.Thread(target=_get_ocr, daemon=True)
    thread.start()


def _pdf_to_images(file_path: Path) -> Iterator[Image.Image]:
    """Yield PDF pages as PIL images one at a time (streaming)."""
    try:
        pdf = pdfium.PdfDocument(str(file_path))
        for i in range(len(pdf)):
            page = pdf[i]
            # Render at 300 DPI for good OCR quality
            bitmap = page.render(scale=300 / 72)
            pil_image = bitmap.to_pil()
            yield pil_image
    except ConvertError:
        raise
    except Exception as exc:
        raise ConvertError(
            f"Failed to convert PDF to images: {exc}",
            code=ErrorCode.E_OCR_FAILED,
        ) from exc


def _ocr_image(ocr: PaddleOCR, image: Image.Image) -> str:
    """Run OCR on a single image and return extracted text."""
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
    del img_array  # release numpy array memory

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
        except Exception:
            rec_texts = None

    if not rec_texts:
        return ""

    lines = [str(text).strip() for text in rec_texts if str(text).strip()]
    return "\n".join(lines)


def convert(file_path: Path, trace_id: str = "", *, ocr_correction_fn=None) -> MarkdownResult:
    """Convert a PDF file to Markdown via OCR."""
    trace_id = trace_id or get_trace_id()

    if not file_path.exists():
        raise ConvertError(
            f"File not found: {file_path}",
            code=ErrorCode.E_FILE_NOT_FOUND,
            trace_id=trace_id,
        )

    with timed("ocr_convert"):
        sections: list[str] = []
        page_count = 0
        for i, image in enumerate(_pdf_to_images(file_path), 1):
            page_count += 1
            with timed(f"ocr_page_{i}"):
                ocr = _get_ocr()
                page_text = _ocr_image(ocr, image)
            del image  # release PIL image memory

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

        content = "\n\n---\n\n".join(sections) if sections else ""

        # Optional LLM-based OCR correction
        if content.strip() and ocr_correction_fn is not None:
            try:
                with timed("ocr_correction"):
                    content = ocr_correction_fn(content)
            except Exception:
                logger.warning(
                    "OCR correction failed, using raw text",
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


def convert_image(file_path: Path, trace_id: str = "", *, ocr_correction_fn=None) -> MarkdownResult:
    """Convert a single image file to Markdown via OCR."""
    trace_id = trace_id or get_trace_id()

    if not file_path.exists():
        raise ConvertError(
            f"File not found: {file_path}",
            code=ErrorCode.E_FILE_NOT_FOUND,
            trace_id=trace_id,
        )

    with timed("ocr_image_convert"):
        image = Image.open(file_path)
        ocr = _get_ocr()
        text = _ocr_image(ocr, image)

        # Optional LLM-based OCR correction
        if text.strip() and ocr_correction_fn is not None:
            try:
                with timed("ocr_correction"):
                    text = ocr_correction_fn(text)
            except Exception:
                logger.warning(
                    "OCR correction failed, using raw text",
                    extra={"trace_id": trace_id},
                )

    return MarkdownResult(
        content=text,
        source_path=str(file_path),
        source_format="image",
        trace_id=trace_id,
    )
