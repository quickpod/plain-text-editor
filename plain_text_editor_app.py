#!/usr/bin/env python3
r"""Plain Text Editor entry point (built into PlainTextEditor.exe).

GUI with no args; ``plain_text_editor_app.py notes.txt`` opens *notes.txt*
in the GUI (this is what double-click / "Open with" / drag-onto-the-exe
produce); CLI subcommands (``cat``, ``count``, ``detect``, ``recent``) and
flags route to ``plaintexteditor.__main__``.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Single-instance marker: the installer's AppMutex checks this to warn the
# user to close the app before install/uninstall. Harmless off Windows.
if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.kernel32.CreateMutexW(None, False, "QuickOpen.PlainTextEditor")
    except Exception:
        pass

CLI_COMMANDS = {"cat", "count", "detect", "recent"}


def main():
    argv = sys.argv[1:]
    if argv and (argv[0] in CLI_COMMANDS or argv[0].startswith("-")):
        from plaintexteditor import __main__ as cli
        return cli.main(argv)
    from plaintexteditor import gui
    # A bare path argument means "open this file in the editor".
    return gui.main(argv[0] if argv else None) or 0


if __name__ == '__main__':
    sys.exit(main() or 0)
