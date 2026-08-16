"""Find & replace, go-to-line math and the F5 stamp -- pure logic."""

import time

import pytest

from plaintexteditor import editing
from plaintexteditor.errors import PlainTextEditorError


TEXT = "The cat sat.\nThe CAT catalog.\ncat\n"


# ---------------------------------------------------------------------------
# find_all
# ---------------------------------------------------------------------------
def test_find_all_case_insensitive_by_default():
    spans = editing.find_all(TEXT, "cat")
    assert len(spans) == 4          # cat, CAT, CATalog's "cat", final cat


def test_find_all_match_case():
    spans = editing.find_all(TEXT, "cat", match_case=True)
    assert len(spans) == 3
    assert all(TEXT[s:e] == "cat" for s, e in spans)


def test_find_all_whole_word():
    spans = editing.find_all(TEXT, "cat", whole_word=True)
    assert len(spans) == 3          # "catalog" excluded


def test_find_all_whole_word_with_punctuation_needle():
    spans = editing.find_all("a+b then a+b.", "a+b", whole_word=True)
    assert len(spans) == 2


def test_find_all_no_match():
    assert editing.find_all(TEXT, "dog") == []


def test_find_empty_needle_raises():
    with pytest.raises(PlainTextEditorError, match="nothing to search"):
        editing.find_all(TEXT, "")


def test_find_needle_is_literal_not_regex():
    assert editing.find_all("a.c abc", "a.c") == [(0, 3)]


# ---------------------------------------------------------------------------
# find_next
# ---------------------------------------------------------------------------
def test_find_next_forward_from_offset():
    first = editing.find_next(TEXT, "cat", start=0, match_case=True)
    second = editing.find_next(TEXT, "cat", start=first[1], match_case=True)
    assert first == (4, 7)
    assert second[0] > first[0]


def test_find_next_wraps_around():
    spans = editing.find_all(TEXT, "cat", match_case=True)
    last = spans[-1]
    wrapped = editing.find_next(TEXT, "cat", start=last[1], match_case=True)
    assert wrapped == spans[0]


def test_find_next_no_wrap_returns_none():
    spans = editing.find_all(TEXT, "cat", match_case=True)
    assert editing.find_next(TEXT, "cat", start=spans[-1][1],
                             match_case=True, wrap=False) is None


def test_find_next_backwards():
    spans = editing.find_all(TEXT, "cat", match_case=True)
    prev = editing.find_next(TEXT, "cat", start=spans[1][0],
                             match_case=True, backwards=True)
    assert prev == spans[0]


def test_find_next_backwards_wraps_to_last():
    spans = editing.find_all(TEXT, "cat", match_case=True)
    prev = editing.find_next(TEXT, "cat", start=0, match_case=True,
                             backwards=True)
    assert prev == spans[-1]


# ---------------------------------------------------------------------------
# replace_all
# ---------------------------------------------------------------------------
def test_replace_all_counts_and_replaces():
    out, n = editing.replace_all("aaa", "a", "b")
    assert (out, n) == ("bbb", 3)


def test_replace_all_case_insensitive():
    out, n = editing.replace_all("Cat cat CAT", "cat", "dog")
    assert (out, n) == ("dog dog dog", 3)


def test_replace_all_whole_word_only():
    out, n = editing.replace_all("cat catalog cat", "cat", "dog",
                                 whole_word=True)
    assert (out, n) == ("dog catalog dog", 2)


def test_replace_all_replacement_is_literal():
    out, n = editing.replace_all("aaa", "a", r"\1$&")
    assert n == 3
    assert out == r"\1$&" * 3


def test_replace_all_no_match():
    out, n = editing.replace_all("abc", "zzz", "x")
    assert (out, n) == ("abc", 0)


# ---------------------------------------------------------------------------
# line/column math
# ---------------------------------------------------------------------------
def test_line_col_start():
    assert editing.line_col("abc\ndef", 0) == (1, 1)


def test_line_col_second_line():
    assert editing.line_col("abc\ndef", 4) == (2, 1)
    assert editing.line_col("abc\ndef", 6) == (2, 3)


def test_line_col_clamps():
    assert editing.line_col("ab", 99) == (1, 3)


def test_line_count():
    assert editing.line_count("") == 1
    assert editing.line_count("a\nb") == 2
    assert editing.line_count("a\nb\n") == 3   # caret can sit on line 3


def test_offset_of_line():
    text = "aa\nbbb\nc"
    assert editing.offset_of_line(text, 1) == 0
    assert editing.offset_of_line(text, 2) == 3
    assert editing.offset_of_line(text, 3) == 7


def test_offset_of_line_out_of_range():
    with pytest.raises(PlainTextEditorError, match="between 1 and"):
        editing.offset_of_line("a\nb", 5)
    with pytest.raises(PlainTextEditorError):
        editing.offset_of_line("a\nb", 0)


def test_offset_and_line_col_are_inverse():
    text = "one\ntwo\nthree\n"
    for line in range(1, editing.line_count(text) + 1):
        off = editing.offset_of_line(text, line)
        assert editing.line_col(text, off) == (line, 1)


# ---------------------------------------------------------------------------
# F5 stamp
# ---------------------------------------------------------------------------
def test_duplicate_line():
    assert editing.duplicate_line("a\nb\nc", 2) == "a\nb\nb\nc"
    assert editing.duplicate_line("only", 1) == "only\nonly"
    assert editing.duplicate_line("a\nb\n", 2) == "a\nb\nb\n"
    with pytest.raises(PlainTextEditorError):
        editing.duplicate_line("a\nb", 3)


def test_delete_line():
    assert editing.delete_line("a\nb\nc", 2) == "a\nc"
    assert editing.delete_line("only", 1) == ""
    assert editing.delete_line("a\nb\n", 2) == "a\n"
    with pytest.raises(PlainTextEditorError):
        editing.delete_line("a", 2)


def test_move_line():
    assert editing.move_line("a\nb\nc", 1, +1) == ("b\na\nc", 2)
    assert editing.move_line("a\nb\nc", 3, -1) == ("a\nc\nb", 2)
    # clamped at the ends: no-op, never an error
    assert editing.move_line("a\nb", 1, -1) == ("a\nb", 1)
    assert editing.move_line("a\nb", 2, +1) == ("a\nb", 2)
    assert editing.move_line("a\nb\nc\n", 1, +1) == ("b\na\nc\n", 2)
    with pytest.raises(PlainTextEditorError):
        editing.move_line("a", 5, 1)


def test_trim_trailing_whitespace():
    text = "a  \nb\t\nc\nno-change"
    out, changed = editing.trim_trailing_whitespace(text)
    assert out == "a\nb\nc\nno-change"
    assert changed == 2
    out2, changed2 = editing.trim_trailing_whitespace(out)
    assert (out2, changed2) == (out, 0)
    # a trailing newline survives
    assert editing.trim_trailing_whitespace("x \n")[0] == "x\n"


def test_f5_stamp_format():
    t = time.struct_time((2026, 8, 5, 22, 35, 0, 2, 217, 0))
    assert editing.f5_stamp(t) == "10:35 PM 8/05/2026"


def test_f5_stamp_strips_leading_zero_hour():
    t = time.struct_time((2026, 12, 31, 9, 5, 0, 3, 365, 0))
    assert editing.f5_stamp(t) == "9:05 AM 12/31/2026"


def test_f5_stamp_now_is_string():
    stamp = editing.f5_stamp()
    assert ("AM" in stamp) or ("PM" in stamp)
