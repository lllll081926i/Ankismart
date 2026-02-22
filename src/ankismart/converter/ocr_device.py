from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

from ankismart.core.logging import get_logger

logger = get_logger("ocr_device")

_cuda_detection_cache: bool | None = None
_cuda_detection_cache_ts = 0.0
_cuda_detection_cache_key: tuple[str | None, str | None, str | None] | None = None
_cuda_detection_lock = threading.Lock()


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    text = raw.strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        logger.warning(
            "Invalid integer environment variable, fallback to default",
            extra={"env_var": name, "raw_value": raw, "default_value": default},
        )
        return default


def _cuda_devices_visible() -> bool:
    visible_devices = os.getenv("CUDA_VISIBLE_DEVICES")
    if visible_devices is None:
        return True

    normalized = visible_devices.strip().lower()
    return normalized not in {"", "-1", "none", "void"}


def _has_nvidia_smi_gpu() -> bool:
    if not _cuda_devices_visible():
        return False

    executables = ["nvidia-smi"]
    system_root = os.getenv("SystemRoot", "C:/Windows")
    executables.append(str(Path(system_root) / "System32" / "nvidia-smi.exe"))
    program_files = os.getenv("ProgramW6432") or os.getenv("ProgramFiles")
    if program_files:
        executables.append(
            str(Path(program_files) / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe")
        )

    commands: list[list[str]] = []
    for executable in executables:
        commands.append([executable, "--query-gpu=index", "--format=csv,noheader"])
        commands.append([executable, "-L"])

    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            continue

        if result.returncode == 0 and result.stdout.strip():
            return True

    return False


def _perform_cuda_detection() -> bool:
    if not _cuda_devices_visible():
        return False

    if _has_nvidia_smi_gpu():
        return True

    cuda_path = os.getenv("CUDA_PATH") or os.getenv("CUDA_HOME")
    if cuda_path:
        try:
            return Path(cuda_path).expanduser().exists()
        except OSError:
            return False

    return False


def detect_cuda_environment(*, force_refresh: bool = False) -> bool:
    global _cuda_detection_cache, _cuda_detection_cache_ts, _cuda_detection_cache_key

    cache_ttl = _get_env_int("ANKISMART_CUDA_CACHE_TTL_SECONDS", 300)
    now = time.time()
    cache_key = (
        os.getenv("CUDA_VISIBLE_DEVICES"),
        os.getenv("CUDA_PATH"),
        os.getenv("CUDA_HOME"),
    )

    if (
        not force_refresh
        and _cuda_detection_cache is not None
        and _cuda_detection_cache_key == cache_key
        and (now - _cuda_detection_cache_ts) <= max(0, cache_ttl)
    ):
        return _cuda_detection_cache

    with _cuda_detection_lock:
        now = time.time()
        if (
            not force_refresh
            and _cuda_detection_cache is not None
            and _cuda_detection_cache_key == cache_key
            and (now - _cuda_detection_cache_ts) <= max(0, cache_ttl)
        ):
            return _cuda_detection_cache

        result = _perform_cuda_detection()
        _cuda_detection_cache = result
        _cuda_detection_cache_ts = now
        _cuda_detection_cache_key = cache_key
        return result


def _cuda_available() -> bool:
    try:
        import paddle

        if not paddle.device.is_compiled_with_cuda():
            return False
        try:
            return paddle.device.cuda.device_count() > 0
        except (RuntimeError, AttributeError):
            return True
    except (ImportError, ModuleNotFoundError):
        return False


def is_cuda_available(*, force_refresh: bool = False) -> bool:
    if _cuda_available():
        return True
    if _has_nvidia_smi_gpu():
        return True
    return detect_cuda_environment(force_refresh=force_refresh)


def preload_cuda_detection() -> None:
    thread = threading.Thread(target=detect_cuda_environment, daemon=True)
    thread.start()
