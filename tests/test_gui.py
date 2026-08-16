"""GUI tests for the 1.1.0 Aura layout-language rework (tabs + gutter).

Pure helpers run anywhere; the App tests need a display (run the suite under
``xvfb-run -a python3 -m pytest``) and are skipped headless, mirroring the
house pattern.  Everything is hermetic: PLAINTEXTEDITOR_HOME lives in the
test's tmp dir.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plaintexteditor import gui, guiconfig  # noqa: E402


# ---------------------------------------------------------------------------
# pure helpers (no display needed)
# ---------------------------------------------------------------------------
def test_fuzzy_match():
    assert gui.fuzzy_match("", "Anything")
    assert gui.fuzzy_match("todo", "my-todo.txt")
    assert gui.fuzzy_match("mtt", "my-todo.txt")       # subsequence
    assert not gui.fuzzy_match("xyz", "my-todo.txt")


def test_shorten_path():
    assert gui.shorten_path("") == ""
    short = os.path.join("a", "b.txt")
    assert gui.shorten_path(short) == short
    long = os.sep.join(["very"] * 30 + ["leaf.txt"])
    out = gui.shorten_path(long, 46)
    assert len(out) <= 60 and out.endswith("leaf.txt") and "…" in out


# ---------------------------------------------------------------------------
# the App under Xvfb
# ---------------------------------------------------------------------------
def _display():
    return bool(os.environ.get("DISPLAY")) and os.name != "nt"


needs_display = pytest.mark.skipif(not _display(),
                                   reason="needs a display (xvfb-run)")


@pytest.fixture()
def app(home):
    guiconfig.set_theme("dark")      # deterministic; no OS follow in tests
    App = gui.build_app()
    a = App()
    a.update()
    yield a
    try:
        a.destroy()
    except Exception:
        pass


@needs_display
def test_app_starts_with_one_untitled_tab(app):
    assert len(app.tabs) == 1
    tab = app._cur()
    assert tab is not None and tab.path is None
    assert tab.pristine()
    assert "Untitled" in app.nb.tab(tab.frame, "text")


@needs_display
def test_new_file_adds_tabs_and_close_restores_empty_state(app):
    app._new_file()
    app.update()
    assert len(app.tabs) == 2
    app._close_current()
    app._close_current()
    app.update()
    assert len(app.tabs) == 0
    # the Aura empty state is showing instead of the notebook
    assert app.empty.winfo_manager() == "place"
    app._new_file()
    app.update()
    assert app.empty.winfo_manager() == ""


@needs_display
def test_open_save_roundtrip_and_recent(app, tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("hello\nworld\n", encoding="utf-8")
    app._open_path(str(p))
    app.update()
    tab = app._cur()
    assert tab.path == guiconfig.norm_path(str(p))
    assert tab.get_text() == "hello\nworld\n"
    # opened into the pristine Untitled tab, not a second tab
    assert len(app.tabs) == 1
    # dirty marker + save
    tab.text.insert("end", "more")
    app.update()
    assert tab.dirty
    assert app._save()
    assert not tab.dirty
    assert p.read_text(encoding="utf-8").endswith("more")
    assert guiconfig.get_recent()[0] == guiconfig.norm_path(str(p))


@needs_display
def test_open_same_file_twice_focuses_existing_tab(app, tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("x", encoding="utf-8")
    app._open_path(str(p))
    app._new_file()
    app.update()
    assert len(app.tabs) == 2
    app._open_path(str(p))
    app.update()
    assert len(app.tabs) == 2                  # no duplicate tab
    assert app._cur().path == guiconfig.norm_path(str(p))


@needs_display
def test_line_operations(app):
    tab = app._cur()
    tab.text.insert("1.0", "a\nb\nc")
    tab.text.mark_set("insert", "2.0")
    app._duplicate_line()
    assert tab.get_text() == "a\nb\nb\nc"
    app._delete_line()
    assert tab.get_text() == "a\nb\nc"
    tab.text.mark_set("insert", "1.0")
    app._move_line(+1)
    assert tab.get_text() == "b\na\nc"
    tab.text.delete("1.0", "end")
    tab.text.insert("1.0", "x  \ny\t")
    app._trim_trailing()
    assert tab.get_text() == "x\ny"


@needs_display
def test_find_match_count_and_replace_all(app):
    tab = app._cur()
    tab.text.insert("1.0", "cat dog cat bird cat")
    app._show_find()
    app.update()
    app.find_entry.insert(0, "cat")
    app._update_match_count()
    assert "3 match" in app._match_lbl.cget("text")
    app.replace_entry.insert(0, "cow")
    app._replace_all()
    assert tab.get_text() == "cow dog cow bird cow"


@needs_display
def test_eol_and_encoding_conversion(app, tmp_path):
    p = tmp_path / "eol.txt"
    p.write_bytes(b"one\r\ntwo\r\n")
    app._open_path(str(p))
    tab = app._cur()
    assert tab.doc.eol == "\r\n"
    app._set_eol("\n")
    assert tab.doc.eol == "\n" and tab.dirty
    app._set_encoding("utf-8-sig")
    assert tab.doc.encoding == "utf-8-sig"
    assert app._save()
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")     # BOM written
    assert b"\r\n" not in raw                  # converted to LF


@needs_display
def test_zoom_applies_to_all_tabs(app):
    app._new_file()
    before = app._font_size
    app._zoom(+1)
    assert app._font_size == before + 1
    for t in app.tabs:
        assert str(before + 1) in str(t.text.cget("font"))
    app._zoom(0)
    assert app._font_size == guiconfig.DEFAULT_FONT


@needs_display
def test_theme_flip_smoke(app):
    app.set_theme("light")
    app.update()
    app.set_theme("dark")
    app.update()
    assert app.theme == "dark"


@needs_display
def test_layout_language_surfaces_exist(app):
    # toolbar with a primary action, sidebar library, status bar strip
    assert hasattr(app, "nb") and hasattr(app, "empty")
    assert hasattr(app, "_recent_scroll")
    assert app._pos_lbl.cget("text").startswith("Ln")
    # sections registered with the AuraApp shell
    assert set(app._sections) >= {"editor", "about"}
