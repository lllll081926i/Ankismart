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

    det_model_dir = Path(
        os.getenv("ANKISMART_OCR_DET_MODEL_DIR", str(model_root / det_model))
    ).expanduser()
    rec_model_dir = Path(
        os.getenv("ANKISMART_OCR_REC_MODEL_DIR", str(model_root / rec_model))
    ).expanduser()

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

    if _has_paddlex_model_files(det_model_dir):
        kwargs["text_detection_model_dir"] = str(det_model_dir)
    else:
        logger.info(
            "Local detection model not found, fallback to auto download",
            extra={"det_model_dir": str(det_model_dir)},
        )

    if _has_paddlex_model_files(rec_model_dir):
        kwargs["text_recognition_model_dir"] = str(rec_model_dir)
    else:
        logger.info(
            "Local recognition model not found, fallback to auto download",
            extra={"rec_model_dir": str(rec_model_dir)},
        )

    if device == "cpu":
        kwargs["enable_mkldnn"] = _get_env_bool("ANKISMART_OCR_CPU_MKLDNN", True)
        kwargs["cpu_threads"] = int(
            os.getenv("ANKISMART_OCR_CPU_THREADS", str(min(4, os.cpu_count() or 1)))
        )

    return kwargs


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
    result = ocr.predict(img_array, use_textline_orientation=False)
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
        ocr = _get_ocr()

        sections: list[str] = []
        page_count = 0
        for i, image in enumerate(_pdf_to_images(file_path), 1):
            page_count += 1
            with timed(f"ocr_page_{i}"):
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
