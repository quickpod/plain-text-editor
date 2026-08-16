r"""Tiny JSON-backed config + per-OS app directories for Plain Text Editor.

Stores the theme preference ("system" follows the OS Aura Dark/Light live;
"light"/"dark" are explicit overrides), the recent-files list, the word
wrap / monospace / line-number toggles, the font size and the last folder
used by the Open/Save dialogs.  On Windows the file lives at
``%LOCALAPPDATA%\PlainTextEditor\config.json``; elsewhere it follows XDG
(``$XDG_CONFIG_HOME/plaintexteditor/config.json``, defaulting to
``~/.config/plaintexteditor/config.json``).  Every function is defensive --
a corrupt or unreadable config must never stop the app (or the CLI) from
starting.

Paths are stored normalized for the current OS, so a file dragged in with
backslashes and the same file opened with forward slashes count as one
recent entry.
"""

from __future__ import annotations

import json
import os

APP_DIRNAME = "PlainTextEditor"
CONFIG_NAME = "config.json"
MAX_RECENT = 10
VALID_THEMES = ("system", "light", "dark")
MIN_FONT, MAX_FONT, DEFAULT_FONT = 6, 72, 12


def config_dir():
    r"""Directory that holds the config file (created on demand).

    ``%LOCALAPPDATA%\PlainTextEditor`` on Windows, XDG config dir otherwise.
    Honours ``PLAINTEXTEDITOR_HOME`` when set so tests can redirect
    everything to a tmp dir.
    """
    override = os.environ.get("PLAINTEXTEDITOR_HOME")
    if override:
        return override
    local = os.environ.get("LOCALAPPDATA")
    if local and os.name == "nt":
        return os.path.join(local, APP_DIRNAME)
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config")
    return os.path.join(xdg, APP_DIRNAME.lower())


def config_path():
    return os.path.join(config_dir(), CONFIG_NAME)


def norm_path(path):
    """Absolute, OS-native form of *path*; accepts / and \\ separators."""
    if not path:
        return path
    p = str(path).replace("\\", os.sep).replace("/", os.sep)
    try:
        return os.path.abspath(os.path.expanduser(p))
    except Exception:
        return p


def _same(a, b):
    a, b = norm_path(a), norm_path(b)
    if os.name == "nt":  # Windows paths are case-insensitive
        return a.lower() == b.lower()
    return a == b


def default_open_dir():
    """Folder the Open/Save dialogs should start in.

    The last folder used wins if it still exists, then the per-user
    Documents folder, then home.
    """
    last = load().get("last_dir")
    if last and os.path.isdir(last):
        return last
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    return docs if os.path.isdir(docs) else os.path.expanduser("~")


def _defaults():
    return {"theme": "system", "recent": [], "wrap": True, "mono": True,
            "linenums": True, "font_size": DEFAULT_FONT, "last_dir": None}


def load():
    """Return the config dict, always with the expected keys present."""
    cfg = _defaults()
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            if data.get("theme") in VALID_THEMES:
                cfg["theme"] = data["theme"]
            recent = data.get("recent")
            if isinstance(recent, list):
                cfg["recent"] = [p for p in recent
                                 if isinstance(p, str)][:MAX_RECENT]
            for key in ("wrap", "mono", "linenums"):
                if isinstance(data.get(key), bool):
                    cfg[key] = data[key]
            size = data.get("font_size")
            if isinstance(size, int) and MIN_FONT <= size <= MAX_FONT:
                cfg["font_size"] = size
            if isinstance(data.get("last_dir"), str):
                cfg["last_dir"] = data["last_dir"]
    except Exception:
        pass  # missing/corrupt -> defaults; never fatal
    return cfg


def save(cfg):
    """Persist *cfg* (best-effort; failures are swallowed)."""
    try:
        os.makedirs(config_dir(), exist_ok=True)
        size = cfg.get("font_size")
        clean = {
            "theme": cfg.get("theme")
            if cfg.get("theme") in VALID_THEMES else "system",
            "recent": [p for p in cfg.get("recent", [])
                       if isinstance(p, str)][:MAX_RECENT],
            "wrap": bool(cfg.get("wrap", True)),
            "mono": bool(cfg.get("mono", True)),
            "linenums": bool(cfg.get("linenums", True)),
            "font_size": size if isinstance(size, int)
            and MIN_FONT <= size <= MAX_FONT else DEFAULT_FONT,
            "last_dir": cfg.get("last_dir")
            if isinstance(cfg.get("last_dir"), str) else None,
        }
        tmp = config_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(clean, fh, indent=2)
        os.replace(tmp, config_path())
    except Exception:
        pass


def _get(key):
    return load().get(key)


def _set(key, value):
    cfg = load()
    cfg[key] = value
    save(cfg)


def get_theme():
    """The persisted theme preference: "system" (follow the OS Aura
    Dark/Light live), "light" or "dark"."""
    return _get("theme")


def set_theme(theme):
    if theme in VALID_THEMES:
        _set("theme", theme)


def get_linenums():
    return bool(_get("linenums"))


def set_linenums(on):
    _set("linenums", bool(on))


def get_wrap():
    return bool(_get("wrap"))


def set_wrap(on):
    _set("wrap", bool(on))


def get_mono():
    return bool(_get("mono"))


def set_mono(on):
    _set("mono", bool(on))


def get_font_size():
    return _get("font_size")


def set_font_size(size):
    if isinstance(size, int):
        _set("font_size", max(MIN_FONT, min(MAX_FONT, size)))


def get_last_dir():
    return _get("last_dir")


def set_last_dir(path):
    if path:
        _set("last_dir", norm_path(path))


def get_recent():
    """Most-recent-first list of recently opened files."""
    return load().get("recent", [])


def add_recent(path):
    """Push *path* to the front of the recent-files list (deduplicated)."""
    if not path:
        return
    ap = norm_path(path)
    cfg = load()
    recent = [p for p in cfg.get("recent", []) if not _same(p, ap)]
    recent.insert(0, ap)
    cfg["recent"] = recent[:MAX_RECENT]
    save(cfg)


def remove_recent(path):
    """Drop *path* from the recent list (e.g. after a failed open)."""
    cfg = load()
    cfg["recent"] = [p for p in cfg.get("recent", []) if not _same(p, path)]
    save(cfg)


def clear_recent():
    cfg = load()
    cfg["recent"] = []
    save(cfg)
