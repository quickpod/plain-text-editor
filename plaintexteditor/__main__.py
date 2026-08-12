"""Command-line interface: ``python -m plaintexteditor <command> ...``.

Commands: ``cat`` (print a file, decoding it like the editor), ``count``
(lines / words / chars), ``detect`` (encoding, BOM and line-ending report)
and ``recent`` (list or clear the recent-files store shared with the GUI).
Every command exits cleanly with a one-line ``error: ...`` message (never a
traceback) when a :class:`PlainTextEditorError` is raised.

Opening the GUI on a file is the entry script's job
(``plain_text_editor_app.py notes.txt``); this module is pure CLI.
"""

from __future__ import annotations

import argparse
import sys

from . import guiconfig, textio
from .errors import PlainTextEditorError


# ---------------------------------------------------------------------------
# command handlers
# ---------------------------------------------------------------------------
def cmd_cat(a):
    doc = textio.load_file(a.file)
    if a.number:
        for i, line in enumerate(doc.text.splitlines(), 1):
            print(f"{i:6}\t{line}")
    else:
        # end="" : the document's own trailing newline (or lack of one) wins
        print(doc.text, end="")
        if doc.text and not doc.text.endswith("\n"):
            print()


def cmd_count(a):
    width = max((len(p) for p in a.files), default=0)
    for path in a.files:
        doc = textio.load_file(path)
        c = textio.counts(doc.text)
        print(f"{path.ljust(width)}  lines={c['lines']}  "
              f"words={c['words']}  chars={c['chars']}")


def cmd_detect(a):
    width = max((len(p) for p in a.files), default=0)
    for path in a.files:
        doc = textio.load_file(path)
        print(f"{path.ljust(width)}  encoding={doc.encoding_label}  "
              f"line-endings={doc.eol_label}")


def cmd_recent(a):
    if a.clear:
        guiconfig.clear_recent()
        print("recent files cleared")
        return
    recent = guiconfig.get_recent()
    if not recent:
        print("(no recent files)")
        return
    for path in recent:
        print(path)


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="plaintexteditor",
        description="Plain Text Editor — Notepad-style plain text tools. "
                    "Run the app with no arguments (or with a file path) "
                    "for the GUI.")
    sub = p.add_subparsers(dest="command")

    def add(name, help_text, func):
        s = sub.add_parser(name, help=help_text)
        s.set_defaults(func=func)
        return s

    s = add("cat", "Print a text file (decoded like the editor)", cmd_cat)
    s.add_argument("file")
    s.add_argument("-n", "--number", action="store_true",
                   help="number the output lines")

    s = add("count", "Count lines, words and characters", cmd_count)
    s.add_argument("files", nargs="+", metavar="FILE")

    s = add("detect", "Report encoding, BOM and line endings", cmd_detect)
    s.add_argument("files", nargs="+", metavar="FILE")

    s = add("recent", "List recently opened files", cmd_recent)
    s.add_argument("--clear", action="store_true",
                   help="empty the recent-files list")

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        args.func(args)
    except PlainTextEditorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
