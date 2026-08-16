"""plaintexteditor -- a fast, offline Notepad-style plain text editor.

The package layers a small, well-tested API over ordinary text files:

    from plaintexteditor import textio, editing, guiconfig
    doc = textio.load_file("notes.txt")        # encoding/BOM/EOL detected
    doc.text = doc.text.replace("teh", "the")
    textio.save_file("notes.txt", doc)         # ...and preserved on save
    editing.find_all(doc.text, "the")
    textio.counts(doc.text)                    # lines / words / chars

:mod:`plaintexteditor.textio` owns encoding detection (UTF-8 default,
UTF-8/16 BOMs, ANSI fallback) and CRLF/LF/CR preservation.
:mod:`plaintexteditor.editing` owns find & replace, go-to-line math and the
Notepad-style F5 time/date stamp.  The GUI (:mod:`plaintexteditor.gui`) and
CLI (:mod:`plaintexteditor.__main__`) build on these modules and never
re-implement file logic.  Every expected failure raises
:class:`PlainTextEditorError` (and only that).

100% AI-built, open source, published on QuickOpen (quickopen.ai).
"""

from __future__ import annotations

from .errors import PlainTextEditorError

__version__ = "1.1.0"

__all__ = ["PlainTextEditorError", "textio", "editing", "guiconfig"]
