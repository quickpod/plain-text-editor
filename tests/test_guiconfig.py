"""Config store: recent files, theme, wrap/font settings -- all hermetic."""

import json
import os

from plaintexteditor import guiconfig


def test_defaults_when_no_config(home):
    cfg = guiconfig.load()
    assert cfg["theme"] == "system"        # fresh installs follow the OS
    assert cfg["recent"] == []
    assert cfg["wrap"] is True
    assert cfg["mono"] is True
    assert cfg["linenums"] is True
    assert cfg["font_size"] == guiconfig.DEFAULT_FONT
    assert cfg["last_dir"] is None


def test_corrupt_config_never_fatal(home):
    os.makedirs(guiconfig.config_dir(), exist_ok=True)
    with open(guiconfig.config_path(), "w") as fh:
        fh.write("{not json!!")
    assert guiconfig.load()["theme"] == "system"
    guiconfig.set_theme("light")            # and saving over it works
    assert guiconfig.get_theme() == "light"


def test_config_dir_honours_override(home):
    assert guiconfig.config_dir() == str(home)


def test_config_dir_xdg_on_posix(monkeypatch, tmp_path):
    if os.name == "nt":
        return  # XDG applies off Windows only
    monkeypatch.delenv("PLAINTEXTEDITOR_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert guiconfig.config_dir() == str(tmp_path / "xdg" /
                                         "plaintexteditor")


def test_theme_roundtrip(home):
    guiconfig.set_theme("light")
    assert guiconfig.get_theme() == "light"
    guiconfig.set_theme("bogus")            # ignored
    assert guiconfig.get_theme() == "light"
    guiconfig.set_theme("system")           # explicit return to OS-follow
    assert guiconfig.get_theme() == "system"


def test_wrap_mono_linenums_roundtrip(home):
    guiconfig.set_wrap(False)
    guiconfig.set_mono(False)
    guiconfig.set_linenums(False)
    assert guiconfig.get_wrap() is False
    assert guiconfig.get_mono() is False
    assert guiconfig.get_linenums() is False


def test_font_size_clamped(home):
    guiconfig.set_font_size(500)
    assert guiconfig.get_font_size() == guiconfig.MAX_FONT
    guiconfig.set_font_size(1)
    assert guiconfig.get_font_size() == guiconfig.MIN_FONT
    guiconfig.set_font_size(14)
    assert guiconfig.get_font_size() == 14


# ---------------------------------------------------------------------------
# recent files
# ---------------------------------------------------------------------------
def test_recent_most_recent_first_and_dedupe(home, tmp_path):
    a, b = str(tmp_path / "a.txt"), str(tmp_path / "b.txt")
    guiconfig.add_recent(a)
    guiconfig.add_recent(b)
    guiconfig.add_recent(a)                 # re-open moves it to the front
    recent = guiconfig.get_recent()
    assert recent[0] == guiconfig.norm_path(a)
    assert recent[1] == guiconfig.norm_path(b)
    assert len(recent) == 2


def test_recent_cap(home, tmp_path):
    for i in range(guiconfig.MAX_RECENT + 5):
        guiconfig.add_recent(str(tmp_path / f"f{i}.txt"))
    recent = guiconfig.get_recent()
    assert len(recent) == guiconfig.MAX_RECENT
    assert recent[0].endswith(f"f{guiconfig.MAX_RECENT + 4}.txt")


def test_recent_remove_and_clear(home, tmp_path):
    a, b = str(tmp_path / "a.txt"), str(tmp_path / "b.txt")
    guiconfig.add_recent(a)
    guiconfig.add_recent(b)
    guiconfig.remove_recent(a)
    assert guiconfig.get_recent() == [guiconfig.norm_path(b)]
    guiconfig.clear_recent()
    assert guiconfig.get_recent() == []


def test_recent_mixed_separators_count_as_one(home, tmp_path):
    p = str(tmp_path / "sub" / "f.txt")
    slashed = p.replace(os.sep, "/")
    backslashed = p.replace(os.sep, "\\")
    guiconfig.add_recent(slashed)
    guiconfig.add_recent(backslashed)
    assert len(guiconfig.get_recent()) == 1


def test_norm_path_handles_both_separators():
    n = guiconfig.norm_path("a/b\\c")
    assert "/" not in n or "\\" not in n   # one native separator style
    assert os.path.isabs(n)


def test_last_dir_roundtrip(home, tmp_path):
    guiconfig.set_last_dir(str(tmp_path))
    assert guiconfig.get_last_dir() == guiconfig.norm_path(str(tmp_path))
    assert guiconfig.default_open_dir() == guiconfig.norm_path(str(tmp_path))


def test_default_open_dir_falls_back(home):
    # no last_dir stored -> Documents or home, both real directories
    assert os.path.isdir(guiconfig.default_open_dir())


def test_saved_file_is_valid_json(home):
    guiconfig.set_theme("light")
    with open(guiconfig.config_path()) as fh:
        data = json.load(fh)
    assert data["theme"] == "light"
