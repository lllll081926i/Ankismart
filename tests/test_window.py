import sys
import traceback

try:
    from ankismart.ui.main_window import MainWindow
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    print("MainWindow created successfully!")
    window.show()
    print("Window shown successfully!")

except Exception as e:
    print(f"Error: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
