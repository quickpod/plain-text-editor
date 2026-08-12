"""The single exception type raised by the plaintexteditor package."""

from __future__ import annotations


class PlainTextEditorError(Exception):
    """Any expected failure (bad path, unreadable file, bad argument).

    The CLI and GUI catch this one type and show its message; anything else
    is a genuine bug and is allowed to surface.
    """
