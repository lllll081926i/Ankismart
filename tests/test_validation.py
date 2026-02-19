"""Input validation tests for ImportPage."""

from __future__ import annotations

from types import SimpleNamespace

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui.import_page import ImportPage


def _make_page() -> ImportPage:
    page = ImportPage.__new__(ImportPage)
    page._main = SimpleNamespace(
        config=AppConfig(
            language="zh",
            llm_providers=[
                LLMProviderConfig(
                    id="p1",
                    name="OpenAI",
                    api_key="test",
                    base_url="https://api.openai.com/v1",
                    model="gpt-4o",
                )
            ],
            active_provider_id="p1",
        )
    )
    return page


def test_card_count_validation() -> None:
    page = _make_page()

    assert page._validate_card_count("20")[0] is True
    assert page._validate_card_count("1")[0] is True
    assert page._validate_card_count("1000")[0] is True

    assert page._validate_card_count("0")[0] is False
    assert page._validate_card_count("1001")[0] is False
    assert page._validate_card_count("-5")[0] is False
    assert page._validate_card_count("abc")[0] is False
    assert page._validate_card_count("20.5")[0] is False


def test_tags_validation() -> None:
    page = _make_page()

    assert page._validate_tags("ankismart")[0] is True
    assert page._validate_tags("ankismart, important")[0] is True
    assert page._validate_tags("重要, 复习")[0] is True
    assert page._validate_tags("tag_1, tag-2")[0] is True
    assert page._validate_tags("")[0] is True

    assert page._validate_tags("tag@123")[0] is False
    assert page._validate_tags("tag#test")[0] is False
    assert page._validate_tags("tag with spaces")[0] is False
    assert page._validate_tags("tag, @invalid")[0] is False


def test_deck_name_validation() -> None:
    page = _make_page()

    assert page._validate_deck_name("Default")[0] is True
    assert page._validate_deck_name("英语学习")[0] is True
    assert page._validate_deck_name("Math_2024")[0] is True
    assert page._validate_deck_name("My Deck")[0] is True

    assert page._validate_deck_name("")[0] is False
    assert page._validate_deck_name("   ")[0] is False
    assert page._validate_deck_name("deck<test>")[0] is False
    assert page._validate_deck_name("deck:test")[0] is False
    assert page._validate_deck_name("deck/test")[0] is False
    assert page._validate_deck_name(r"deck\test")[0] is False
    assert page._validate_deck_name("deck|test")[0] is False
    assert page._validate_deck_name("deck?test")[0] is False
    assert page._validate_deck_name("deck*test")[0] is False
