from __future__ import annotations

import inspect
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
_RAW_CARD_BUILD_SLACK_MULTIPLIER = 3
_RAW_CARD_BUILD_MIN_SLACK = 20
_RAW_CARD_BUILD_DEFAULT_CAP = 300
_RAW_CARD_BUILD_MAX_CAP = 500
_AUTO_CARD_SAFETY_MIN = 24
_AUTO_CARD_SAFETY_MAX = 240
_AUTO_CARD_CHARS_PER_CARD = 450


class CardGenerator:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    @staticmethod
    def _build_target_instruction(target_count: int, *, auto_target_count: bool) -> str:
        if auto_target_count:
            if target_count <= 0:
                return (
                    "\n- Decide the card count from the content length and knowledge density\n"
                    "- Create one card for each atomic, high-value knowledge point\n"
                    "- Skip low-value, repetitive, or purely transitional details\n"
                    "- Do not pad the output to reach a fixed number\n"
                    "- Keep the final set concise but complete for learning\n"
                )
            return (
                f"\n- Generate around {target_count} cards\n"
                "- cover all important knowledge points while keeping the output concise\n"
                "- treat the number as a soft guide, not a hard quota\n"
            )
        if target_count <= 0:
            return ""
        return f"\n- Generate exactly {target_count} cards\n"

    @staticmethod
    def _estimate_request_timeout(
        *,
        content_length: int,
        target_count: int,
        chunk_count: int = 1,
        auto_target_count: bool = False,
    ) -> float:
        base_timeout = 120.0
        length_bonus = min(240.0, max(0.0, content_length / 1500.0))
        target_bonus = min(180.0, max(0, target_count) * 10.0)
        chunk_bonus = min(180.0, max(0, chunk_count - 1) * 25.0)
        auto_bonus = 30.0 if auto_target_count else 0.0
        return base_timeout + length_bonus + target_bonus + chunk_bonus + auto_bonus

    @staticmethod
    def _raw_card_build_limit(target_count: int) -> int:
        if target_count <= 0:
            return _RAW_CARD_BUILD_DEFAULT_CAP
        requested_limit = max(
            target_count * _RAW_CARD_BUILD_SLACK_MULTIPLIER,
            target_count + _RAW_CARD_BUILD_MIN_SLACK,
        )
        return min(requested_limit, _RAW_CARD_BUILD_MAX_CAP)

    @staticmethod
    def _auto_card_safety_limit(content_length: int, *, target_hint: int = 0) -> int:
        length = max(0, int(content_length or 0))
        content_limit = _AUTO_CARD_SAFETY_MIN + (length // _AUTO_CARD_CHARS_PER_CARD)
        if target_hint > 0:
            content_limit = max(
                content_limit,
                target_hint * _RAW_CARD_BUILD_SLACK_MULTIPLIER,
                target_hint + _RAW_CARD_BUILD_MIN_SLACK,
            )
        return min(_AUTO_CARD_SAFETY_MAX, max(_AUTO_CARD_SAFETY_MIN, content_limit))

    @classmethod
    def _limit_raw_cards_for_build(
        cls,
        raw_cards: list[dict],
        *,
        target_count: int,
        strategy: str,
        trace_id: str,
    ) -> list[dict]:
        limit = cls._raw_card_build_limit(target_count)
        if len(raw_cards) <= limit:
            return raw_cards
        logger.warning(
            "LLM returned excessive raw cards; limiting before draft build",
            extra={
                "event": "card_gen.raw_cards.limited",
                "strategy": strategy,
                "raw_cards": len(raw_cards),
                "limit": limit,
                "target_count": target_count,
                "trace_id": trace_id,
            },
        )
        return raw_cards[:limit]

    @classmethod
    def _limit_auto_drafts_for_safety(
        cls,
        drafts: list[CardDraft],
        *,
        content_length: int,
        target_hint: int,
        strategy: str,
        trace_id: str,
    ) -> list[CardDraft]:
        limit = cls._auto_card_safety_limit(content_length, target_hint=target_hint)
        if len(drafts) <= limit:
            return drafts
        logger.warning(
            "Auto card generation exceeded content-derived safety limit; trimming output",
            extra={
                "event": "card_gen.auto_cards.limited",
                "strategy": strategy,
                "card_count": len(drafts),
                "limit": limit,
                "content_length": content_length,
                "target_hint": target_hint,
                "trace_id": trace_id,
            },
        )
        return drafts[:limit]

    @classmethod
    def _raw_limit_target_for_request(
        cls,
        *,
        target_count: int,
        auto_target_count: bool,
        content_length: int,
    ) -> int:
        if not auto_target_count or target_count > 0:
            return target_count
        return cls._auto_card_safety_limit(content_length, target_hint=0)

    def _chat_with_timeout(
        self, system_prompt: str, user_prompt: str, *, timeout: float | None
    ) -> str:
        chat_fn = self._llm.chat
        side_effect = getattr(chat_fn, "side_effect", None)
        signature_target = side_effect if callable(side_effect) else chat_fn

        supports_timeout = True
        try:
            parameters = inspect.signature(signature_target).parameters.values()
        except (TypeError, ValueError):
            parameters = ()

        if parameters:
            supports_timeout = False
            positional_count = 0
            for parameter in parameters:
                if parameter.kind == inspect.Parameter.VAR_KEYWORD:
                    supports_timeout = True
                    break
                if parameter.name == "timeout":
                    supports_timeout = True
                    break
                if parameter.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                ):
                    positional_count += 1
            if positional_count >= 3:
                supports_timeout = True

        if supports_timeout and timeout is not None:
            return self._llm.chat(system_prompt, user_prompt, timeout=timeout)
        return self._llm.chat(system_prompt, user_prompt)

    @staticmethod
    def _hard_split_text(text: str, threshold: int) -> list[str]:
        value = str(text or "")
        if threshold <= 0 or len(value) <= threshold:
            return [value]

        parts: list[str] = []
        start = 0
        while start < len(value):
            parts.append(value[start : start + threshold])
            start += threshold
        return [part for part in parts if part]

    def _split_code_block(self, code_block_buffer: list[str], threshold: int) -> list[str]:
        if not code_block_buffer:
            return []

        if len(code_block_buffer) == 1 and "\n" in code_block_buffer[0]:
            raw_lines = code_block_buffer[0].splitlines()
            opening = raw_lines[0]
            if len(raw_lines) > 1 and raw_lines[-1].strip() == "```":
                closing = raw_lines[-1].strip()
                body = "\n".join(raw_lines[1:-1])
            else:
                closing = "```"
                body = "\n".join(raw_lines[1:])
        else:
            opening = code_block_buffer[0]
            closing = code_block_buffer[-1] if len(code_block_buffer) > 1 else "```"
            body = "\n\n".join(code_block_buffer[1:-1] if len(code_block_buffer) > 1 else [])

        if len(f"{opening}\n{body}\n{closing}") <= threshold:
            return [f"{opening}\n{body}\n{closing}".strip()]

        max_body_length = max(1, threshold - len(opening) - len(closing) - 2)
        return [
            f"{opening}\n{piece}\n{closing}"
            for piece in self._hard_split_text(body, max_body_length)
        ]

    @staticmethod
    def _is_complete_code_block_paragraph(text: str) -> bool:
        lines = str(text or "").splitlines()
        if len(lines) < 2 or not lines[0].strip().startswith("```"):
            return False

        for index, line in enumerate(lines[1:], 1):
            if line.strip().startswith("```"):
                return all(not trailing.strip() for trailing in lines[index + 1 :])
        return False

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

        def can_append_to_current(text: str) -> bool:
            separator_length = 2 if current_chunk else 0
            return current_length + separator_length + len(text) <= threshold

        def append_to_current(text: str) -> None:
            nonlocal current_length
            separator_length = 2 if current_chunk else 0
            current_chunk.append(text)
            current_length += separator_length + len(text)

        def reset_current(text: str) -> None:
            nonlocal current_chunk, current_length
            current_chunk = [text]
            current_length = len(text)

        def flush_current() -> None:
            nonlocal current_chunk, current_length
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0

        def flush_code_block(complete_block: str, buffer: list[str]) -> None:
            if len(complete_block) > threshold:
                flush_current()
                chunks.extend(self._split_code_block(buffer, threshold))
                return

            if not can_append_to_current(complete_block):
                flush_current()
                reset_current(complete_block)
            else:
                append_to_current(complete_block)

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Detect code block boundaries
            if para.startswith("```"):
                if not in_code_block:
                    if self._is_complete_code_block_paragraph(para):
                        flush_code_block(para, [para])
                        continue
                    # Start of code block
                    in_code_block = True
                    code_block_buffer = [para]
                    continue
                else:
                    # End of code block
                    in_code_block = False
                    code_block_buffer.append(para)
                    complete_block = "\n\n".join(code_block_buffer)

                    flush_code_block(complete_block, code_block_buffer)

                    code_block_buffer = []
                    continue

            # If inside code block, accumulate
            if in_code_block:
                code_block_buffer.append(para)
                continue

            para_length = len(para)

            # If single paragraph exceeds threshold, split it by sentences
            if para_length > threshold:
                flush_current()

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
                        if len(sentence) > threshold:
                            for piece in self._hard_split_text(sentence, threshold):
                                chunks.append(piece)
                            sentence_chunk = []
                            sentence_length = 0
                        else:
                            sentence_chunk = [sentence]
                            sentence_length = len(sentence)
                    else:
                        sentence_chunk.append(sentence)
                        sentence_length += len(sentence)

                if sentence_chunk:
                    chunks.append("".join(sentence_chunk))
                continue

            # Normal paragraph handling
            if not can_append_to_current(para):
                flush_current()
                reset_current(para)
            else:
                append_to_current(para)

        # Add remaining content
        if code_block_buffer:
            trailing_chunks = self._split_code_block(code_block_buffer, threshold)
            if len(trailing_chunks) == 1 and len(trailing_chunks[0]) <= threshold:
                if can_append_to_current(trailing_chunks[0]):
                    append_to_current(trailing_chunks[0])
                else:
                    flush_current()
                    reset_current(trailing_chunks[0])
            else:
                flush_current()
                chunks.extend(trailing_chunks)

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
                auto_target_count = bool(getattr(request, "auto_target_count", False))

                system_prompt = base_system_prompt
                system_prompt += self._build_target_instruction(
                    request.target_count,
                    auto_target_count=auto_target_count,
                )

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
                        if (
                            remaining_target <= 0
                            and request.target_count > 0
                            and not auto_target_count
                        ):
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
                        chunk_system_prompt += self._build_target_instruction(
                            chunk_target or request.target_count,
                            auto_target_count=auto_target_count,
                        )

                        request_timeout = self._estimate_request_timeout(
                            content_length=len(chunk),
                            target_count=chunk_target or request.target_count,
                            chunk_count=len(chunks),
                            auto_target_count=auto_target_count,
                        )

                        # Call LLM for this chunk
                        with timed(f"llm_generate_chunk_{i}"):
                            raw_output = self._chat_with_timeout(
                                chunk_system_prompt,
                                chunk,
                                timeout=request_timeout,
                            )

                        # Parse and build card drafts for this chunk
                        raw_limit_target = self._raw_limit_target_for_request(
                            target_count=chunk_target or request.target_count,
                            auto_target_count=auto_target_count,
                            content_length=len(chunk),
                        )
                        raw_cards = self._limit_raw_cards_for_build(
                            parse_llm_output(raw_output),
                            target_count=raw_limit_target,
                            strategy=normalized_strategy,
                            trace_id=trace_id,
                        )
                        chunk_drafts = build_card_drafts(
                            raw_cards=raw_cards,
                            deck_name=request.deck_name,
                            note_type=note_type,
                            tags=request.tags or ["ankismart"],
                            trace_id=trace_id,
                            source_path=request.source_path,
                            source_document=(
                                Path(request.source_path).name if request.source_path else ""
                            ),
                            strategy_id=normalized_strategy,
                        )

                        if (
                            chunk_target > 0
                            and not auto_target_count
                            and len(chunk_drafts) > chunk_target
                        ):
                            chunk_drafts = chunk_drafts[:chunk_target]

                        all_drafts.extend(chunk_drafts)
                        if remaining_target > 0:
                            remaining_target = max(0, remaining_target - len(chunk_drafts))
                            if auto_target_count and request.target_count > 0:
                                remaining_target = max(1, remaining_target)
                            if remaining_target <= 0 and not auto_target_count:
                                break

                    drafts = all_drafts
                else:
                    request_timeout = self._estimate_request_timeout(
                        content_length=len(markdown),
                        target_count=request.target_count,
                        auto_target_count=auto_target_count,
                    )
                    # Normal processing without split
                    with timed("llm_generate"):
                        raw_output = self._chat_with_timeout(
                            system_prompt,
                            markdown,
                            timeout=request_timeout,
                        )

                    # Parse and build card drafts
                    raw_limit_target = self._raw_limit_target_for_request(
                        target_count=request.target_count,
                        auto_target_count=auto_target_count,
                        content_length=len(markdown),
                    )
                    raw_cards = self._limit_raw_cards_for_build(
                        parse_llm_output(raw_output),
                        target_count=raw_limit_target,
                        strategy=normalized_strategy,
                        trace_id=trace_id,
                    )
                    drafts = build_card_drafts(
                        raw_cards=raw_cards,
                        deck_name=request.deck_name,
                        note_type=note_type,
                        tags=request.tags or ["ankismart"],
                        trace_id=trace_id,
                        source_path=request.source_path,
                        source_document=(
                            Path(request.source_path).name if request.source_path else ""
                        ),
                        strategy_id=normalized_strategy,
                    )

                # Attach source image for image-based strategy
                if normalized_strategy in {"image_qa", "image_occlusion"} and request.source_path:
                    self._attach_image(drafts, request.source_path)

                if auto_target_count:
                    drafts = self._limit_auto_drafts_for_safety(
                        drafts,
                        content_length=len(markdown),
                        target_hint=max(0, request.target_count),
                        strategy=normalized_strategy,
                        trace_id=trace_id,
                    )
                elif request.target_count > 0 and len(drafts) > request.target_count:
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
