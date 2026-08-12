"""The GUI module imports cleanly and degrades on a headless host."""

import os
import sys

import pytest


@pytest.mark.skipif(sys.platform == "win32",
                    reason="Windows CI has a real display; main() would open "
                           "a window and block")
def test_import_has_no_side_effects():
    # Importing must not require tkinter or a display.
    from plaintexteditor import gui
    assert hasattr(gui, "main")
    assert hasattr(gui, "build_app")
    assert isinstance(gui.ACCENT, str) and gui.ACCENT.startswith("#")


@pytest.mark.skipif(sys.platform == "win32",
                    reason="Windows CI has a real display; main() would open "
                           "a window and block")
def test_main_headless_returns_zero(monkeypatch, home):
    from plaintexteditor import gui
    # Ensure no display is available so main() takes the headless path.
    monkeypatch.delenv("DISPLAY", raising=False)
    rc = gui.main()
    assert rc == 0


@pytest.mark.skipif(sys.platform == "win32",
                    reason="Windows CI has a real display; main() would open "
                           "a window and block")
def test_main_with_path_headless(monkeypatch, home, tmp_path):
    from plaintexteditor import gui
    monkeypatch.delenv("DISPLAY", raising=False)
    p = tmp_path / "f.txt"
    p.write_text("hi")
    assert gui.main(str(p)) == 0


def test_asset_path_none_for_missing():
    from plaintexteditor import gui
    assert gui.asset_path("definitely-not-a-real-asset.xyz") is None


def test_entry_script_routes_cli_and_gui():
    """The exe entry treats subcommands/flags as CLI and paths as GUI."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, repo)
    try:
        import plain_text_editor_app as entry
    finally:
        sys.path.remove(repo)
    assert entry.CLI_COMMANDS == {"cat", "count", "detect", "recent"}
