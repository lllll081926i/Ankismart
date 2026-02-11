from __future__ import annotations

import json
import re

from ankismart.core.errors import CardGenError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft, CardMetadata
from ankismart.core.tracing import get_trace_id

logger = get_logger("card_gen.postprocess")

_CLOZE_PATTERN = re.compile(r"\{\{c\d+::.*?\}\}")


def parse_llm_output(raw: str) -> list[dict]:
    """Extract JSON array from LLM output, handling markdown code blocks."""
    trace_id = get_trace_id()
    text = raw.strip()

    # Strip markdown code block wrapper if present
    if text.startswith("```"):
        # Remove first line (```json or ```) and last line (```)
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    # Try to find JSON array in the text
    bracket_start = text.find("[")
    bracket_end = text.rfind("]")
    if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
        text = text[bracket_start:bracket_end + 1]

    try:
        result = json.loads(text)
        if not isinstance(result, list):
            raise ValueError("Expected JSON array")
        return result
    except (json.JSONDecodeError, ValueError) as exc:
        raise CardGenError(
            f"Failed to parse LLM output as JSON: {exc}",
            code=ErrorCode.E_LLM_PARSE_ERROR,
            trace_id=trace_id,
        ) from exc


def validate_cloze(text: str) -> bool:
    """Check that text contains at least one valid cloze deletion."""
    return bool(_CLOZE_PATTERN.search(text))


def build_card_drafts(
    raw_cards: list[dict],
    deck_name: str,
    note_type: str,
    tags: list[str],
    trace_id: str,
    source_format: str = "",
) -> list[CardDraft]:
    """Convert raw LLM output dicts into validated CardDraft objects."""
    drafts: list[CardDraft] = []

    for i, card in enumerate(raw_cards):
        if not isinstance(card, dict):
            logger.warning("Skipping non-dict card", extra={"index": i, "trace_id": trace_id})
            continue

        # For Cloze cards, validate syntax
        if note_type == "Cloze":
            text = card.get("Text", "")
            if not validate_cloze(text):
                logger.warning(
                    "Skipping card with invalid cloze syntax",
                    extra={"index": i, "trace_id": trace_id},
                )
                continue

        draft = CardDraft(
            trace_id=trace_id,
            deck_name=deck_name,
            note_type=note_type,
            fields=card,
            tags=tags,
            metadata=CardMetadata(source_format=source_format),
        )
        drafts.append(draft)

    return drafts
