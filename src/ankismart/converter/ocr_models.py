from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.logging import get_logger

logger = get_logger("ocr_models")

_model_download_lock = threading.Lock()

OCR_MODEL_PRESETS: dict[str, dict[str, str]] = {
    "lite": {
        "label": "轻量",
        "det": "PP-OCRv5_mobile_det",
        "rec": "PP-OCRv5_mobile_rec",
        "recommended": "8GB 内存 / CPU / 无独显（轻薄本推荐）",
    },
    "standard": {
        "label": "标准",
        "det": "PP-OCRv5_server_det",
        "rec": "PP-OCRv5_mobile_rec",
        "recommended": "16GB 内存 / 4 核以上 CPU",
    },
    "accuracy": {
        "label": "高精度",
        "det": "PP-OCRv5_server_det",
        "rec": "PP-OCRv5_server_rec",
        "recommended": "16GB+ 内存，建议独显",
    },
}

OCR_MODEL_SOURCE_MAP: dict[str, str] = {
    "official": "huggingface",
    "cn_mirror": "modelscope",
}


def get_ocr_model_presets() -> dict[str, dict[str, str]]:
    return {key: value.copy() for key, value in OCR_MODEL_PRESETS.items()}


def resolve_ocr_model_pair(model_tier: str | None = None) -> tuple[str, str]:
    normalized_tier = (model_tier or "lite").strip().lower()
    preset = OCR_MODEL_PRESETS.get(normalized_tier, OCR_MODEL_PRESETS["lite"])
    return preset["det"], preset["rec"]


def resolve_ocr_model_source(model_source: str | None = None) -> str:
    normalized_source = (model_source or "official").strip().lower()
    return OCR_MODEL_SOURCE_MAP.get(normalized_source, OCR_MODEL_SOURCE_MAP["official"])


def configure_ocr_runtime(
    *,
    model_tier: str | None = None,
    model_source: str | None = None,
    reset_ocr_instance: bool = False,
    on_reset_runtime=None,
) -> dict[str, str]:
    if model_tier is not None:
        det_model, rec_model = resolve_ocr_model_pair(model_tier)
        os.environ["ANKISMART_OCR_DET_MODEL"] = det_model
        os.environ["ANKISMART_OCR_REC_MODEL"] = rec_model

    if model_source is not None:
        source_alias = resolve_ocr_model_source(model_source)
        os.environ["PADDLE_PDX_MODEL_SOURCE"] = source_alias

    if reset_ocr_instance and callable(on_reset_runtime):
        on_reset_runtime()

    return {
        "det_model": os.getenv("ANKISMART_OCR_DET_MODEL", OCR_MODEL_PRESETS["lite"]["det"]),
        "rec_model": os.getenv("ANKISMART_OCR_REC_MODEL", OCR_MODEL_PRESETS["lite"]["rec"]),
        "source_alias": os.getenv("PADDLE_PDX_MODEL_SOURCE", OCR_MODEL_SOURCE_MAP["official"]),
    }


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


def get_missing_ocr_models(
    *,
    model_tier: str | None = None,
    model_source: str | None = None,
    configure_runtime_fn=configure_ocr_runtime,
) -> list[str]:
    configure_runtime_fn(model_tier=model_tier, model_source=model_source)
    model_root = _resolve_model_root()
    det_model = os.getenv("ANKISMART_OCR_DET_MODEL", OCR_MODEL_PRESETS["lite"]["det"])
    rec_model = os.getenv("ANKISMART_OCR_REC_MODEL", OCR_MODEL_PRESETS["lite"]["rec"])

    missing: list[str] = []
    if _find_existing_model_dir(det_model, "ANKISMART_OCR_DET_MODEL_DIR", model_root) is None:
        missing.append(det_model)
    if _find_existing_model_dir(rec_model, "ANKISMART_OCR_REC_MODEL_DIR", model_root) is None:
        missing.append(rec_model)
    return missing


def download_missing_ocr_models(
    progress_callback=None,
    *,
    model_tier: str | None = None,
    model_source: str | None = None,
    configure_runtime_fn=configure_ocr_runtime,
    get_missing_fn=get_missing_ocr_models,
    on_models_ready=None,
) -> list[str]:
    configure_runtime_fn(model_tier=model_tier, model_source=model_source)
    missing = get_missing_fn(model_tier=model_tier, model_source=model_source)
    if not missing:
        return []

    if not _model_download_lock.acquire(blocking=False):
        raise ConvertError(
            "OCR model download already in progress",
            code=ErrorCode.E_OCR_FAILED,
        )

    from paddlex.inference.utils.official_models import official_models

    try:
        total = len(missing)
        for idx, model_name in enumerate(missing, start=1):
            logger.info(
                "Starting OCR model download",
                extra={
                    "event": "ocr.download.started",
                    "model_name": model_name,
                    "index": idx,
                    "total": total,
                },
            )
            if progress_callback is not None:
                progress_callback(
                    idx - 1,
                    total,
                    f"正在下载模型 {model_name}（{idx}/{total}）...",
                )

            official_models[model_name]
            logger.info(
                "OCR model download completed",
                extra={
                    "event": "ocr.download.completed",
                    "model_name": model_name,
                    "index": idx,
                    "total": total,
                },
            )
            if progress_callback is not None:
                progress_callback(idx, total, f"模型下载完成：{model_name}（{idx}/{total}）")

        remain = get_missing_fn(model_tier=model_tier, model_source=model_source)
        if remain:
            raise ConvertError(
                f"OCR model download failed: {', '.join(remain)}",
                code=ErrorCode.E_OCR_FAILED,
            )

        if callable(on_models_ready):
            on_models_ready()

        return list(missing)
    finally:
        _model_download_lock.release()
