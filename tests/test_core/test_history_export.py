from __future__ import annotations

import csv
import json
from pathlib import Path

from ankismart.core.history_export import (
    export_cards_to_csv,
    export_cards_to_json,
    export_cards_to_markdown,
)
from ankismart.core.models import CardDraft, CardMetadata


def _card(index: int) -> CardDraft:
    return CardDraft(
        trace_id=f"trace-{index}",
        deck_name="Default",
        note_type="Basic",
        fields={"Front": f"问题 {index}", "Back": f"答案 {index}"},
        tags=["ankismart", "history"],
        metadata=CardMetadata(source_document="lesson.md", strategy_id="basic"),
    )


def test_export_cards_to_json_writes_readable_payload(tmp_path: Path) -> None:
    output = tmp_path / "cards.json"

    export_cards_to_json([_card(1)], output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["card_count"] == 1
    assert payload["cards"][0]["fields"]["Front"] == "问题 1"


def test_export_cards_to_csv_writes_flat_rows(tmp_path: Path) -> None:
    output = tmp_path / "cards.csv"

    export_cards_to_csv([_card(1), _card(2)], output)

    rows = list(csv.DictReader(output.read_text(encoding="utf-8-sig").splitlines()))
    assert rows[0]["source_document"] == "lesson.md"
    assert rows[0]["front"] == "问题 1"
    assert rows[1]["back"] == "答案 2"


def test_export_cards_to_markdown_writes_card_sections(tmp_path: Path) -> None:
    output = tmp_path / "cards.md"

    export_cards_to_markdown([_card(1)], output)

    content = output.read_text(encoding="utf-8")
    assert "# Ankismart 历史导出" in content
    assert "## 1. 问题 1" in content
    assert "**来源文件：** lesson.md" in content
    assert "答案 1" in content
