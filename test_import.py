import sys
import traceback

try:
    from ankismart.ui import main
    print("Import successful!")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
