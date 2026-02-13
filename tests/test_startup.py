"""Test script to verify application can start without errors."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    print("Testing imports...")
    from ankismart.ui.import_page import ImportPage
    print("✓ import_page imported successfully")

    from ankismart.ui.workers import BatchConvertWorker
    print("✓ workers imported successfully")

    from ankismart.ui.preview_page import PreviewPage
    print("✓ preview_page imported successfully")

    from ankismart.ui.result_page import ResultPage
    print("✓ result_page imported successfully")

    from ankismart.ui.settings_page import SettingsPage
    print("✓ settings_page imported successfully")

    print("\n✓ All imports successful! No syntax errors detected.")
    sys.exit(0)

except Exception as e:
    print(f"\n✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
