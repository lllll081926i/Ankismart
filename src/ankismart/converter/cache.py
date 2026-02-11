from __future__ import annotations

import json
from pathlib import Path

from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult

logger = get_logger("converter.cache")

CACHE_DIR: Path = Path.home() / ".ankismart" / "cache"


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
