r"""Text file I/O with encoding, BOM and line-ending awareness.

The one rule: **what you open is what you save**.  A file's encoding
(UTF-8, UTF-8 with BOM, UTF-16 LE/BE, or a legacy ANSI codepage), its BOM
and its line endings (CRLF, LF or lone CR) are detected on load, carried on
the :class:`Document`, and reproduced byte-for-byte on save.  In memory the
text is always normalized to ``\n`` so the editor, search and counts work on
one canonical form.

New documents default to UTF-8 without BOM and the platform's native line
ending (CRLF on Windows, LF elsewhere) -- exactly like modern Notepad.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace as _dc_replace

from .errors import PlainTextEditorError

# BOM signatures, longest first (UTF-32 LE starts with the UTF-16 LE BOM).
_BOMS = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)

# Codec used to (de/en)code the payload after the BOM is stripped, and the
# BOM bytes written back on save when ``Document.bom`` is set.
_CODEC = {
    "utf-8": ("utf-8", b""),
    "utf-8-sig": ("utf-8", b"\xef\xbb\xbf"),
    "utf-16-le": ("utf-16-le", b"\xff\xfe"),
    "utf-16-be": ("utf-16-be", b"\xfe\xff"),
    "utf-32-le": ("utf-32-le", b"\xff\xfe\x00\x00"),
    "utf-32-be": ("utf-32-be", b"\x00\x00\xfe\xff"),
    "cp1252": ("cp1252", b""),
    "latin-1": ("latin-1", b""),
}

_ENC_LABEL = {
    "utf-8": "UTF-8",
    "utf-8-sig": "UTF-8 BOM",
    "utf-16-le": "UTF-16 LE",
    "utf-16-be": "UTF-16 BE",
    "utf-32-le": "UTF-32 LE",
    "utf-32-be": "UTF-32 BE",
    "cp1252": "ANSI",
    "latin-1": "ANSI",
}

_EOL_LABEL = {"\r\n": "CRLF", "\n": "LF", "\r": "CR"}

MAX_SIZE = 64 * 1024 * 1024      # refuse >64 MiB: not a plain-text workload


def default_eol():
    r"""The platform's native line ending: ``\r\n`` on Windows, ``\n`` else."""
    return "\r\n" if os.name == "nt" else "\n"


@dataclass
class Document:
    """Editable text plus everything needed to write it back faithfully."""

    text: str = ""
    encoding: str = "utf-8"
    eol: str = field(default_factory=default_eol)
    mixed_eol: bool = False       # file had more than one ending style

    @property
    def encoding_label(self):
        """Status-bar name for the encoding ("UTF-8", "UTF-8 BOM", ...)."""
        return _ENC_LABEL.get(self.encoding, self.encoding.upper())

    @property
    def eol_label(self):
        """Status-bar name for the line ending ("CRLF", "LF" or "CR")."""
        label = _EOL_LABEL.get(self.eol, "LF")
        return label + " (mixed)" if self.mixed_eol else label

    def copy(self):
        return _dc_replace(self)


def detect_encoding(data):
    """Return the encoding key for raw *data* (see keys of ``_CODEC``).

    BOMs win outright; otherwise strict UTF-8 is tried (covering plain
    ASCII), then Windows-1252, then Latin-1 which cannot fail.
    """
    for sig, enc in _BOMS:
        if data.startswith(sig):
            return enc
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            data.decode(_CODEC[enc][0])
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


def detect_eol(text):
    r"""Return ``(dominant_eol, mixed)`` for *text* (any form, 1 style wins).

    With no line breaks at all the platform default is reported (and
    ``mixed`` is False).  Ties go CRLF > LF > CR, matching what a Windows
    user would expect a mostly-Windows file to stay.
    """
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    styles = [n > 0 for n in (crlf, lf, cr)].count(True)
    if styles == 0:
        return default_eol(), False
    best = max((crlf, "\r\n"), (lf, "\n"), (cr, "\r"), key=lambda t: t[0])
    return best[1], styles > 1


def normalize(text):
    r"""Collapse every line-ending style in *text* to ``\n``."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def decode_bytes(data):
    """Decode raw file *data* into a :class:`Document` (text normalized)."""
    if not isinstance(data, bytes):
        raise PlainTextEditorError("decode_bytes expects bytes")
    encoding = detect_encoding(data)
    codec, bom = _CODEC[encoding]
    payload = data[len(bom):] if bom and data.startswith(bom) else data
    try:
        raw = payload.decode(codec, errors="replace")
    except LookupError:  # pragma: no cover - every codec above is stdlib
        raise PlainTextEditorError(f"unsupported encoding: {encoding}")
    eol, mixed = detect_eol(raw)
    return Document(text=normalize(raw), encoding=encoding, eol=eol,
                    mixed_eol=mixed)


def encode_document(doc):
    """Encode *doc* back to bytes: BOM + text with its own line endings."""
    if doc.encoding not in _CODEC:
        raise PlainTextEditorError(f"unsupported encoding: {doc.encoding}")
    codec, bom = _CODEC[doc.encoding]
    body = normalize(doc.text).replace("\n", doc.eol)
    try:
        return bom + body.encode(codec, errors="replace")
    except LookupError:  # pragma: no cover
        raise PlainTextEditorError(f"unsupported encoding: {doc.encoding}")


def load_file(path):
    """Read *path* into a :class:`Document`; raises on any expected failure."""
    path = os.path.expanduser(str(path))
    if not os.path.exists(path):
        raise PlainTextEditorError(f"file not found: {path}")
    if os.path.isdir(path):
        raise PlainTextEditorError(f"that is a folder, not a file: {path}")
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise PlainTextEditorError(f"cannot stat {path}: {exc}")
    if size > MAX_SIZE:
        raise PlainTextEditorError(
            f"file is {size // (1024 * 1024)} MiB — too large for a plain "
            f"text editor (limit {MAX_SIZE // (1024 * 1024)} MiB)")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise PlainTextEditorError(f"cannot read {path}: {exc}")
    return decode_bytes(data)


def save_file(path, doc):
    """Write *doc* to *path* (atomic: temp file + replace).  Returns *path*."""
    path = os.path.expanduser(str(path))
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        raise PlainTextEditorError(f"folder does not exist: {parent}")
    data = encode_document(doc)
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise PlainTextEditorError(f"cannot write {path}: {exc}")
    return path


def counts(text):
    r"""Return ``{"lines", "words", "chars"}`` for normalized *text*.

    Lines follow ``str.splitlines`` (a trailing ``\n`` does not open a new
    line); words are whitespace-separated runs; chars count everything
    including the ``\n`` separators.
    """
    return {
        "lines": len(text.splitlines()),
        "words": len(text.split()),
        "chars": len(text),
    }
