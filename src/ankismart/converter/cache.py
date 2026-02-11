from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult

logger = get_logger("converter.cache")

CACHE_DIR: Path = Path.home() / ".ankismart" / "cache"


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
    except Exception:
        logger.warning("Failed to read hash cache", extra={"file_hash": file_hash})
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
    except Exception:
        logger.warning("Failed to read cache", extra={"trace_id": trace_id})
        return None
