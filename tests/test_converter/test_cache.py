"""Tests for ankismart.converter.cache."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from ankismart.converter.cache import (
    clear_cache,
    get_cache_count,
    get_cache_size,
    get_cache_stats,
    get_cached,
    get_cached_by_hash,
    get_file_hash,
    save_cache,
    save_cache_by_hash,
)
from ankismart.core.models import MarkdownResult

# ---------------------------------------------------------------------------
# save_cache
# ---------------------------------------------------------------------------

class TestSaveCache:
    def test_saves_md_and_json(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        result = MarkdownResult(
            content="# Hello",
            source_path="/tmp/test.md",
            source_format="markdown",
            trace_id="abc123",
        )
        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            save_cache(result)

        md_path = cache_dir / "abc123.md"
        meta_path = cache_dir / "abc123.json"
        assert md_path.exists()
        assert meta_path.exists()
        assert md_path.read_text(encoding="utf-8") == "# Hello"

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["source_path"] == "/tmp/test.md"
        assert meta["source_format"] == "markdown"
        assert meta["trace_id"] == "abc123"

    def test_skips_when_no_trace_id(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        result = MarkdownResult(
            content="data",
            source_path="/tmp/x.md",
            source_format="markdown",
            trace_id="",
        )
        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            save_cache(result)

        assert not cache_dir.exists()

    def test_handles_os_error_gracefully(self, tmp_path: Path) -> None:
        result = MarkdownResult(
            content="data",
            source_path="/tmp/x.md",
            source_format="markdown",
            trace_id="err1",
        )
        with patch("ankismart.converter.cache.CACHE_DIR", tmp_path / "cache"):
            with patch.object(Path, "mkdir", side_effect=OSError("disk full")):
                # Should not raise
                save_cache(result)

    def test_creates_cache_dir_if_missing(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "deep" / "nested" / "cache"
        result = MarkdownResult(
            content="content",
            source_path="/a.md",
            source_format="markdown",
            trace_id="nested1",
        )
        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            save_cache(result)

        assert cache_dir.exists()

    def test_unicode_content(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        result = MarkdownResult(
            content="你好世界",
            source_path="/tmp/中文.md",
            source_format="markdown",
            trace_id="uni1",
        )
        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            save_cache(result)

        md_path = cache_dir / "uni1.md"
        assert md_path.read_text(encoding="utf-8") == "你好世界"

        meta = json.loads((cache_dir / "uni1.json").read_text(encoding="utf-8"))
        assert meta["source_path"] == "/tmp/中文.md"


# ---------------------------------------------------------------------------
# get_cached
# ---------------------------------------------------------------------------

class TestGetCached:
    def test_returns_result_when_cached(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "t1.md").write_text("cached content", encoding="utf-8")
        (cache_dir / "t1.json").write_text(
            json.dumps({"source_path": "/a.md", "source_format": "markdown", "trace_id": "t1"}),
            encoding="utf-8",
        )

        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            result = get_cached("t1")

        assert result is not None
        assert result.content == "cached content"
        assert result.source_path == "/a.md"
        assert result.source_format == "markdown"
        assert result.trace_id == "t1"

    def test_returns_none_when_md_missing(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "t2.json").write_text("{}", encoding="utf-8")

        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            assert get_cached("t2") is None

    def test_returns_none_when_json_missing(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "t3.md").write_text("data", encoding="utf-8")

        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            assert get_cached("t3") is None

    def test_returns_none_when_both_missing(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            assert get_cached("nonexistent") is None

    def test_returns_none_on_corrupt_json(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "bad.md").write_text("content", encoding="utf-8")
        (cache_dir / "bad.json").write_text("NOT JSON", encoding="utf-8")

        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            assert get_cached("bad") is None

    def test_missing_meta_fields_default_to_empty(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "sparse.md").write_text("data", encoding="utf-8")
        (cache_dir / "sparse.json").write_text("{}", encoding="utf-8")

        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            result = get_cached("sparse")

        assert result is not None
        assert result.source_path == ""
        assert result.source_format == ""

    def test_roundtrip_save_then_get(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        original = MarkdownResult(
            content="roundtrip",
            source_path="/round.md",
            source_format="text",
            trace_id="rt1",
        )
        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            save_cache(original)
            loaded = get_cached("rt1")

        assert loaded is not None
        assert loaded.content == original.content
        assert loaded.source_path == original.source_path
        assert loaded.source_format == original.source_format
        assert loaded.trace_id == original.trace_id


# ---------------------------------------------------------------------------
# get_file_hash
# ---------------------------------------------------------------------------

class TestGetFileHash:
    def test_content_change_with_same_size_and_mtime_changes_hash(self, tmp_path: Path) -> None:
        file_path = tmp_path / "same.txt"
        file_path.write_text("AAAA", encoding="utf-8")
        hash1 = get_file_hash(file_path)

        fixed_ts = 1700000000
        os.utime(file_path, (fixed_ts, fixed_ts))
        file_path.write_text("BBBB", encoding="utf-8")
        os.utime(file_path, (fixed_ts, fixed_ts))
        hash2 = get_file_hash(file_path)

        assert hash1 != hash2

    def test_unreadable_content_falls_back_to_metadata_key(self, tmp_path: Path) -> None:
        file_path = tmp_path / "x.txt"
        file_path.write_text("data", encoding="utf-8")

        with patch("ankismart.converter.cache._hash_file_content", side_effect=OSError("locked")):
            value = get_file_hash(file_path)

        assert isinstance(value, str)
        assert len(value) == 64


class TestHashCache:
    def test_save_and_get_cached_by_hash_roundtrip(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        result = MarkdownResult(
            content="hash-content",
            source_path="/tmp/a.md",
            source_format="markdown",
            trace_id="trace-1",
        )
        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            save_cache_by_hash("abc", result)
            loaded = get_cached_by_hash("abc")

        assert loaded is not None
        assert loaded.content == "hash-content"
        assert loaded.source_path == "/tmp/a.md"
        assert loaded.source_format == "markdown"

    def test_get_cached_by_hash_returns_none_when_missing(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            assert get_cached_by_hash("missing") is None

    def test_get_cached_by_hash_returns_none_on_invalid_json(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "fh_bad.md").write_text("x", encoding="utf-8")
        (cache_dir / "fh_bad.json").write_text("{bad", encoding="utf-8")
        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            assert get_cached_by_hash("bad") is None


class TestCacheStatsAndClear:
    def test_cache_size_count_stats_and_clear(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "a.md").write_text("12345", encoding="utf-8")
        (cache_dir / "a.json").write_text("{}", encoding="utf-8")

        with patch("ankismart.converter.cache.CACHE_DIR", cache_dir):
            size_mb = get_cache_size()
            count = get_cache_count()
            stats = get_cache_stats()
            cleared = clear_cache()
            count_after = get_cache_count()

        assert size_mb > 0
        assert count == 2
        assert stats["count"] == 2
        assert cleared is True
        assert count_after == 0
