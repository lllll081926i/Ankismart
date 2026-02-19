from __future__ import annotations


def test_ui_main_module_importable() -> None:
    from ankismart.ui import main

    assert main is not None
