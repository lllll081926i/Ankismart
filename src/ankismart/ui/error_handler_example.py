"""Example usage of ErrorHandler in Ankismart UI pages.

This file demonstrates how to integrate the ErrorHandler into existing pages.
"""

from ankismart.ui.error_handler import ErrorHandler

# Example 1: Basic error handling in import_page.py
def example_import_page_error_handling():
    """Example of using ErrorHandler in import_page.py"""

    # Initialize error handler (typically in __init__)
    error_handler = ErrorHandler(language="zh")

    # Example: Handle file conversion error
    try:
        # ... file conversion code ...
        pass
    except Exception as e:
        # Show error with InfoBar for non-critical errors
        error_handler.show_error(
            parent=self,  # The page widget
            error=e,
            use_infobar=True,  # Use InfoBar instead of MessageBox
        )
        # Or log without showing UI
        error_handler.log_error(e, context="File conversion")


# Example 2: Error handling with action callback in result_page.py
def example_result_page_error_handling():
    """Example of using ErrorHandler in result_page.py"""

    error_handler = ErrorHandler(language="zh")

    # Example: Handle Anki connection error with action button
    try:
        # ... Anki push code ...
        pass
    except Exception as e:
        # Show error with action button to go to settings
        error_handler.show_error(
            parent=self,
            error=e,
            use_infobar=False,  # Use MessageBox for critical errors
            action_callback=lambda: self._main.switch_to_settings(),
        )


# Example 3: Replace existing QMessageBox with ErrorHandler
def example_replace_messagebox():
    """Example of replacing QMessageBox with ErrorHandler"""

    # OLD CODE:
    # QMessageBox.warning(
    #     self,
    #     "警告",
    #     "请先选择文件"
    # )

    # NEW CODE:
    error_handler = ErrorHandler(language="zh")
    error_handler.show_error(
        parent=self,
        error="请先选择文件",  # Can pass string directly
        use_infobar=True,
    )


# Example 4: Custom error classification
def example_custom_error():
    """Example of handling custom errors"""

    error_handler = ErrorHandler(language="zh")

    # The ErrorHandler will automatically classify the error
    # based on keywords in the error message
    try:
        # Simulate API key error
        raise Exception("API key is invalid or expired")
    except Exception as e:
        # Will be classified as API_KEY error automatically
        error_handler.show_error(parent=self, error=e)

    try:
        # Simulate network error
        raise Exception("Connection timeout")
    except Exception as e:
        # Will be classified as NETWORK/TIMEOUT error automatically
        error_handler.show_error(parent=self, error=e, use_infobar=True)


# Example 5: Integration pattern for existing pages
class ExamplePageWithErrorHandler:
    """Example page class showing ErrorHandler integration pattern"""

    def __init__(self, main_window):
        self._main = main_window
        # Initialize error handler with current language
        self._error_handler = ErrorHandler(language=self._main.config.language)

    def _handle_operation_error(self, error: Exception, use_infobar: bool = False):
        """Centralized error handling method"""
        self._error_handler.show_error(
            parent=self,
            error=error,
            use_infobar=use_infobar,
            action_callback=self._on_error_action if self._should_show_action(error) else None,
        )

    def _should_show_action(self, error: Exception) -> bool:
        """Determine if action button should be shown"""
        error_info = self._error_handler.classify_error(error)
        # Show action button for configuration-related errors
        return error_info.category in [
            ErrorCategory.API_KEY,
            ErrorCategory.ANKI_CONNECTION,
            ErrorCategory.LLM_PROVIDER,
        ]

    def _on_error_action(self):
        """Handle error action button click"""
        # Navigate to settings page
        self._main.switch_to_settings()

    def update_language(self, language: str):
        """Update error handler language when app language changes"""
        self._error_handler = ErrorHandler(language=language)
