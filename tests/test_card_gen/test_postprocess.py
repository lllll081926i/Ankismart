"""Tests for ankismart.card_gen.postprocess module."""

from __future__ import annotations

import json

import pytest

from ankismart.card_gen.postprocess import (
    build_card_drafts,
    parse_llm_output,
    validate_cloze,
)
from ankismart.core.errors import CardGenError, ErrorCode

# ---------------------------------------------------------------------------
# parse_llm_output
# ---------------------------------------------------------------------------


class TestParseLlmOutput:
    """Tests for parse_llm_output."""

    def test_plain_json_array(self):
        raw = '[{"Front": "Q1", "Back": "A1"}]'
        result = parse_llm_output(raw)
        assert result == [{"Front": "Q1", "Back": "A1"}]

    def test_json_with_surrounding_whitespace(self):
        raw = '  \n [{"Front": "Q"}] \n '
        result = parse_llm_output(raw)
        assert result == [{"Front": "Q"}]

    def test_markdown_code_block_json(self):
        raw = '```json\n[{"Front": "Q", "Back": "A"}]\n```'
        result = parse_llm_output(raw)
        assert result == [{"Front": "Q", "Back": "A"}]

    def test_markdown_code_block_no_lang(self):
        raw = '```\n[{"Text": "hello"}]\n```'
        result = parse_llm_output(raw)
        assert result == [{"Text": "hello"}]

    def test_markdown_code_block_without_trailing_backticks(self):
        raw = '```json\n[{"Front": "Q", "Back": "A"}]'
        result = parse_llm_output(raw)
        assert result == [{"Front": "Q", "Back": "A"}]

    def test_json_array_embedded_in_text(self):
        raw = 'Here are the cards:\n[{"Front": "Q"}]\nDone.'
        result = parse_llm_output(raw)
        assert result == [{"Front": "Q"}]

    def test_multiple_objects_in_array(self):
        cards = [{"Front": "Q1", "Back": "A1"}, {"Front": "Q2", "Back": "A2"}]
        raw = json.dumps(cards)
        result = parse_llm_output(raw)
        assert len(result) == 2
        assert result[0]["Front"] == "Q1"
        assert result[1]["Front"] == "Q2"

    def test_empty_array(self):
        result = parse_llm_output("[]")
        assert result == []

    def test_invalid_json_raises_card_gen_error(self):
        with pytest.raises(CardGenError) as exc_info:
            parse_llm_output("not json at all")
        assert exc_info.value.code == ErrorCode.E_LLM_PARSE_ERROR

    def test_json_object_not_array_raises_error(self):
        with pytest.raises(CardGenError) as exc_info:
            parse_llm_output('{"Front": "Q"}')
        assert exc_info.value.code == ErrorCode.E_LLM_PARSE_ERROR

    def test_broken_json_raises_error(self):
        with pytest.raises(CardGenError):
            parse_llm_output('[{"Front": "Q"')


# ---------------------------------------------------------------------------
# validate_cloze
# ---------------------------------------------------------------------------


class TestValidateCloze:
    """Tests for validate_cloze."""

    def test_valid_single_cloze(self):
        assert validate_cloze("The {{c1::sun}} is a star.") is True

    def test_valid_multiple_cloze(self):
        assert validate_cloze("{{c1::A}} and {{c2::B}}") is True

    def test_no_cloze(self):
        assert validate_cloze("No cloze here.") is False

    def test_empty_string(self):
        assert validate_cloze("") is False

    def test_malformed_cloze_missing_braces(self):
        assert validate_cloze("{c1::answer}") is False

    def test_cloze_with_hint(self):
        # {{c1::answer::hint}} -- the regex matches because .*? covers "answer::hint"
        assert validate_cloze("{{c1::answer::hint}}") is True

    def test_cloze_number_multidigit(self):
        assert validate_cloze("{{c12::value}}") is True


# ---------------------------------------------------------------------------
# build_card_drafts
# ---------------------------------------------------------------------------


class TestBuildCardDrafts:
    """Tests for build_card_drafts."""

    def _basic_cards(self):
        return [
            {"Front": "Q1", "Back": "A1"},
            {"Front": "Q2", "Back": "A2"},
        ]

    def test_basic_note_type(self):
        drafts = build_card_drafts(
            raw_cards=self._basic_cards(),
            deck_name="TestDeck",
            note_type="Basic",
            tags=["tag1"],
            trace_id="t-123",
        )
        assert len(drafts) == 2
        assert drafts[0].deck_name == "TestDeck"
        assert drafts[0].note_type == "Basic"
        assert drafts[0].tags == ["tag1"]
        assert drafts[0].trace_id == "t-123"
        assert drafts[0].fields == {"Front": "Q1", "Back": "A1"}

    def test_cloze_valid_cards(self):
        raw = [
            {"Text": "The {{c1::sun}} is a star.", "Extra": ""},
            {"Text": "{{c1::Water}} is H2O.", "Extra": "Chemistry"},
        ]
        drafts = build_card_drafts(
            raw_cards=raw,
            deck_name="Deck",
            note_type="Cloze",
            tags=[],
            trace_id="t-1",
        )
        assert len(drafts) == 2

    def test_cloze_skips_invalid_syntax(self):
        raw = [
            {"Text": "No cloze here.", "Extra": ""},
            {"Text": "{{c1::valid}} card.", "Extra": ""},
        ]
        drafts = build_card_drafts(
            raw_cards=raw,
            deck_name="Deck",
            note_type="Cloze",
            tags=[],
            trace_id="t-2",
        )
        assert len(drafts) == 1
        assert "valid" in drafts[0].fields["Text"]

    def test_skips_non_dict_entries(self):
        raw = [
            {"Front": "Q", "Back": "A"},
            "not a dict",
            42,
            None,
        ]
        drafts = build_card_drafts(
            raw_cards=raw,
            deck_name="Deck",
            note_type="Basic",
            tags=[],
            trace_id="t-3",
        )
        assert len(drafts) == 1

    def test_empty_input(self):
        drafts = build_card_drafts(
            raw_cards=[],
            deck_name="Deck",
            note_type="Basic",
            tags=[],
            trace_id="t-4",
        )
        assert drafts == []

    def test_source_format_metadata(self):
        drafts = build_card_drafts(
            raw_cards=[{"Front": "Q", "Back": "A"}],
            deck_name="Deck",
            note_type="Basic",
            tags=["t"],
            trace_id="t-5",
            source_format="pdf",
        )
        assert drafts[0].metadata.source_format == "pdf"

    def test_all_cloze_invalid_returns_empty(self):
        raw = [
            {"Text": "No cloze 1"},
            {"Text": "No cloze 2"},
        ]
        drafts = build_card_drafts(
            raw_cards=raw,
            deck_name="Deck",
            note_type="Cloze",
            tags=[],
            trace_id="t-6",
        )
        assert drafts == []
