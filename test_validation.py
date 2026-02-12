"""Test input validation for ImportPage."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ankismart.ui.import_page import ImportPage
from ankismart.core.config import AppConfig, LLMProvider
from PyQt6.QtWidgets import QApplication


def test_card_count_validation():
    """Test card count validation."""
    app = QApplication.instance() or QApplication(sys.argv)

    # Create mock main window with config
    class MockMainWindow:
        def __init__(self):
            self.config = AppConfig()
            self.config.language = "zh"
            self.config.llm_providers = [
                LLMProvider(
                    name="Test",
                    base_url="http://test.com",
                    api_key="test",
                    model="test"
                )
            ]

    main = MockMainWindow()
    page = ImportPage(main)

    # Test valid inputs
    print("Testing valid card counts...")
    assert page._validate_card_count("20")[0] == True
    assert page._validate_card_count("1")[0] == True
    assert page._validate_card_count("1000")[0] == True
    print("✓ Valid card counts passed")

    # Test invalid inputs
    print("\nTesting invalid card counts...")
    assert page._validate_card_count("0")[0] == False
    assert page._validate_card_count("1001")[0] == False
    assert page._validate_card_count("-5")[0] == False
    assert page._validate_card_count("abc")[0] == False
    assert page._validate_card_count("20.5")[0] == False
    print("✓ Invalid card counts rejected")


def test_tags_validation():
    """Test tags validation."""
    app = QApplication.instance() or QApplication(sys.argv)

    class MockMainWindow:
        def __init__(self):
            self.config = AppConfig()
            self.config.language = "zh"

    main = MockMainWindow()
    page = ImportPage(main)

    # Test valid tags
    print("\nTesting valid tags...")
    assert page._validate_tags("ankismart")[0] == True
    assert page._validate_tags("ankismart, important")[0] == True
    assert page._validate_tags("重要, 复习")[0] == True
    assert page._validate_tags("tag_1, tag-2")[0] == True
    assert page._validate_tags("")[0] == True  # Empty is allowed
    print("✓ Valid tags passed")

    # Test invalid tags
    print("\nTesting invalid tags...")
    assert page._validate_tags("tag@123")[0] == False
    assert page._validate_tags("tag#test")[0] == False
    assert page._validate_tags("tag with spaces")[0] == False
    assert page._validate_tags("tag, @invalid")[0] == False
    print("✓ Invalid tags rejected")


def test_deck_name_validation():
    """Test deck name validation."""
    app = QApplication.instance() or QApplication(sys.argv)

    class MockMainWindow:
        def __init__(self):
            self.config = AppConfig()
            self.config.language = "zh"

    main = MockMainWindow()
    page = ImportPage(main)

    # Test valid deck names
    print("\nTesting valid deck names...")
    assert page._validate_deck_name("Default")[0] == True
    assert page._validate_deck_name("英语学习")[0] == True
    assert page._validate_deck_name("Math_2024")[0] == True
    assert page._validate_deck_name("My Deck")[0] == True
    print("✓ Valid deck names passed")

    # Test invalid deck names
    print("\nTesting invalid deck names...")
    assert page._validate_deck_name("")[0] == False
    assert page._validate_deck_name("   ")[0] == False
    assert page._validate_deck_name("deck<test>")[0] == False
    assert page._validate_deck_name("deck:test")[0] == False
    assert page._validate_deck_name("deck/test")[0] == False
    assert page._validate_deck_name("deck\\test")[0] == False
    assert page._validate_deck_name("deck|test")[0] == False
    assert page._validate_deck_name("deck?test")[0] == False
    assert page._validate_deck_name("deck*test")[0] == False
    print("✓ Invalid deck names rejected")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Input Validation")
    print("=" * 60)

    try:
        test_card_count_validation()
        test_tags_validation()
        test_deck_name_validation()

        print("\n" + "=" * 60)
        print("✓ All validation tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
