"""Encoding / BOM / line-ending detection and byte-faithful round-trips."""

import pytest

from plaintexteditor import textio
from plaintexteditor.errors import PlainTextEditorError


# ---------------------------------------------------------------------------
# encoding detection
# ---------------------------------------------------------------------------
def test_detect_plain_ascii_is_utf8():
    assert textio.detect_encoding(b"hello world") == "utf-8"


def test_detect_utf8_multibyte():
    assert textio.detect_encoding("héllo — wörld".encode("utf-8")) == "utf-8"


def test_detect_utf8_bom():
    assert textio.detect_encoding(b"\xef\xbb\xbfhi") == "utf-8-sig"


def test_detect_utf16_le_bom():
    data = "\ufeffhi".encode("utf-16-le")
    assert textio.detect_encoding(data) == "utf-16-le"


def test_detect_utf16_be_bom():
    data = "\ufeffhi".encode("utf-16-be")
    assert textio.detect_encoding(data) == "utf-16-be"


def test_detect_utf32_le_bom_not_mistaken_for_utf16():
    data = "\ufeffhi".encode("utf-32-le")
    assert textio.detect_encoding(data) == "utf-32-le"


def test_detect_ansi_fallback():
    # 0x93/0x94 are cp1252 curly quotes and invalid UTF-8
    assert textio.detect_encoding(b"\x93quoted\x94") == "cp1252"


# ---------------------------------------------------------------------------
# EOL detection
# ---------------------------------------------------------------------------
def test_detect_eol_lf():
    assert textio.detect_eol("a\nb\nc") == ("\n", False)


def test_detect_eol_crlf():
    assert textio.detect_eol("a\r\nb\r\nc") == ("\r\n", False)


def test_detect_eol_lone_cr():
    assert textio.detect_eol("a\rb\rc") == ("\r", False)


def test_detect_eol_mixed_reports_dominant():
    eol, mixed = textio.detect_eol("a\r\nb\r\nc\nd")
    assert eol == "\r\n"
    assert mixed is True


def test_detect_eol_no_breaks_uses_platform_default():
    eol, mixed = textio.detect_eol("single line")
    assert eol == textio.default_eol()
    assert mixed is False


def test_normalize_collapses_all_styles():
    assert textio.normalize("a\r\nb\rc\nd") == "a\nb\nc\nd"


# ---------------------------------------------------------------------------
# decode / encode round-trips: what you open is what you save
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("data", [
    b"plain ascii\nwith lines\n",
    "üñïçødé text\n".encode("utf-8"),
    b"\xef\xbb\xbfBOM me up\r\nline 2\r\n",
    "\ufeffutf-16 le\r\ncontent".encode("utf-16-le"),
    "\ufeffutf-16 be\ncontent".encode("utf-16-be"),
    b"cp1252 \x93quotes\x94\r\n",
    b"",
])
def test_roundtrip_bytes_exact(data):
    doc = textio.decode_bytes(data)
    assert textio.encode_document(doc) == data


def test_decode_reports_labels():
    doc = textio.decode_bytes(b"\xef\xbb\xbfhi\r\n")
    assert doc.encoding_label == "UTF-8 BOM"
    assert doc.eol_label == "CRLF"
    doc = textio.decode_bytes(b"hi\n")
    assert doc.encoding_label == "UTF-8"
    assert doc.eol_label == "LF"


def test_decode_mixed_eol_label():
    doc = textio.decode_bytes(b"a\r\nb\n")
    assert "mixed" in doc.eol_label


def test_decoded_text_is_normalized():
    doc = textio.decode_bytes(b"a\r\nb\rc\n")
    assert doc.text == "a\nb\nc\n"


def test_new_document_defaults():
    doc = textio.Document()
    assert doc.text == ""
    assert doc.encoding == "utf-8"
    assert doc.eol == textio.default_eol()


def test_eol_switch_rewrites_endings():
    doc = textio.decode_bytes(b"a\nb\n")
    doc.eol = "\r\n"
    assert textio.encode_document(doc) == b"a\r\nb\r\n"


# ---------------------------------------------------------------------------
# file I/O
# ---------------------------------------------------------------------------
def test_load_save_file_preserves_bytes(tmp_path):
    p = tmp_path / "f.txt"
    original = "\ufeffline one\r\nline two\r\n".encode("utf-16-le")
    p.write_bytes(original)
    doc = textio.load_file(str(p))
    assert doc.text == "line one\nline two\n"
    out = tmp_path / "out.txt"
    textio.save_file(str(out), doc)
    assert out.read_bytes() == original


def test_save_after_edit_keeps_encoding_and_eol(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"\xef\xbb\xbfold\r\ntext\r\n")
    doc = textio.load_file(str(p))
    doc.text = doc.text.replace("old", "new") + "extra\n"
    textio.save_file(str(p), doc)
    assert p.read_bytes() == b"\xef\xbb\xbfnew\r\ntext\r\nextra\r\n"


def test_load_missing_file_raises():
    with pytest.raises(PlainTextEditorError, match="not found"):
        textio.load_file("/no/such/file.txt")


def test_load_directory_raises(tmp_path):
    with pytest.raises(PlainTextEditorError, match="folder"):
        textio.load_file(str(tmp_path))


def test_save_into_missing_folder_raises(tmp_path):
    doc = textio.Document(text="x")
    with pytest.raises(PlainTextEditorError, match="folder does not exist"):
        textio.save_file(str(tmp_path / "nope" / "f.txt"), doc)
    # and no stray temp file was left behind
    assert list(tmp_path.iterdir()) == []


def test_save_is_atomic_no_tmp_left(tmp_path):
    p = tmp_path / "f.txt"
    textio.save_file(str(p), textio.Document(text="hello\n", eol="\n"))
    assert p.read_bytes() == b"hello\n"
    assert sorted(f.name for f in tmp_path.iterdir()) == ["f.txt"]


def test_load_refuses_oversized(tmp_path, monkeypatch):
    p = tmp_path / "big.txt"
    p.write_bytes(b"x" * 128)
    monkeypatch.setattr(textio, "MAX_SIZE", 64)
    with pytest.raises(PlainTextEditorError, match="too large"):
        textio.load_file(str(p))


# ---------------------------------------------------------------------------
# counts
# ---------------------------------------------------------------------------
def test_counts_basic():
    c = textio.counts("one two\nthree\n")
    assert c == {"lines": 2, "words": 3, "chars": 14}


def test_counts_empty():
    assert textio.counts("") == {"lines": 0, "words": 0, "chars": 0}


def test_counts_no_trailing_newline():
    c = textio.counts("a\nb")
    assert c["lines"] == 2
    assert c["chars"] == 3
