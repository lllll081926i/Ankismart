from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from ankismart.core.models import CardDraft


def export_cards_to_json(cards: list[CardDraft], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "card_count": len(cards),
        "cards": [card.model_dump(mode="json") for card in cards],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def export_cards_to_csv(cards: list[CardDraft], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "index",
                "deck_name",
                "note_type",
                "tags",
                "source_document",
                "strategy_id",
                "front",
                "back",
                "text",
                "extra",
                "trace_id",
            ],
        )
        writer.writeheader()
        for index, card in enumerate(cards, start=1):
            writer.writerow(
                {
                    "index": index,
                    "deck_name": card.deck_name,
                    "note_type": card.note_type,
                    "tags": ", ".join(card.tags),
                    "source_document": getattr(card.metadata, "source_document", "") or "",
                    "strategy_id": getattr(card.metadata, "strategy_id", "") or "",
                    "front": _field(card, "Front", "Question"),
                    "back": _field(card, "Back", "Answer"),
                    "text": _field(card, "Text"),
                    "extra": _field(card, "Extra"),
                    "trace_id": card.trace_id,
                }
            )
    return path


def export_cards_to_markdown(cards: list[CardDraft], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Ankismart 历史导出",
        "",
        f"- 导出时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 卡片数量：{len(cards)}",
        "",
    ]
    for index, card in enumerate(cards, start=1):
        lines.extend(_markdown_card_section(index, card))
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _markdown_card_section(index: int, card: CardDraft) -> list[str]:
    title = _compact_title(_field(card, "Front", "Question", "Text") or f"卡片 {index}")
    source_document = getattr(card.metadata, "source_document", "") or "未知"
    strategy_id = getattr(card.metadata, "strategy_id", "") or "未记录"
    lines = [
        f"## {index}. {title}",
        "",
        f"**牌组：** {card.deck_name}",
        f"**类型：** {card.note_type}",
        f"**来源文件：** {source_document}",
        f"**策略：** {strategy_id}",
        "",
    ]
    for key, value in card.fields.items():
        text = str(value or "").strip()
        if not text:
            continue
        lines.extend([f"### {key}", "", text, ""])
    return lines


def _field(card: CardDraft, *keys: str) -> str:
    for key in keys:
        value = str(card.fields.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _compact_title(text: str, *, limit: int = 64) -> str:
    plain = " ".join(str(text or "").replace("\r", " ").replace("\n", " ").split())
    if len(plain) <= limit:
        return plain
    return f"{plain[: limit - 1]}..."
