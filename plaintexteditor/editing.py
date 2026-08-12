r"""Pure editing logic: find & replace, go-to-line math, the F5 stamp.

Everything here works on plain strings with ``\n`` line endings (the
in-memory form produced by :mod:`plaintexteditor.textio`) and is fully unit
tested, so the GUI and CLI only translate widget indices to offsets and
back.  Offsets are 0-based; lines and columns are 1-based like the status
bar and Notepad's own "Ln 1, Col 1".
"""

from __future__ import annotations

import re
import time

from .errors import PlainTextEditorError


def _pattern(needle, match_case=False, whole_word=False):
    if not needle:
        raise PlainTextEditorError("nothing to search for")
    pat = re.escape(needle)
    if whole_word:
        # \b breaks on needles that start/end with punctuation; these
        # lookarounds define "word boundary" against [A-Za-z0-9_] instead.
        pat = r"(?<!\w)" + pat + r"(?!\w)"
    return re.compile(pat, 0 if match_case else re.IGNORECASE)


def find_all(text, needle, match_case=False, whole_word=False):
    """All ``(start, end)`` spans of *needle* in *text*, left to right."""
    return [m.span() for m in
            _pattern(needle, match_case, whole_word).finditer(text)]


def find_next(text, needle, start=0, match_case=False, whole_word=False,
              backwards=False, wrap=True):
    """The next ``(start, end)`` match from offset *start*, or ``None``.

    Forward search begins **at** *start*; backward search ends **before**
    it.  With ``wrap`` the search continues from the other end of the text,
    so exactly one full pass is made either way.
    """
    rx = _pattern(needle, match_case, whole_word)
    start = max(0, min(len(text), start))
    if backwards:
        spans = [m.span() for m in rx.finditer(text)]
        before = [s for s in spans if s[1] <= start]
        if before:
            return before[-1]
        return spans[-1] if (wrap and spans) else None
    m = rx.search(text, start)
    if m:
        return m.span()
    if wrap:
        m = rx.search(text, 0)
        if m and m.start() < start:
            return m.span()
    return None


def replace_all(text, needle, replacement, match_case=False,
                whole_word=False):
    """Replace every match literally; returns ``(new_text, count)``."""
    rx = _pattern(needle, match_case, whole_word)
    return rx.subn(lambda _m: replacement, text)


def line_col(text, offset):
    """1-based ``(line, column)`` of *offset* in *text* (clamped in range)."""
    offset = max(0, min(len(text), offset))
    line = text.count("\n", 0, offset) + 1
    nl = text.rfind("\n", 0, offset)
    return line, offset - nl if nl >= 0 else offset + 1


def line_count(text):
    """Number of lines a caret can sit on (an empty text still has line 1)."""
    return text.count("\n") + 1


def offset_of_line(text, line):
    """0-based offset of the start of 1-based *line*; raises if out of range."""
    total = line_count(text)
    if not isinstance(line, int) or line < 1 or line > total:
        raise PlainTextEditorError(
            f"line number must be between 1 and {total}")
    offset = 0
    for _ in range(line - 1):
        offset = text.index("\n", offset) + 1
    return offset


def f5_stamp(t=None):
    """The Notepad F5 time/date stamp, e.g. ``10:35 PM 8/12/2026``."""
    t = time.localtime() if t is None else t
    stamp = time.strftime("%I:%M %p %m/%d/%Y", t)
    # drop the leading zeros Notepad never shows (hour and month)
    stamp = stamp.lstrip("0")
    date = stamp.rsplit(" ", 1)
    return date[0] + " " + date[1].lstrip("0") if len(date) == 2 else stamp
