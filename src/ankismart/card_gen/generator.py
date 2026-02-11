from __future__ import annotations

from pathlib import Path

from ankismart.card_gen.llm_client import LLMClient
from ankismart.card_gen.postprocess import build_card_drafts, parse_llm_output
from ankismart.card_gen.prompts import (
    BASIC_SYSTEM_PROMPT,
    CLOZE_SYSTEM_PROMPT,
    CONCEPT_SYSTEM_PROMPT,
    IMAGE_QA_SYSTEM_PROMPT,
    KEY_TERMS_SYSTEM_PROMPT,
    OCR_CORRECTION_PROMPT,
)
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft, GenerateRequest, MediaItem
from ankismart.core.tracing import timed, trace_context

logger = get_logger("card_gen")

_STRATEGY_MAP: dict[str, tuple[str, str]] = {
    "basic": (BASIC_SYSTEM_PROMPT, "Basic"),
    "cloze": (CLOZE_SYSTEM_PROMPT, "Cloze"),
    "concept": (CONCEPT_SYSTEM_PROMPT, "Basic"),
    "key_terms": (KEY_TERMS_SYSTEM_PROMPT, "Basic"),
    "image_qa": (IMAGE_QA_SYSTEM_PROMPT, "Basic"),
    "image_occlusion": (IMAGE_QA_SYSTEM_PROMPT, "Basic"),
}

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


class CardGenerator:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def generate(self, request: GenerateRequest) -> list[CardDraft]:
        with trace_context(request.trace_id or None) as trace_id:
            with timed("card_generate_total"):
                strategy_info = _STRATEGY_MAP.get(request.strategy)
                if strategy_info is None:
                    strategy_info = _STRATEGY_MAP["basic"]

                system_prompt, note_type = strategy_info
                markdown = request.markdown

                logger.info(
                    "Generating cards",
                    extra={
                        "strategy": request.strategy,
                        "note_type": note_type,
                        "content_length": len(markdown),
                        "trace_id": trace_id,
                    },
                )

                # Call LLM
                with timed("llm_generate"):
                    raw_output = self._llm.chat(system_prompt, markdown)

                # Parse and build card drafts
                raw_cards = parse_llm_output(raw_output)
                drafts = build_card_drafts(
                    raw_cards=raw_cards,
                    deck_name=request.deck_name,
                    note_type=note_type,
                    tags=request.tags or ["ankismart"],
                    trace_id=trace_id,
                )

                # Attach source image for image-based strategy
                if (
                    request.strategy in {"image_qa", "image_occlusion"}
                    and request.source_path
                ):
                    self._attach_image(drafts, request.source_path)

                logger.info(
                    "Card generation completed",
                    extra={
                        "card_count": len(drafts),
                        "trace_id": trace_id,
                    },
                )
                return drafts

    def _attach_image(
        self, drafts: list[CardDraft], source_path: str
    ) -> None:
        """Attach source image to card fields and media."""
        p = Path(source_path)
        if p.suffix.lower() not in _IMAGE_EXTENSIONS:
            return
        filename = p.name
        img_tag = f'<img src="{filename}">'
        for draft in drafts:
            # Append image to Back field
            back = draft.fields.get("Back", "")
            draft.fields["Back"] = f"{back}<br>{img_tag}" if back else img_tag
            # Add as picture media
            draft.media.picture.append(
                MediaItem(
                    filename=filename,
                    path=str(p),
                    fields=["Back"],
                )
            )

    def correct_ocr_text(self, text: str) -> str:
        """Use LLM to correct OCR errors in text."""
        with timed("ocr_correction"):
            return self._llm.chat(OCR_CORRECTION_PROMPT, text)
