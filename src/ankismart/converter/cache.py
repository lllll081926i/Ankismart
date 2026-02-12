from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult

logger = get_logger("converter.cache")


def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _resolve_app_dir() -> Path:
    env_app_dir = os.getenv("ANKISMART_APP_DIR", "").strip()
    if env_app_dir:
        return Path(env_app_dir).expanduser().resolve()
    return _resolve_project_root() / ".local" / "ankismart"


CACHE_DIR: Path = _resolve_app_dir() / "cache"


# ---------------------------------------------------------------------------
# File-hash based cache (path + mtime + size)
# ---------------------------------------------------------------------------

def get_file_hash(path: Path) -> str:
    """Generate a cache key based on path, mtime and size."""
    stat = path.stat()
    raw = f"{path.resolve()}|{stat.st_mtime}|{stat.st_size}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_by_hash(file_hash: str) -> MarkdownResult | None:
    """Retrieve cached conversion result by file hash."""
    md_path = CACHE_DIR / f"fh_{file_hash}.md"
    meta_path = CACHE_DIR / f"fh_{file_hash}.json"
    if not md_path.exists() or not meta_path.exists():
        return None
    try:
        content = md_path.read_text(encoding="utf-8")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return MarkdownResult(
            content=content,
            source_path=meta.get("source_path", ""),
            source_format=meta.get("source_format", ""),
            trace_id=meta.get("trace_id", ""),
        )
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read hash cache: {e}", extra={"file_hash": file_hash})
        return None


def save_cache_by_hash(file_hash: str, result: MarkdownResult) -> None:
    """Save conversion result keyed by file hash."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        md_path = CACHE_DIR / f"fh_{file_hash}.md"
        md_path.write_text(result.content, encoding="utf-8")
        meta_path = CACHE_DIR / f"fh_{file_hash}.json"
        meta_path.write_text(
            json.dumps({
                "source_path": result.source_path,
                "source_format": result.source_format,
                "trace_id": result.trace_id,
            }, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        logger.warning("Failed to save hash cache", extra={"file_hash": file_hash})


# ---------------------------------------------------------------------------
# Trace-id based cache (original)
# ---------------------------------------------------------------------------


def save_cache(result: MarkdownResult) -> None:
    """Save conversion result to local cache."""
    if not result.trace_id:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Save markdown content
        md_path = CACHE_DIR / f"{result.trace_id}.md"
        md_path.write_text(result.content, encoding="utf-8")
        # Save metadata
        meta_path = CACHE_DIR / f"{result.trace_id}.json"
        meta_path.write_text(
            json.dumps({
                "source_path": result.source_path,
                "source_format": result.source_format,
                "trace_id": result.trace_id,
            }, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        logger.warning("Failed to save cache", extra={"trace_id": result.trace_id})


def get_cached(trace_id: str) -> MarkdownResult | None:
    """Retrieve cached conversion result by trace_id."""
    md_path = CACHE_DIR / f"{trace_id}.md"
    meta_path = CACHE_DIR / f"{trace_id}.json"
    if not md_path.exists() or not meta_path.exists():
        return None
    try:
        content = md_path.read_text(encoding="utf-8")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return MarkdownResult(
            content=content,
            source_path=meta.get("source_path", ""),
            source_format=meta.get("source_format", ""),
            trace_id=trace_id,
        )
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read cache: {e}", extra={"trace_id": trace_id})
        return None


# ---------------------------------------------------------------------------
# Cache management utilities
# ---------------------------------------------------------------------------


def get_cache_size() -> float:
    """Calculate total cache directory size in MB.

    Returns:
        Total size of all cache files in megabytes.
    """
    if not CACHE_DIR.exists():
        return 0.0

    total_size = 0
    try:
        for file_path in CACHE_DIR.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except OSError:
        logger.warning("Failed to calculate cache size")
        return 0.0

    return total_size / (1024 * 1024)  # Convert bytes to MB


def get_cache_count() -> int:
    """Count the number of cache files.

    Returns:
        Number of cache files (both .md and .json files).
    """
    if not CACHE_DIR.exists():
        return 0

    try:
        return sum(1 for f in CACHE_DIR.rglob("*") if f.is_file())
    except OSError:
        logger.warning("Failed to count cache files")
        return 0


def clear_cache() -> bool:
    """Delete all cache files.

    Returns:
        True if cache was cleared successfully, False otherwise.
    """
    if not CACHE_DIR.exists():
        return True

    try:
        for file_path in CACHE_DIR.rglob("*"):
            if file_path.is_file():
                file_path.unlink()
        logger.info("Cache cleared successfully")
        return True
    except OSError as e:
        logger.error("Failed to clear cache", extra={"error": str(e)})
        return False


def get_cache_stats() -> dict[str, float | int]:
    """Get cache statistics.

    Returns:
        Dictionary containing cache statistics:
        - size_mb: Total cache size in megabytes
        - count: Number of cache files
        - size_gb: Total cache size in gigabytes (for display)
    """
    size_mb = get_cache_size()
    count = get_cache_count()

    return {
        "size_mb": size_mb,
        "size_gb": size_mb / 1024,
        "count": count,
    }
