"""Tests for ankismart.card_gen.generator module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from ankismart.card_gen.generator import _STRATEGY_MAP, CardGenerator
from ankismart.card_gen.prompts import (
    BASIC_SYSTEM_PROMPT,
    CLOZE_SYSTEM_PROMPT,
    IMAGE_QA_SYSTEM_PROMPT,
    MULTIPLE_CHOICE_SYSTEM_PROMPT,
    OCR_CORRECTION_PROMPT,
    SINGLE_CHOICE_SYSTEM_PROMPT,
)
from ankismart.core.models import GenerateRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_llm_basic(system_prompt: str, user_prompt: str) -> str:
    return json.dumps([{"Front": "Q1", "Back": "A1"}, {"Front": "Q2", "Back": "A2"}])


def _fake_llm_cloze(system_prompt: str, user_prompt: str) -> str:
    return json.dumps([
        {"Text": "The {{c1::sun}} is a star.", "Extra": ""},
        {"Text": "{{c1::Water}} is H2O.", "Extra": "Chemistry"},
    ])


def _make_generator(chat_side_effect=None, chat_return_value=None) -> CardGenerator:
    mock_llm = MagicMock()
    if chat_side_effect is not None:
        mock_llm.chat.side_effect = chat_side_effect
    elif chat_return_value is not None:
        mock_llm.chat.return_value = chat_return_value
    else:
        mock_llm.chat.side_effect = _fake_llm_basic
    return CardGenerator(llm_client=mock_llm)


# ---------------------------------------------------------------------------
# CardGenerator.generate
# ---------------------------------------------------------------------------


class TestCardGeneratorGenerate:
    """Tests for CardGenerator.generate."""

    def test_basic_strategy(self):
        gen = _make_generator(chat_side_effect=_fake_llm_basic)
        request = GenerateRequest(
            markdown="# Hello\nSome content",
            strategy="basic",
            deck_name="MyDeck",
            tags=["test"],
            trace_id="t-100",
        )
        drafts = gen.generate(request)

        assert len(drafts) == 2
        assert drafts[0].deck_name == "MyDeck"
        assert drafts[0].note_type == "Basic"
        assert drafts[0].fields["Front"] == "Q1"
        assert drafts[0].tags == ["test"]

    def test_cloze_strategy(self):
        gen = _make_generator(chat_side_effect=_fake_llm_cloze)
        request = GenerateRequest(
            markdown="Some cloze content",
            strategy="cloze",
            deck_name="ClozeDeck",
        )
        drafts = gen.generate(request)

        assert len(drafts) == 2
        assert drafts[0].note_type == "Cloze"
        assert "{{c1::" in drafts[0].fields["Text"]

    def test_unknown_strategy_falls_back_to_basic(self):
        gen = _make_generator(chat_side_effect=_fake_llm_basic)
        request = GenerateRequest(
            markdown="content",
            strategy="nonexistent_strategy",
        )
        drafts = gen.generate(request)

        # Should fall back to basic
        assert len(drafts) == 2
        assert drafts[0].note_type == "Basic"
        # Verify the LLM was called with BASIC_SYSTEM_PROMPT
        gen._llm.chat.assert_called_once()
        call_args = gen._llm.chat.call_args
        assert call_args[0][0] == BASIC_SYSTEM_PROMPT

    def test_default_tags_when_none_provided(self):
        gen = _make_generator(chat_side_effect=_fake_llm_basic)
        request = GenerateRequest(markdown="content", tags=[])
        drafts = gen.generate(request)

        assert drafts[0].tags == ["ankismart"]

    def test_strategy_map_uses_correct_prompts(self):
        assert _STRATEGY_MAP["basic"][0] == BASIC_SYSTEM_PROMPT
        assert _STRATEGY_MAP["cloze"][0] == CLOZE_SYSTEM_PROMPT
        assert _STRATEGY_MAP["single_choice"][0] == SINGLE_CHOICE_SYSTEM_PROMPT
        assert _STRATEGY_MAP["multiple_choice"][0] == MULTIPLE_CHOICE_SYSTEM_PROMPT
        assert _STRATEGY_MAP["image_qa"][0] == IMAGE_QA_SYSTEM_PROMPT
        assert _STRATEGY_MAP["image_occlusion"][0] == IMAGE_QA_SYSTEM_PROMPT

    def test_target_count_trims_generated_cards(self):
        gen = _make_generator(chat_side_effect=_fake_llm_basic)
        request = GenerateRequest(markdown="content", strategy="basic", target_count=1)
        drafts = gen.generate(request)

        assert len(drafts) == 1

    def test_image_qa_attaches_image(self, tmp_path):
        img_path = tmp_path / "diagram.png"
        img_path.write_bytes(b"\x89PNG fake")

        gen = _make_generator(chat_side_effect=_fake_llm_basic)
        request = GenerateRequest(
            markdown="OCR text from image",
            strategy="image_qa",
            deck_name="ImgDeck",
            source_path=str(img_path),
        )
        drafts = gen.generate(request)

        assert len(drafts) == 2
        for draft in drafts:
            assert '<img src="diagram.png">' in draft.fields["Back"]
            assert len(draft.media.picture) == 1
            assert draft.media.picture[0].filename == "diagram.png"
            assert draft.media.picture[0].path == str(img_path)
            assert draft.media.picture[0].fields == ["Back"]

    def test_image_qa_non_image_extension_no_attach(self, tmp_path):
        txt_path = tmp_path / "notes.txt"
        txt_path.write_text("some text")

        gen = _make_generator(chat_side_effect=_fake_llm_basic)
        request = GenerateRequest(
            markdown="text content",
            strategy="image_qa",
            source_path=str(txt_path),
        )
        drafts = gen.generate(request)

        for draft in drafts:
            assert "<img" not in draft.fields.get("Back", "")
            assert len(draft.media.picture) == 0

    def test_image_qa_no_source_path(self):
        gen = _make_generator(chat_side_effect=_fake_llm_basic)
        request = GenerateRequest(
            markdown="text",
            strategy="image_qa",
            source_path="",
        )
        drafts = gen.generate(request)

        for draft in drafts:
            assert len(draft.media.picture) == 0

    def test_basic_strategy_no_image_attach(self, tmp_path):
        img_path = tmp_path / "photo.jpg"
        img_path.write_bytes(b"\xff\xd8 fake jpg")

        gen = _make_generator(chat_side_effect=_fake_llm_basic)
        request = GenerateRequest(
            markdown="content",
            strategy="basic",
            source_path=str(img_path),
        )
        drafts = gen.generate(request)

        # basic strategy should NOT attach images
        for draft in drafts:
            assert len(draft.media.picture) == 0

    def test_image_back_field_appends_to_existing(self, tmp_path):
        img_path = tmp_path / "fig.jpeg"
        img_path.write_bytes(b"fake")

        gen = _make_generator(chat_side_effect=_fake_llm_basic)
        request = GenerateRequest(
            markdown="content",
            strategy="image_qa",
            source_path=str(img_path),
        )
        drafts = gen.generate(request)

        # Back field should be "A1<br><img ...>"
        assert drafts[0].fields["Back"].startswith("A1<br>")

    def test_llm_called_with_markdown_content(self):
        gen = _make_generator(chat_side_effect=_fake_llm_basic)
        request = GenerateRequest(markdown="My special content")
        gen.generate(request)

        gen._llm.chat.assert_called_once()
        call_args = gen._llm.chat.call_args[0]
        assert call_args[1] == "My special content"


# ---------------------------------------------------------------------------
# CardGenerator.correct_ocr_text
# ---------------------------------------------------------------------------


class TestCorrectOcrText:
    """Tests for CardGenerator.correct_ocr_text."""

    def test_calls_llm_with_ocr_prompt(self):
        gen = _make_generator(chat_return_value="corrected text")
        result = gen.correct_ocr_text("raw OCR text with err0rs")

        assert result == "corrected text"
        gen._llm.chat.assert_called_once_with(OCR_CORRECTION_PROMPT, "raw OCR text with err0rs")

    def test_returns_llm_output_directly(self):
        gen = _make_generator(chat_return_value="clean output")
        result = gen.correct_ocr_text("messy input")
        assert result == "clean output"
