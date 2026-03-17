from __future__ import annotations

import re
from pathlib import Path

from ankismart.card_gen.llm_client import LLMClient
from ankismart.card_gen.postprocess import build_card_drafts, parse_llm_output
from ankismart.card_gen.prompts import (
    BASIC_SYSTEM_PROMPT,
    CLOZE_SYSTEM_PROMPT,
    CONCEPT_SYSTEM_PROMPT,
    IMAGE_QA_SYSTEM_PROMPT,
    KEY_TERMS_SYSTEM_PROMPT,
    MULTIPLE_CHOICE_SYSTEM_PROMPT,
    OCR_CORRECTION_PROMPT,
    SINGLE_CHOICE_SYSTEM_PROMPT,
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
    "single_choice": (SINGLE_CHOICE_SYSTEM_PROMPT, "Basic"),
    "multiple_choice": (MULTIPLE_CHOICE_SYSTEM_PROMPT, "Basic"),
    "image_qa": (IMAGE_QA_SYSTEM_PROMPT, "Basic"),
    "image_occlusion": (IMAGE_QA_SYSTEM_PROMPT, "Basic"),
}

_STRATEGY_ALIASES = {
    "basic_qa": "basic",
    "fill_blank": "cloze",
    "concept_explanation": "concept",
}

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


class CardGenerator:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def _split_markdown(self, markdown: str, threshold: int) -> list[str]:
        """Split markdown content into chunks at paragraph boundaries.

        Args:
            markdown: The markdown content to split
            threshold: Maximum character count per chunk

        Returns:
            List of markdown chunks, each under the threshold
        """
        if len(markdown) <= threshold:
            return [markdown]

        chunks = []
        current_chunk = []
        current_length = 0

        # Split by double newlines (paragraph boundaries)
        paragraphs = re.split(r"\n\n+", markdown)

        # Track if we're inside a code block or table
        in_code_block = False
        code_block_buffer = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Detect code block boundaries
            if para.startswith("```"):
                if not in_code_block:
                    # Start of code block
                    in_code_block = True
                    code_block_buffer = [para]
                    continue
                else:
                    # End of code block
                    in_code_block = False
                    code_block_buffer.append(para)
                    complete_block = "\n\n".join(code_block_buffer)

                    # If code block is too large, add it as separate chunk
                    if len(complete_block) > threshold:
                        if current_chunk:
                            chunks.append("\n\n".join(current_chunk))
                            current_chunk = []
                            current_length = 0
                        chunks.append(complete_block)
                    else:
                        # Try to add to current chunk
                        if current_length + len(complete_block) > threshold:
                            if current_chunk:
                                chunks.append("\n\n".join(current_chunk))
                            current_chunk = [complete_block]
                            current_length = len(complete_block)
                        else:
                            current_chunk.append(complete_block)
                            current_length += len(complete_block) + 2

                    code_block_buffer = []
                    continue

            # If inside code block, accumulate
            if in_code_block:
                code_block_buffer.append(para)
                continue

            para_length = len(para)

            # If single paragraph exceeds threshold, split it by sentences
            if para_length > threshold:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # Split by sentences for very long paragraphs
                sentences = re.split(r"([.!?。！？]\s+)", para)
                sentence_chunk = []
                sentence_length = 0

                for i in range(0, len(sentences), 2):
                    sentence = sentences[i]
                    if i + 1 < len(sentences):
                        sentence += sentences[i + 1]

                    if sentence_length + len(sentence) > threshold:
                        if sentence_chunk:
                            chunks.append("".join(sentence_chunk))
                        sentence_chunk = [sentence]
                        sentence_length = len(sentence)
                    else:
                        sentence_chunk.append(sentence)
                        sentence_length += len(sentence)

                if sentence_chunk:
                    chunks.append("".join(sentence_chunk))
                continue

            # Normal paragraph handling
            if current_length + para_length > threshold:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_length = para_length
            else:
                current_chunk.append(para)
                current_length += para_length + 2  # +2 for \n\n

        # Add remaining content
        if code_block_buffer:
            # Unclosed code block
            remaining = "\n\n".join(code_block_buffer)
            if current_chunk:
                current_chunk.append(remaining)
            else:
                current_chunk = [remaining]

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        logger.info(
            "Document split into chunks",
            extra={
                "original_length": len(markdown),
                "chunk_count": len(chunks),
                "threshold": threshold,
            },
        )

        return chunks

    def generate(self, request: GenerateRequest) -> list[CardDraft]:
        with trace_context(request.trace_id or None) as trace_id:
            with timed("card_generate_total"):
                normalized_strategy = _STRATEGY_ALIASES.get(request.strategy, request.strategy)
                strategy_info = _STRATEGY_MAP.get(normalized_strategy)
                if strategy_info is None:
                    strategy_info = _STRATEGY_MAP["basic"]
                    normalized_strategy = "basic"

                base_system_prompt, note_type = strategy_info
                markdown = request.markdown

                system_prompt = base_system_prompt
                if request.target_count > 0:
                    system_prompt += f"\n- Generate exactly {request.target_count} cards\n"

                logger.info(
                    "Generating cards",
                    extra={
                        "strategy": normalized_strategy,
                        "strategy_requested": request.strategy,
                        "note_type": note_type,
                        "content_length": len(markdown),
                        "target_count": request.target_count,
                        "trace_id": trace_id,
                    },
                )

                # Check if auto-split is needed
                enable_split = getattr(request, "enable_auto_split", False)
                split_threshold = getattr(request, "split_threshold", 70000)

                all_drafts = []

                if enable_split and len(markdown) > split_threshold:
                    # Split document into chunks
                    chunks = self._split_markdown(markdown, split_threshold)
                    remaining_target = max(0, request.target_count)

                    logger.info(
                        "Processing document in chunks",
                        extra={
                            "chunk_count": len(chunks),
                            "trace_id": trace_id,
                        },
                    )

                    # Process each chunk
                    for i, chunk in enumerate(chunks, 1):
                        if remaining_target <= 0 and request.target_count > 0:
                            break

                        logger.info(
                            f"Processing chunk {i}/{len(chunks)}",
                            extra={
                                "chunk_index": i,
                                "chunk_length": len(chunk),
                                "trace_id": trace_id,
                            },
                        )

                        chunk_system_prompt = base_system_prompt
                        chunk_target = 0
                        if remaining_target > 0:
                            chunks_left = len(chunks) - i + 1
                            base_target = remaining_target // max(1, chunks_left)
                            extra_target = 1 if remaining_target % max(1, chunks_left) else 0
                            chunk_target = max(1, base_target + extra_target)
                            chunk_system_prompt += (
                                f"\n- Generate exactly {chunk_target} cards\n"
                            )

                        # Call LLM for this chunk
                        with timed(f"llm_generate_chunk_{i}"):
                            raw_output = self._llm.chat(chunk_system_prompt, chunk)

                        # Parse and build card drafts for this chunk
                        raw_cards = parse_llm_output(raw_output)
                        chunk_drafts = build_card_drafts(
                            raw_cards=raw_cards,
                            deck_name=request.deck_name,
                            note_type=note_type,
                            tags=request.tags or ["ankismart"],
                            trace_id=trace_id,
                        )

                        if chunk_target > 0 and len(chunk_drafts) > chunk_target:
                            chunk_drafts = chunk_drafts[:chunk_target]

                        all_drafts.extend(chunk_drafts)
                        if remaining_target > 0:
                            remaining_target = max(0, remaining_target - len(chunk_drafts))
                            if remaining_target <= 0:
                                break

                    drafts = all_drafts
                else:
                    # Normal processing without split
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
                if normalized_strategy in {"image_qa", "image_occlusion"} and request.source_path:
                    self._attach_image(drafts, request.source_path)

                if request.target_count > 0 and len(drafts) > request.target_count:
                    drafts = drafts[: request.target_count]

                logger.info(
                    "Card generation completed",
                    extra={
                        "card_count": len(drafts),
                        "trace_id": trace_id,
                    },
                )
                return drafts

    def _attach_image(self, drafts: list[CardDraft], source_path: str) -> None:
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
