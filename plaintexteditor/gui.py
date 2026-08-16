#!/usr/bin/env python3
r"""Plain Text Editor -- an Aura (QuickOpen design system) GUI over the
``plaintexteditor`` core.

Layout per branding/aura-design-system/APP-LAYOUT-LANGUAGE.md, benchmarked
against **Notepad++** (adopting its daily-use layout, refusing its pro tail):

  * **Sidebar** (AuraApp) -- Editor / About nav, plus a *Recent files*
    library in ``sidebar_body``: one click re-opens a file.  Collapsible
    with Ctrl+\.
  * **Toolbar** -- "+ New file" (primary), Open…, Save, with the Word wrap /
    Monospace view switches on the right.
  * **Content** -- a **multi-tab** workspace (the defining Notepad++
    feature): one tab per file with its own undo history, a line-number
    gutter, current-line highlight, and a slide-in Find & Replace bar with a
    live match count.  Closing the last tab shows an Aura empty state.
  * **Status bar** -- Ln/Col, selection size, chars/words, encoding, line
    endings and zoom; errors surface here, never as raw dialogs.

Daily-use features from the benchmark: tabs (Ctrl+W close, Ctrl+Tab cycle,
right-click tab menu), duplicate / delete / move line (Ctrl+D,
Ctrl+Shift+K, Ctrl+Shift+Up/Down), trim trailing whitespace, EOL conversion
(LF/CRLF) and encoding choice (UTF-8 / UTF-8 BOM / UTF-16 LE / ANSI) from
the Format menu, Ctrl+P quick switcher over open tabs + recent files, and a
Ctrl+, Settings dialog (theme System/Light/Dark, font size, editor
defaults).  Deliberately refused pro tail: syntax highlighting, macros,
plugins, split views, column mode, hidden unsaved sessions -- your text
lives in files you own, nothing else.

Design goals baked in here (mirrors the QuickOpen house style):
  * built on the vendored ``plaintexteditor/aura.py`` design system for the
    chrome -- but each editing surface itself is a plain ``tk.Text``:
    native selection and cursor behavior, no styling games with your text.
  * Importing this module does nothing.  Only :func:`main` builds a root
    window, and it degrades gracefully (prints a note, returns 0) with no
    display or with customtkinter missing.
  * Frozen-exe safe: bundled assets are resolved via ``sys._MEIPASS`` / the
    exe directory when ``sys.frozen`` is set -- never ``__file__``.
  * Every file operation calls the tested core (textio/editing/guiconfig);
    encoding, BOM and CRLF/LF endings are preserved on save.  Failures show
    in the Aura status bar -- never a raw traceback.

100% AI-built, open source, published on QuickOpen (quickopen.ai).
"""

from __future__ import annotations

import os
import sys

# NOTE: tkinter/customtkinter are imported lazily inside main()/build_app so
# that merely importing this module (packaging, headless CI) never fails.

APP_NAME = "Plain Text Editor"
APP_VERSION = "1.1.0"
WINDOW_TITLE = "Plain Text Editor — by QuickOpen (quickopen.ai)"
PROJECT_URL = "https://quickopen.ai"
ACCENT = "#5b86f7"      # Aura brand accent

# Format-menu choices -> textio Document fields
EOL_CHOICES = (("LF  (Unix / macOS)", "\n"), ("CRLF  (Windows)", "\r\n"))
ENC_CHOICES = (("UTF-8", "utf-8"), ("UTF-8 with BOM", "utf-8-sig"),
               ("UTF-16 LE", "utf-16-le"), ("ANSI", "cp1252"))


# ---------------------------------------------------------------------------
# Asset / frozen handling
# ---------------------------------------------------------------------------
def asset_path(name):
    """Locate a bundled asset from source OR a PyInstaller one-file build.

    For a frozen exe we look only at ``sys._MEIPASS`` and the executable's
    own directory (never ``__file__``).  From source we also consult the
    package dir, the repo root and the CWD.  Returns an absolute path or
    ``None``.
    """
    roots = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(meipass)
        roots.append(os.path.dirname(os.path.abspath(sys.executable)))
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        roots += [here, os.path.dirname(here), os.getcwd()]
    for root in roots:
        candidate = os.path.join(root, name)
        if os.path.exists(candidate):
            return candidate
    return None


def open_with_default_app(path):
    """Open a file/URL with the OS default application, guarded."""
    try:
        if hasattr(os, "startfile"):
            os.startfile(path)                # noqa: S606 - intended
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", path])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def fuzzy_match(query, name):
    """True when *query* matches *name* (substring first, then subsequence)."""
    q = (query or "").casefold().strip()
    if not q:
        return True
    n = (name or "").casefold()
    if q in n:
        return True
    it = iter(n)
    return all(ch in it for ch in q)


def shorten_path(path, limit=46):
    """Middle-truncate *path* for captions/menus ('/home/…/notes/todo.txt')."""
    if not path or len(path) <= limit:
        return path or ""
    head, tail = os.path.dirname(path), os.path.basename(path)
    keep = max(4, limit - len(tail) - 3)
    return head[:keep] + "…" + os.sep + tail


# ---------------------------------------------------------------------------
# The app (built lazily; tkinter/customtkinter imported only inside build_app)
# ---------------------------------------------------------------------------
def build_app():
    """Construct and return the App class bound to live GUI imports.

    Kept inside a function so this module imports cleanly without a display
    (and without customtkinter installed).
    """
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
    import customtkinter as ctk

    from . import aura, editing, guiconfig, textio
    from .errors import PlainTextEditorError

    # Readable families in both worlds; DejaVu is the Linux fallback so the
    # editor never renders as tofu under Xvfb.
    UI_FAMILY = "Segoe UI" if os.name == "nt" else "DejaVu Sans"
    MONO_FAMILY = "Consolas" if os.name == "nt" else "DejaVu Sans Mono"

    FILETYPES = [("Text files", "*.txt"), ("Log files", "*.log"),
                 ("All files", "*.*")]

    # (light, dark) palette pairs so CustomTkinter auto-flips these frames
    # with the theme.
    pair = aura._pair

    GUTTER_W = 48

    class EditorTab:
        """One open document: notebook page + gutter + tk.Text + scrollbars.

        Each tab owns its Document (encoding/EOL metadata), its dirty flag
        and its own undo stack -- exactly like a Notepad++ tab.
        """

        _seq = 0

        def __init__(self, app, doc=None, path=None):
            EditorTab._seq += 1
            self.app = app
            self.doc = doc or textio.Document()
            self.path = path
            self.dirty = False
            self.untitled_n = EditorTab._seq
            self._gutter_job = None

            self.frame = ttk.Frame(app.nb)
            surface = ctk.CTkFrame(self.frame, fg_color=pair("field"),
                                   corner_radius=10, border_width=1,
                                   border_color=pair("border"))
            surface.pack(fill="both", expand=True)
            surface.grid_columnconfigure(1, weight=1)
            surface.grid_rowconfigure(0, weight=1)
            self.surface = surface

            self.gutter = tk.Canvas(surface, width=GUTTER_W,
                                    highlightthickness=0, borderwidth=0)
            self.gutter.grid(row=0, column=0, sticky="ns", padx=(8, 0),
                             pady=6)
            self.text = tk.Text(
                surface, undo=True, autoseparators=True, maxundo=-1,
                wrap="word" if app._wrap else "none",
                relief="flat", borderwidth=0, highlightthickness=0,
                padx=8, pady=4, tabs=("1c",))
            self.ysb = aura.AuraScrollbar(surface, command=self.text.yview)
            self.xsb = aura.AuraScrollbar(surface, orientation="horizontal",
                                          command=self.text.xview)
            self.text.configure(yscrollcommand=self._on_yscroll,
                                xscrollcommand=self.xsb.set)
            self.text.grid(row=0, column=1, sticky="nsew", pady=6)
            self.ysb.grid(row=0, column=2, sticky="ns", padx=(0, 4), pady=6)
            self.xsb.grid(row=1, column=1, sticky="ew", pady=(0, 4))
            if app._wrap:
                self.xsb.grid_remove()
            aura.track(self.text, "text")

            self.set_text(self.doc.text)
            self.apply_font()
            self.style()
            self.text.edit_modified(False)
            self.text.bind("<<Modified>>", self._on_modified)
            for seq in ("<KeyRelease>", "<ButtonRelease-1>"):
                self.text.bind(seq, lambda _e: self.app._on_caret_moved(),
                               add="+")
            self.text.bind("<Configure>",
                           lambda _e: self.schedule_gutter(), add="+")
            app._bind_text_keys(self.text)

        # ---- naming
        def display_name(self):
            if self.path:
                return os.path.basename(self.path)
            n = self.untitled_n
            return "Untitled" if n == 1 else f"Untitled {n}"

        def label(self):
            return ("• " if self.dirty else "") + self.display_name()

        def pristine(self):
            """True for an empty, unsaved, untouched Untitled tab."""
            return (self.path is None and not self.dirty
                    and not self.text.get("1.0", "end-1c"))

        # ---- text plumbing
        def get_text(self):
            return self.text.get("1.0", "end-1c")

        def set_text(self, value):
            self.text.delete("1.0", "end")
            self.text.insert("1.0", value)
            self.text.edit_reset()
            self.text.edit_modified(False)
            self.dirty = False
            self.text.mark_set("insert", "1.0")
            self.text.see("insert")
            self.schedule_gutter()

        def _on_modified(self, _e=None):
            if self.text.edit_modified():
                self.text.edit_modified(False)
                if not self.dirty:
                    self.dirty = True
                    self.app._refresh_tab_label(self)
            self.schedule_gutter()
            self.app._on_caret_moved()

        # ---- gutter + current-line highlight
        def _on_yscroll(self, first, last):
            self.ysb.set(first, last)
            self.schedule_gutter()

        def schedule_gutter(self):
            if self._gutter_job is None:
                try:
                    self._gutter_job = self.text.after(15, self.redraw_gutter)
                except Exception:
                    pass

        def redraw_gutter(self):
            self._gutter_job = None
            g = self.gutter
            try:
                g.delete("all")
                if not self.app._linenums:
                    return
                fg = aura.P("faint")
                cur_fg = aura.P("muted")
                curline = self.text.index("insert").split(".")[0]
                fnt = self.app._gutter_font
                i = self.text.index("@0,0 linestart")
                while True:
                    d = self.text.dlineinfo(i)
                    if d is None:
                        break
                    num = i.split(".")[0]
                    g.create_text(GUTTER_W - 8, d[1] + 2, anchor="ne",
                                  text=num, font=fnt,
                                  fill=cur_fg if num == curline else fg)
                    nxt = self.text.index(f"{num}.0 +1line")
                    if nxt == i or int(nxt.split(".")[0]) <= int(num):
                        break
                    i = nxt
            except Exception:
                pass

        def update_curline(self):
            t = self.text
            try:
                t.tag_remove("curline", "1.0", "end")
                t.tag_add("curline", "insert linestart",
                          "insert lineend+1c")
                t.tag_lower("curline")
            except Exception:
                pass

        # ---- styling (called on build and on every theme flip)
        def style(self):
            try:
                self.text.tag_configure("curline",
                                        background=aura.P("surface"))
                self.gutter.configure(bg=aura.P("field"))
                self.update_curline()
                self.schedule_gutter()
            except Exception:
                pass

        def apply_font(self):
            family = MONO_FAMILY if self.app._mono else UI_FAMILY
            self.text.configure(font=(family, self.app._font_size))
            self.schedule_gutter()

        def apply_wrap(self):
            self.text.configure(wrap="word" if self.app._wrap else "none")
            if self.app._wrap:
                self.xsb.grid_remove()
            else:
                self.xsb.grid()
            self.schedule_gutter()

        def show_gutter(self, on):
            if on:
                self.gutter.grid()
            else:
                self.gutter.grid_remove()
            self.schedule_gutter()

    class App(aura.AuraApp):

        def __init__(self, path=None):
            super().__init__(
                title=WINDOW_TITLE, app_name=APP_NAME, accent=ACCENT,
                theme=guiconfig.get_theme(),
                icon_png=asset_path("plain-text-editor.png"),
                version=APP_VERSION, tagline="plain text, kept plain",
                on_theme_change=guiconfig.set_theme,
                size=(1220, 740), min_size=(940, 560))

            self.tabs = []
            self._img_refs = []
            self._font_size = guiconfig.get_font_size()
            self._wrap = guiconfig.get_wrap()
            self._mono = guiconfig.get_mono()
            self._linenums = guiconfig.get_linenums()
            self._gutter_font = (MONO_FAMILY, max(8, self._font_size - 2))
            self._recent_rows = []

            self._set_icon()
            self._build_menu()
            self.add_section("editor", "Editor", "✎", self._build_editor)
            self.add_section("about", "About", "ℹ", self._build_about)
            self._build_recent_sidebar()
            self.show("editor")
            self.protocol("WM_DELETE_WINDOW", self._on_close)
            self.set_status("Ready")
            if path:
                self.after(80, lambda: self._open_path(path))
            else:
                self._new_file()

        # ---- assets / icon
        def _set_icon(self):
            try:
                ico = asset_path("plain-text-editor.ico")
                if ico and os.name == "nt":
                    self.iconbitmap(ico)
                    return
            except Exception:
                pass
            try:
                png = asset_path("plain-text-editor.png")
                if png:
                    img = tk.PhotoImage(file=png)
                    self._img_refs.append(img)
                    self.iconphoto(True, img)
            except Exception:
                pass  # icon is cosmetic; never block launch

        # =================================================================
        # Menus (☰ dropdown; native menubars are banned) + shortcuts
        # =================================================================
        def _build_menu(self):
            bar = tk.Menu(self)

            filem = tk.Menu(bar, tearoff=0)
            filem.add_command(label="New file", accelerator="Ctrl+N",
                              command=self._new_file)
            filem.add_command(label="Open…", accelerator="Ctrl+O",
                              command=self._open_dialog)
            self._recent_menu = tk.Menu(filem, tearoff=0,
                                        postcommand=self._fill_recent)
            filem.add_cascade(label="Open Recent", menu=self._recent_menu)
            filem.add_command(label="Quick switcher…", accelerator="Ctrl+P",
                              command=self._quick_switch)
            filem.add_separator()
            filem.add_command(label="Save", accelerator="Ctrl+S",
                              command=self._save)
            filem.add_command(label="Save As…", accelerator="Ctrl+Shift+S",
                              command=self._save_as)
            filem.add_command(label="Save All", command=self._save_all)
            filem.add_separator()
            filem.add_command(label="Close tab", accelerator="Ctrl+W",
                              command=self._close_current)
            filem.add_separator()
            filem.add_command(label="Settings…", accelerator="Ctrl+,",
                              command=self._open_settings)
            filem.add_command(label="Exit", command=self._on_close)
            bar.add_cascade(label="File", menu=filem)

            editm = tk.Menu(bar, tearoff=0)
            editm.add_command(label="Undo", accelerator="Ctrl+Z",
                              command=lambda: self._edit_event("<<Undo>>"))
            editm.add_command(label="Redo", accelerator="Ctrl+Y",
                              command=lambda: self._edit_event("<<Redo>>"))
            editm.add_separator()
            editm.add_command(label="Cut", accelerator="Ctrl+X",
                              command=lambda: self._edit_event("<<Cut>>"))
            editm.add_command(label="Copy", accelerator="Ctrl+C",
                              command=lambda: self._edit_event("<<Copy>>"))
            editm.add_command(label="Paste", accelerator="Ctrl+V",
                              command=lambda: self._edit_event("<<Paste>>"))
            editm.add_command(label="Select All", accelerator="Ctrl+A",
                              command=self._select_all)
            editm.add_separator()
            editm.add_command(label="Duplicate line", accelerator="Ctrl+D",
                              command=self._duplicate_line)
            editm.add_command(label="Delete line", accelerator="Ctrl+Shift+K",
                              command=self._delete_line)
            editm.add_command(label="Move line up",
                              accelerator="Ctrl+Shift+Up",
                              command=lambda: self._move_line(-1))
            editm.add_command(label="Move line down",
                              accelerator="Ctrl+Shift+Down",
                              command=lambda: self._move_line(+1))
            editm.add_command(label="Trim trailing whitespace",
                              command=self._trim_trailing)
            editm.add_separator()
            editm.add_command(label="Find…", accelerator="Ctrl+F",
                              command=lambda: self._show_find(replace=False))
            editm.add_command(label="Replace…", accelerator="Ctrl+H",
                              command=lambda: self._show_find(replace=True))
            editm.add_command(label="Find Next", accelerator="F3",
                              command=lambda: self._find_step(False))
            editm.add_command(label="Find Previous", accelerator="Shift+F3",
                              command=lambda: self._find_step(True))
            editm.add_command(label="Go To Line…", accelerator="Ctrl+G",
                              command=self._goto_line)
            editm.add_separator()
            editm.add_command(label="Time/Date", accelerator="F5",
                              command=self._insert_timestamp)
            bar.add_cascade(label="Edit", menu=editm)

            self._wrap_var = tk.BooleanVar(value=self._wrap)
            self._mono_var = tk.BooleanVar(value=self._mono)
            self._nums_var = tk.BooleanVar(value=self._linenums)
            self._eol_var = tk.StringVar()
            self._enc_var = tk.StringVar()

            fmtm = tk.Menu(bar, tearoff=0,
                           postcommand=self._sync_format_menu)
            fmtm.add_checkbutton(label="Word Wrap", variable=self._wrap_var,
                                 command=self._apply_wrap)
            fmtm.add_checkbutton(label="Monospace Font",
                                 variable=self._mono_var,
                                 command=self._apply_font)
            fmtm.add_checkbutton(label="Line Numbers",
                                 variable=self._nums_var,
                                 command=self._apply_linenums)
            fmtm.add_separator()
            eolm = tk.Menu(fmtm, tearoff=0)
            for label, eol in EOL_CHOICES:
                eolm.add_radiobutton(label=label, value=eol,
                                     variable=self._eol_var,
                                     command=lambda e=eol:
                                     self._set_eol(e))
            fmtm.add_cascade(label="Line Endings", menu=eolm)
            encm = tk.Menu(fmtm, tearoff=0)
            for label, enc in ENC_CHOICES:
                encm.add_radiobutton(label=label, value=enc,
                                     variable=self._enc_var,
                                     command=lambda e=enc:
                                     self._set_encoding(e))
            fmtm.add_cascade(label="Encoding", menu=encm)
            fmtm.add_separator()
            fmtm.add_command(label="Zoom In", accelerator="Ctrl+=",
                             command=lambda: self._zoom(+1))
            fmtm.add_command(label="Zoom Out", accelerator="Ctrl+-",
                             command=lambda: self._zoom(-1))
            fmtm.add_command(label="Restore Default Zoom",
                             accelerator="Ctrl+0",
                             command=lambda: self._zoom(0))
            bar.add_cascade(label="Format", menu=fmtm)

            viewm = tk.Menu(bar, tearoff=0)
            viewm.add_command(label="Next tab", accelerator="Ctrl+Tab",
                              command=lambda: self._cycle_tab(+1))
            viewm.add_command(label="Previous tab",
                              accelerator="Ctrl+Shift+Tab",
                              command=lambda: self._cycle_tab(-1))
            viewm.add_separator()
            viewm.add_command(label="Toggle sidebar", accelerator="Ctrl+\\",
                              command=self.toggle_sidebar)
            viewm.add_command(
                label="Toggle dark mode",
                command=lambda: self.set_theme(
                    "light" if self.theme == "dark" else "dark"))
            bar.add_cascade(label="View", menu=viewm)

            helpm = tk.Menu(bar, tearoff=0)
            helpm.add_command(label="About", command=lambda: self.show("about"))
            helpm.add_command(label="Open project page (quickopen.ai)",
                              command=lambda: open_with_default_app(PROJECT_URL))
            bar.add_cascade(label="Help", menu=helpm)
            self.configure(menu=bar)

            # window-level fallbacks so shortcuts work outside the Text too
            for seq, fn in (("<Control-n>", self._new_file),
                            ("<Control-o>", self._open_dialog),
                            ("<Control-s>", self._save),
                            ("<Control-S>", self._save_as),
                            ("<Control-w>", self._close_current),
                            ("<Control-p>", self._quick_switch),
                            ("<Control-g>", self._goto_line),
                            ("<Control-comma>", self._open_settings),
                            ("<F5>", self._insert_timestamp)):
                self.bind(seq, lambda _e, f=fn: (f(), "break")[1])
            self.bind("<Escape>", lambda _e: self._hide_find())
            self.bind_all("<Control-Tab>",
                          lambda e: (self._cycle_tab(+1), "break")[1])
            for seq in ("<Control-Shift-Tab>", "<Control-ISO_Left_Tab>",
                        "<Control-Shift-ISO_Left_Tab>"):
                try:
                    self.bind_all(
                        seq, lambda e: (self._cycle_tab(-1), "break")[1])
                except Exception:
                    pass

        def _sync_format_menu(self):
            tab = self._cur()
            if tab is None:
                return
            self._eol_var.set(tab.doc.eol)
            self._enc_var.set(tab.doc.encoding)

        def _fill_recent(self):
            m = self._recent_menu
            m.delete(0, "end")
            recent = guiconfig.get_recent()
            if not recent:
                m.add_command(label="(no recent files)", state="disabled")
                return
            for path in recent:
                m.add_command(label=shorten_path(path, 60),
                              command=lambda p=path: self._open_path(p))
            m.add_separator()
            m.add_command(label="Clear list", command=self._clear_recent)

        def _clear_recent(self):
            guiconfig.clear_recent()
            self._refresh_recent_sidebar()

        # ---- key bindings.  tk.Text ships emacs-style class bindings for
        # Ctrl+O (insert line), Ctrl+F (cursor forward), Ctrl+H (backspace),
        # Ctrl+D (delete char)…  Binding on the widget and returning "break"
        # beats them all.
        def _bind_text_keys(self, t):
            def on(seq, fn):
                t.bind(seq, lambda _e, f=fn: (f(), "break")[1])

            on("<Control-n>", self._new_file)
            on("<Control-o>", self._open_dialog)
            on("<Control-s>", self._save)
            on("<Control-S>", self._save_as)             # Ctrl+Shift+S
            on("<Control-w>", self._close_current)
            on("<Control-p>", self._quick_switch)
            on("<Control-f>", lambda: self._show_find(False))
            on("<Control-h>", lambda: self._show_find(True))
            on("<Control-g>", self._goto_line)
            on("<Control-a>", self._select_all)
            on("<Control-y>", lambda: self._edit_event("<<Redo>>"))
            on("<Control-d>", self._duplicate_line)
            on("<Control-K>", self._delete_line)         # Ctrl+Shift+K
            on("<Control-Shift-Up>", lambda: self._move_line(-1))
            on("<Control-Shift-Down>", lambda: self._move_line(+1))
            on("<F5>", self._insert_timestamp)
            on("<F3>", lambda: self._find_step(False))
            on("<Shift-F3>", lambda: self._find_step(True))
            for seq in ("<Control-equal>", "<Control-plus>",
                        "<Control-KP_Add>"):
                on(seq, lambda: self._zoom(+1))
            for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
                on(seq, lambda: self._zoom(-1))
            for seq in ("<Control-0>", "<Control-KP_0>"):
                on(seq, lambda: self._zoom(0))
            t.bind("<Control-MouseWheel>",
                   lambda e: (self._zoom(+1 if e.delta > 0 else -1),
                              "break")[1])
            t.bind("<Control-Button-4>",
                   lambda _e: (self._zoom(+1), "break")[1])
            t.bind("<Control-Button-5>",
                   lambda _e: (self._zoom(-1), "break")[1])

        # =================================================================
        # Recent-files sidebar library (sidebar_body)
        # =================================================================
        def _build_recent_sidebar(self):
            aura.SectionLabel(self.sidebar_body, "Recent files").pack(
                anchor="w", padx=6, pady=(0, 4))
            self._recent_scroll = ctk.CTkScrollableFrame(
                self.sidebar_body, fg_color="transparent")
            self._recent_scroll.pack(fill="both", expand=True)
            self._refresh_recent_sidebar()

        def _refresh_recent_sidebar(self):
            for w in list(self._recent_scroll.winfo_children()):
                try:
                    w.destroy()
                except Exception:
                    pass
            recent = guiconfig.get_recent()
            if not recent:
                aura.Caption(self._recent_scroll,
                             "Files you open appear here.").pack(
                    anchor="w", padx=6, pady=(2, 0))
                return
            open_paths = {guiconfig.norm_path(t.path)
                          for t in self.tabs if t.path}
            for path in recent[:10]:
                active = guiconfig.norm_path(path) in open_paths
                btn = ctk.CTkButton(
                    self._recent_scroll, text=os.path.basename(path),
                    anchor="w", height=30,
                    corner_radius=aura.TOKENS["geometry"]["radius_button"],
                    fg_color=pair("accent_soft") if active else "transparent",
                    hover_color=(aura._pal["light"]["surface2"],
                                 aura._pal["dark"]["surface2"]),
                    text_color=pair("text") if active else pair("muted"),
                    font=aura.font(role="body"),
                    command=lambda p=path: self._open_path(p))
                btn.pack(fill="x", pady=1)
                aura.Tooltip(btn, path)

        # =================================================================
        # Editor section — toolbar + find bar + tabbed workspace
        # =================================================================
        def _build_editor(self, frame):
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(2, weight=1)

            # ---- toolbar (primary action left; view switches right)
            tb = aura.Toolbar(frame)
            tb.grid(row=0, column=0, sticky="ew", pady=(0, 10))
            tb.add_button("＋ New file", self._new_file, kind="primary")
            tb.add_button("Open…", self._open_dialog)
            tb.add_button("Save", self._save)
            self._mono_switch = aura.Switch(
                tb, text="Monospace", command=self._on_mono_switch)
            tb.add_right(self._mono_switch)
            (self._mono_switch.select if self._mono
             else self._mono_switch.deselect)()
            self._wrap_switch = aura.Switch(
                tb, text="Word wrap", command=self._on_wrap_switch)
            tb.add_right(self._wrap_switch)
            (self._wrap_switch.select if self._wrap
             else self._wrap_switch.deselect)()

            # ---- find & replace bar (hidden until Ctrl+F / Ctrl+H)
            self._find_bar = ctk.CTkFrame(
                frame, fg_color=pair("surface"), corner_radius=10,
                border_width=1, border_color=pair("border"))
            self._find_bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
            self._find_bar.grid_remove()
            fb = self._find_bar
            fb.grid_columnconfigure(0, weight=1)

            row1 = ctk.CTkFrame(fb, fg_color="transparent")
            row1.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
            self.find_entry = aura.AuraEntry(row1, placeholder="Find…")
            self.find_entry.pack(side="left", fill="x", expand=True)
            self.find_entry.bind("<Return>", lambda _e: self._find_step(False))
            self.find_entry.bind("<Shift-Return>",
                                 lambda _e: self._find_step(True))
            self.find_entry.bind("<KeyRelease>",
                                 lambda _e: self._update_match_count())
            self._match_lbl = aura.Caption(row1, "")
            self._match_lbl.pack(side="left", padx=(10, 0))
            aura.AuraButton(row1, "Next", kind="secondary", height=28,
                            width=62, command=lambda: self._find_step(False)
                            ).pack(side="left", padx=(8, 0))
            aura.AuraButton(row1, "Previous", kind="ghost", height=28,
                            width=76, command=lambda: self._find_step(True)
                            ).pack(side="left", padx=(6, 0))
            aura.AuraButton(row1, "✕", kind="ghost", height=28, width=32,
                            command=self._hide_find).pack(side="left",
                                                          padx=(6, 0))

            row2 = ctk.CTkFrame(fb, fg_color="transparent")
            row2.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 8))
            self.replace_entry = aura.AuraEntry(row2,
                                                placeholder="Replace with…")
            self.replace_entry.pack(side="left", fill="x", expand=True)
            aura.AuraButton(row2, "Replace", kind="secondary", height=28,
                            width=76, command=self._replace_one
                            ).pack(side="left", padx=(8, 0))
            aura.AuraButton(row2, "Replace All", kind="ghost", height=28,
                            width=96, command=self._replace_all
                            ).pack(side="left", padx=(6, 0))
            self._case_switch = aura.Switch(row2, text="Match case",
                                            command=self._update_match_count)
            self._case_switch.pack(side="left", padx=(12, 0))
            self._word_switch = aura.Switch(row2, text="Whole word",
                                            command=self._update_match_count)
            self._word_switch.pack(side="left", padx=(10, 0))

            # ---- the tabbed workspace (Aura-styled ttk.Notebook)
            self.nb = ttk.Notebook(frame)
            self.nb.grid(row=2, column=0, sticky="nsew")
            self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)
            self.nb.bind("<Button-2>", self._on_tab_middle_click)
            self.nb.bind("<Button-3>", self._on_tab_right_click)
            self._tab_menu = tk.Menu(self, tearoff=0)
            aura.track(self._tab_menu, "menu")

            # ---- empty state (shown when the last tab is closed)
            self.empty = aura.EmptyState(
                frame, title="Nothing open",
                caption="Create a new file or open one to start writing — "
                        "each file gets its own tab.",
                action_text="＋ New file", action=self._new_file,
                image=(asset_path("assets/editor-empty-light.png"),
                       asset_path("assets/editor-empty-dark.png")))

            # ---- status strip (right side of the Aura status bar)
            act = self.statusbar.actions
            self._pos_lbl = aura.Caption(act, "Ln 1, Col 1")
            self._sel_lbl = aura.Caption(act, "")
            self._count_lbl = aura.Caption(act, "0 chars")
            self._enc_lbl = aura.Caption(act, "UTF-8")
            self._eol_lbl = aura.Caption(act, "LF")
            self._zoom_lbl = aura.Caption(act, f"{self._font_size} pt")
            for lbl in (self._pos_lbl, self._sel_lbl, self._count_lbl,
                        self._enc_lbl, self._eol_lbl, self._zoom_lbl):
                lbl.pack(side="left", padx=(0, 14))
            self._update_empty_state()

        # =================================================================
        # Tab management
        # =================================================================
        def _cur(self):
            """The selected EditorTab, or None with no tabs open."""
            try:
                sel = self.nb.select()
            except Exception:
                return None
            for t in self.tabs:
                if str(t.frame) == sel:
                    return t
            return None

        def _add_tab(self, doc=None, path=None, select=True):
            if not self.tabs:
                EditorTab._seq = 0     # an empty workspace restarts Untitled 1
            tab = EditorTab(self, doc=doc, path=path)
            self.tabs.append(tab)
            self.nb.add(tab.frame, text=tab.label())
            if select:
                self.nb.select(tab.frame)
            self._update_empty_state()
            self._refresh_recent_sidebar()
            return tab

        def _refresh_tab_label(self, tab):
            try:
                self.nb.tab(tab.frame, text=tab.label())
            except Exception:
                pass
            if tab is self._cur():
                self._refresh_title()

        def _remove_tab(self, tab):
            try:
                self.nb.forget(tab.frame)
            except Exception:
                pass
            if tab in self.tabs:
                self.tabs.remove(tab)
            try:
                tab.frame.destroy()
            except Exception:
                pass
            self._update_empty_state()
            self._refresh_recent_sidebar()
            self._refresh_title()

        def _close_tab(self, tab):
            if tab is None:
                return
            if not self._confirm_discard(tab):
                return
            self._remove_tab(tab)

        def _close_current(self):
            self._close_tab(self._cur())

        def _cycle_tab(self, step):
            if len(self.tabs) < 2:
                return
            try:
                idx = self.nb.index(self.nb.select())
                self.nb.select((idx + step) % len(self.nb.tabs()))
            except Exception:
                pass

        def _on_tab_changed(self, _e=None):
            tab = self._cur()
            if tab is None:
                return
            self._refresh_title()
            self._refresh_doc_labels()
            self._update_match_count()
            try:
                tab.text.focus_set()
                tab.schedule_gutter()
            except Exception:
                pass

        def _tab_at(self, event):
            try:
                idx = self.nb.index(f"@{event.x},{event.y}")
            except Exception:
                return None
            try:
                frame_name = self.nb.tabs()[idx]
            except Exception:
                return None
            for t in self.tabs:
                if str(t.frame) == frame_name:
                    return t
            return None

        def _on_tab_middle_click(self, event):
            tab = self._tab_at(event)
            if tab is not None:
                self._close_tab(tab)
                return "break"

        def _on_tab_right_click(self, event):
            tab = self._tab_at(event)
            if tab is None:
                return
            m = self._tab_menu
            m.delete(0, "end")
            m.add_command(label="Close", command=lambda: self._close_tab(tab))
            m.add_command(label="Close others",
                          command=lambda: self._close_others(tab))
            m.add_command(label="Close all", command=self._close_all)
            m.add_separator()
            m.add_command(
                label="Copy full path",
                state="normal" if tab.path else "disabled",
                command=lambda: self._copy_path(tab))
            m.add_command(
                label="Open containing folder",
                state="normal" if tab.path else "disabled",
                command=lambda: open_with_default_app(
                    os.path.dirname(tab.path)))
            aura.style_menu(m)
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                m.grab_release()

        def _close_others(self, keep):
            for t in [t for t in self.tabs if t is not keep]:
                if not self._confirm_discard(t):
                    return
                self._remove_tab(t)

        def _close_all(self):
            for t in list(self.tabs):
                if not self._confirm_discard(t):
                    return
                self._remove_tab(t)

        def _copy_path(self, tab):
            try:
                self.clipboard_clear()
                self.clipboard_append(tab.path)
                self.set_status("Path copied")
            except Exception:
                pass

        def _update_empty_state(self):
            if self.tabs:
                self.empty.place_forget()
                self.nb.grid()
            else:
                self.nb.grid_remove()
                self.empty.place(relx=0, rely=0.12, relwidth=1,
                                 relheight=0.85)
                self.empty.lift()

        # =================================================================
        # Document plumbing
        # =================================================================
        def _refresh_title(self):
            tab = self._cur()
            if tab is None:
                self.title(WINDOW_TITLE)
                return
            star = "• " if tab.dirty else ""
            self.title(f"{star}{tab.display_name()} — {WINDOW_TITLE}")

        def _on_caret_moved(self):
            tab = self._cur()
            if tab is None or not hasattr(self, "_pos_lbl"):
                return
            try:
                line, col = tab.text.index("insert").split(".")
                self._pos_lbl.configure(text=f"Ln {line}, Col {int(col) + 1}")
                try:
                    sel = tab.text.get("sel.first", "sel.last")
                    self._sel_lbl.configure(text=f"Sel {len(sel)}")
                except tk.TclError:
                    self._sel_lbl.configure(text="")
                c = textio.counts(tab.get_text())
                self._count_lbl.configure(
                    text=f"{c['chars']} chars · {c['words']} words")
                tab.update_curline()
                tab.schedule_gutter()
            except Exception:
                pass

        def _refresh_doc_labels(self):
            tab = self._cur()
            if tab is None or not hasattr(self, "_enc_lbl"):
                return
            self._enc_lbl.configure(text=tab.doc.encoding_label)
            self._eol_lbl.configure(text=tab.doc.eol_label)
            self._refresh_title()
            self._on_caret_moved()

        def _confirm_discard(self, tab):
            """True when it is safe to drop *tab* (saving if asked)."""
            if tab is None or not tab.dirty:
                return True
            try:
                self.nb.select(tab.frame)
            except Exception:
                pass
            answer = messagebox.askyesnocancel(
                APP_NAME,
                f"Do you want to save changes to {tab.display_name()}?",
                parent=self)
            if answer is None:
                return False
            if answer:
                return self._save(tab)
            return True

        # =================================================================
        # File commands
        # =================================================================
        def _new_file(self):
            self._add_tab()
            self.set_status("New file")

        def _open_dialog(self):
            path = filedialog.askopenfilename(
                parent=self, title="Open text file",
                initialdir=guiconfig.default_open_dir(),
                filetypes=FILETYPES)
            if path:
                self._open_path(path)

        def _open_path(self, path):
            path = guiconfig.norm_path(path)
            # already open? -> just focus its tab (the Notepad++ behaviour)
            for t in self.tabs:
                if t.path and guiconfig.norm_path(t.path) == path:
                    self.nb.select(t.frame)
                    return
            try:
                doc = textio.load_file(path)
            except PlainTextEditorError as exc:
                guiconfig.remove_recent(path)
                self._refresh_recent_sidebar()
                self.set_error(str(exc))
                return
            cur = self._cur()
            if cur is not None and cur.pristine():
                # load into the untouched Untitled tab instead of a new one
                cur.doc, cur.path = doc, path
                cur.set_text(doc.text)
                self._refresh_tab_label(cur)
            else:
                self._add_tab(doc=doc, path=path)
            guiconfig.add_recent(path)
            guiconfig.set_last_dir(os.path.dirname(path))
            self._refresh_recent_sidebar()
            self._refresh_doc_labels()
            self.set_status(
                f"Opened {os.path.basename(path)} "
                f"({doc.encoding_label}, {doc.eol_label})")

        def _save(self, tab=None):
            tab = tab or self._cur()
            if tab is None:
                return False
            if not tab.path:
                return self._save_as(tab)
            return self._write_to(tab, tab.path)

        def _save_as(self, tab=None):
            tab = tab or self._cur()
            if tab is None:
                return False
            path = filedialog.asksaveasfilename(
                parent=self, title="Save as",
                initialdir=(os.path.dirname(tab.path) if tab.path
                            else guiconfig.default_open_dir()),
                initialfile=(os.path.basename(tab.path) if tab.path
                             else tab.display_name() + ".txt"),
                defaultextension=".txt", filetypes=FILETYPES)
            if not path:
                return False
            return self._write_to(tab, guiconfig.norm_path(path))

        def _save_all(self):
            saved = 0
            for t in list(self.tabs):
                if t.dirty or not t.path:
                    if not self._save(t):
                        return
                    saved += 1
            self.set_success(f"Saved {saved} file(s)" if saved
                             else "Nothing to save")

        def _write_to(self, tab, path):
            tab.doc.text = tab.get_text()
            try:
                textio.save_file(path, tab.doc)
            except PlainTextEditorError as exc:
                self.set_error(str(exc))
                return False
            tab.path = path
            tab.dirty = False
            tab.doc.mixed_eol = False  # saved uniformly in the dominant EOL
            tab.text.edit_modified(False)
            self._refresh_tab_label(tab)
            guiconfig.add_recent(path)
            guiconfig.set_last_dir(os.path.dirname(path))
            self._refresh_recent_sidebar()
            self._refresh_doc_labels()
            self.set_success(
                f"Saved {tab.display_name()} "
                f"({tab.doc.encoding_label}, {tab.doc.eol_label})")
            return True

        # =================================================================
        # Edit commands
        # =================================================================
        def _edit_event(self, virtual):
            tab = self._cur()
            if tab is None:
                return
            try:
                tab.text.event_generate(virtual)
            except tk.TclError:
                pass  # empty undo/redo stack or empty clipboard

        def _select_all(self):
            tab = self._cur()
            if tab is None:
                return
            tab.text.tag_add("sel", "1.0", "end-1c")
            tab.text.mark_set("insert", "end-1c")

        def _insert_timestamp(self):
            tab = self._cur()
            if tab is None:
                return
            tab.text.insert("insert", editing.f5_stamp())
            self._on_caret_moved()

        def _goto_line(self):
            tab = self._cur()
            if tab is None:
                return
            total = editing.line_count(tab.get_text())
            line = simpledialog.askinteger(
                "Go To Line", f"Line number (1–{total}):", parent=self,
                minvalue=1, maxvalue=total)
            if line is None:
                return
            tab.text.mark_set("insert", f"{line}.0")
            tab.text.see("insert")
            tab.text.focus_set()
            self._on_caret_moved()

        # ---- line operations (the Notepad++ daily set; tested core math)
        def _line_op(self, fn):
            """Run editing.fn(text, line, …) and swap the result in, keeping
            the caret column."""
            tab = self._cur()
            if tab is None:
                return None
            line, col = (int(v) for v in tab.text.index("insert").split("."))
            try:
                return tab, line, col, tab.get_text()
            except Exception:
                return None

        def _swap_text(self, tab, new_text, line, col):
            tab.text.edit_separator()
            yview = tab.text.yview()
            tab.text.delete("1.0", "end")
            tab.text.insert("1.0", new_text)
            line = min(line, editing.line_count(new_text))
            tab.text.mark_set("insert", f"{line}.{col}")
            try:
                tab.text.yview_moveto(yview[0])
            except Exception:
                pass
            tab.text.see("insert")
            self._on_caret_moved()

        def _duplicate_line(self):
            ctx = self._line_op(None)
            if ctx is None:
                return
            tab, line, col, text = ctx
            try:
                new_text = editing.duplicate_line(text, line)
            except PlainTextEditorError as exc:
                self.set_error(str(exc))
                return
            self._swap_text(tab, new_text, line + 1, col)

        def _delete_line(self):
            ctx = self._line_op(None)
            if ctx is None:
                return
            tab, line, col, text = ctx
            try:
                new_text = editing.delete_line(text, line)
            except PlainTextEditorError as exc:
                self.set_error(str(exc))
                return
            self._swap_text(tab, new_text, line, 0)

        def _move_line(self, delta):
            ctx = self._line_op(None)
            if ctx is None:
                return
            tab, line, col, text = ctx
            try:
                new_text, new_line = editing.move_line(text, line, delta)
            except PlainTextEditorError as exc:
                self.set_error(str(exc))
                return
            if new_text != text:
                self._swap_text(tab, new_text, new_line, col)

        def _trim_trailing(self):
            ctx = self._line_op(None)
            if ctx is None:
                return
            tab, line, col, text = ctx
            new_text, changed = editing.trim_trailing_whitespace(text)
            if not changed:
                self.set_status("No trailing whitespace")
                return
            self._swap_text(tab, new_text, line, col)
            self.set_success(f"Trimmed {changed} line(s)")

        # ---- Format-menu document conversions
        def _set_eol(self, eol):
            tab = self._cur()
            if tab is None:
                return
            if tab.doc.eol != eol or tab.doc.mixed_eol:
                tab.doc.eol = eol
                tab.doc.mixed_eol = False
                if not tab.dirty:
                    tab.dirty = True
                    self._refresh_tab_label(tab)
                self._refresh_doc_labels()
                label = "CRLF" if eol == "\r\n" else "LF"
                self.set_status(f"Line endings set to {label} — "
                                f"applies on save")

        def _set_encoding(self, enc):
            tab = self._cur()
            if tab is None:
                return
            if tab.doc.encoding != enc:
                tab.doc.encoding = enc
                if not tab.dirty:
                    tab.dirty = True
                    self._refresh_tab_label(tab)
                self._refresh_doc_labels()
                self.set_status(f"Encoding set to {tab.doc.encoding_label} — "
                                f"applies on save")

        # ---- find & replace --------------------------------------------
        def _show_find(self, replace=False):
            tab = self._cur()
            if tab is None:
                return
            self._find_bar.grid()
            try:  # pre-fill with the current selection
                sel = tab.text.get("sel.first", "sel.last")
                if sel and "\n" not in sel:
                    self.find_entry.delete(0, "end")
                    self.find_entry.insert(0, sel)
            except tk.TclError:
                pass
            self._update_match_count()
            (self.replace_entry if replace else self.find_entry).focus_set()

        def _hide_find(self):
            self._find_bar.grid_remove()
            tab = self._cur()
            if tab is not None:
                tab.text.focus_set()

        def _find_args(self, quiet=False):
            needle = self.find_entry.get()
            if not needle:
                if not quiet:
                    self.set_status("Type something to find")
                return None
            return {"needle": needle,
                    "match_case": bool(self._case_switch.get()),
                    "whole_word": bool(self._word_switch.get())}

        def _update_match_count(self, *_a):
            if not hasattr(self, "_match_lbl"):
                return
            tab = self._cur()
            args = self._find_args(quiet=True)
            if tab is None or args is None:
                self._match_lbl.configure(text="")
                return
            try:
                n = len(editing.find_all(tab.get_text(), args["needle"],
                                         args["match_case"],
                                         args["whole_word"]))
            except PlainTextEditorError:
                n = 0
            self._match_lbl.configure(
                text=f"{n} match{'es' if n != 1 else ''}")

        def _insert_offset(self, tab):
            return len(tab.text.get("1.0", "insert"))

        def _select_span(self, tab, span):
            start, end = span
            tab.text.tag_remove("sel", "1.0", "end")
            tab.text.tag_add("sel", f"1.0+{start}c", f"1.0+{end}c")
            tab.text.mark_set("insert", f"1.0+{end}c")
            tab.text.see("insert")
            self._on_caret_moved()

        def _find_step(self, backwards):
            tab = self._cur()
            args = self._find_args()
            if tab is None or not args:
                return
            text = tab.get_text()
            start = self._insert_offset(tab)
            if backwards:
                try:  # step over the current selection so Prev moves
                    if tab.text.get("sel.first", "sel.last"):
                        start = len(tab.text.get("1.0", "sel.first")) \
                            + len(args["needle"])
                except tk.TclError:
                    pass
            span = editing.find_next(text, start=start,
                                     backwards=backwards, **args)
            if span is None:
                self.set_status(f"Cannot find \"{args['needle']}\"")
                return
            self._select_span(tab, span)
            self.set_status("")

        def _replace_one(self):
            tab = self._cur()
            args = self._find_args()
            if tab is None or not args:
                return
            replacement = self.replace_entry.get()
            try:
                sel = tab.text.get("sel.first", "sel.last")
            except tk.TclError:
                sel = None
            if sel is not None:
                matches = editing.find_all(sel, args["needle"],
                                           args["match_case"],
                                           args["whole_word"])
                if matches == [(0, len(sel))]:
                    tab.text.delete("sel.first", "sel.last")
                    tab.text.insert("insert", replacement)
            self._find_step(False)
            self._update_match_count()

        def _replace_all(self):
            tab = self._cur()
            args = self._find_args()
            if tab is None or not args:
                return
            new_text, count = editing.replace_all(
                tab.get_text(), args["needle"],
                self.replace_entry.get(), args["match_case"],
                args["whole_word"])
            if not count:
                self.set_status(f"Cannot find \"{args['needle']}\"")
                return
            tab.text.edit_separator()
            insert = tab.text.index("insert")
            tab.text.delete("1.0", "end")
            tab.text.insert("1.0", new_text)
            tab.text.mark_set("insert", insert)
            tab.text.see("insert")
            self.set_success(f"Replaced {count} occurrence(s)")
            self._on_caret_moved()
            self._update_match_count()

        # =================================================================
        # Quick switcher (Ctrl+P): open tabs + recent files
        # =================================================================
        def _quick_switch(self):
            dlg = aura.Dialog(self, title="Quick switcher", size=(520, 420))
            entry = aura.AuraEntry(dlg.body, placeholder="Type to filter "
                                   "open tabs and recent files…")
            entry.pack(fill="x")
            lb = tk.Listbox(dlg.body, activestyle="none",
                            exportselection=False,
                            font=(UI_FAMILY, 11))
            lb.pack(fill="both", expand=True, pady=(10, 0))
            aura.track(lb, "listbox")

            entries = []          # (label, kind, payload)

            def rebuild(_e=None):
                q = entry.get()
                lb.delete(0, "end")
                entries.clear()
                for t in self.tabs:
                    name = t.display_name()
                    if fuzzy_match(q, name):
                        entries.append((f"{t.label()}   — open tab",
                                        "tab", t))
                open_paths = {guiconfig.norm_path(t.path)
                              for t in self.tabs if t.path}
                for p in guiconfig.get_recent():
                    if guiconfig.norm_path(p) in open_paths:
                        continue
                    if fuzzy_match(q, os.path.basename(p)) or \
                            fuzzy_match(q, p):
                        entries.append((shorten_path(p, 56), "path", p))
                for label, _k, _p in entries:
                    lb.insert("end", label)
                if entries:
                    lb.selection_set(0)

            def choose(_e=None):
                sel = lb.curselection()
                if not sel:
                    return
                _label, kind, payload = entries[sel[0]]
                dlg.close()
                if kind == "tab":
                    self.nb.select(payload.frame)
                else:
                    self._open_path(payload)

            entry.bind("<KeyRelease>", rebuild)
            entry.bind("<Return>", choose)
            entry.bind("<Down>", lambda _e: lb.focus_set())
            lb.bind("<Return>", choose)
            lb.bind("<Double-Button-1>", choose)
            rebuild()
            entry.focus_set()

        # =================================================================
        # View commands
        # =================================================================
        def _on_wrap_switch(self):
            self._wrap_var.set(bool(self._wrap_switch.get()))
            self._apply_wrap()

        def _apply_wrap(self):
            self._wrap = bool(self._wrap_var.get())
            (self._wrap_switch.select if self._wrap
             else self._wrap_switch.deselect)()
            for t in self.tabs:
                t.apply_wrap()
            guiconfig.set_wrap(self._wrap)

        def _on_mono_switch(self):
            self._mono_var.set(bool(self._mono_switch.get()))
            self._apply_font()

        def _apply_font(self):
            self._mono = bool(self._mono_var.get())
            if hasattr(self, "_mono_switch"):
                (self._mono_switch.select if self._mono
                 else self._mono_switch.deselect)()
            for t in self.tabs:
                t.apply_font()
            guiconfig.set_mono(self._mono)

        def _apply_linenums(self):
            self._linenums = bool(self._nums_var.get())
            for t in self.tabs:
                t.show_gutter(self._linenums)
            guiconfig.set_linenums(self._linenums)

        def _zoom(self, direction):
            if direction == 0:
                self._font_size = guiconfig.DEFAULT_FONT
            else:
                self._font_size = max(guiconfig.MIN_FONT,
                                      min(guiconfig.MAX_FONT,
                                          self._font_size + direction))
            guiconfig.set_font_size(self._font_size)
            self._gutter_font = (MONO_FAMILY, max(8, self._font_size - 2))
            for t in self.tabs:
                t.apply_font()
            if hasattr(self, "_zoom_lbl"):
                self._zoom_lbl.configure(text=f"{self._font_size} pt")

        # =================================================================
        # Settings dialog (Ctrl+,)
        # =================================================================
        def _open_settings(self):
            dlg = aura.Dialog(self, title="Settings", size=(520, 420))

            aura.SectionLabel(dlg.body, "Editor").pack(anchor="w",
                                                       pady=(0, 2))
            frow = ctk.CTkFrame(dlg.body, fg_color="transparent")
            frow.pack(anchor="w", pady=(4, 8))
            aura.Caption(frow, "Font size").pack(side="left", padx=(0, 10))
            fs = aura.AuraOption(
                frow, values=[str(s) for s in
                              (9, 10, 11, 12, 13, 14, 16, 18, 20, 24)],
                width=90, height=30, command=self._set_font_size)
            fs.set(str(self._font_size))
            fs.pack(side="left")

            def switch_row(text, initial, command):
                sw = aura.Switch(dlg.body, text=text, command=command)
                sw.pack(anchor="w", pady=(2, 2))
                (sw.select if initial else sw.deselect)()
                return sw

            self._set_wrap_sw = switch_row(
                "Word wrap", self._wrap,
                lambda: (self._wrap_var.set(
                    bool(self._set_wrap_sw.get())), self._apply_wrap()))
            self._set_mono_sw = switch_row(
                "Monospace font", self._mono,
                lambda: (self._mono_var.set(
                    bool(self._set_mono_sw.get())), self._apply_font()))
            self._set_nums_sw = switch_row(
                "Line numbers", self._linenums,
                lambda: (self._nums_var.set(
                    bool(self._set_nums_sw.get())), self._apply_linenums()))

            aura.SectionLabel(dlg.body, "Appearance").pack(anchor="w",
                                                           pady=(12, 2))
            trow = ctk.CTkFrame(dlg.body, fg_color="transparent")
            trow.pack(anchor="w", pady=(4, 0))
            aura.Caption(trow, "Theme").pack(side="left", padx=(0, 10))
            cur = guiconfig.get_theme()
            th = aura.AuraOption(trow, values=["System", "Light", "Dark"],
                                 width=110, height=30,
                                 command=self._set_theme_pref)
            th.set(cur.capitalize() if cur in ("light", "dark") else "System")
            th.pack(side="left")
            aura.Caption(dlg.body,
                         "System follows the OS Aura Dark/Light live.").pack(
                anchor="w", pady=(6, 0))

            dlg.add_button("Close")

        def _set_font_size(self, value):
            try:
                size = int(value)
            except (TypeError, ValueError):
                return
            self._font_size = max(guiconfig.MIN_FONT,
                                  min(guiconfig.MAX_FONT, size))
            guiconfig.set_font_size(self._font_size)
            self._gutter_font = (MONO_FAMILY, max(8, self._font_size - 2))
            for t in self.tabs:
                t.apply_font()
            if hasattr(self, "_zoom_lbl"):
                self._zoom_lbl.configure(text=f"{self._font_size} pt")

        def _set_theme_pref(self, choice):
            pref = str(choice).lower()
            if pref == "system":
                guiconfig.set_theme("system")
                self._follow_system = True
                if getattr(self, "_sys_listener", None) is None:
                    self._start_system_listener()
                self.set_theme(aura._system_theme(), _system=True)
            elif pref in ("light", "dark"):
                self.set_theme(pref)     # persists via on_theme_change

        # ---- theme: restyle the raw-tk gutters/curline with the flip
        def set_theme(self, theme, _system=False):
            super().set_theme(theme, _system=_system)
            try:
                for t in self.tabs:
                    t.style()
                self._refresh_recent_sidebar()
            except Exception:
                pass

        # =================================================================
        # About section
        # =================================================================
        def _build_about(self, frame):
            card = aura.Card(frame, title=APP_NAME)
            card.pack(anchor="nw", fill="x")
            aura.Caption(card.body, f"Version {APP_VERSION}").pack(anchor="w")
            ctk.CTkLabel(
                card.body, justify="left", anchor="w", wraplength=680,
                font=aura.font(role="body"),
                text="A fast, clean, offline text editor in the spirit of "
                     "Notepad++: tabs for every open file, line numbers, "
                     "find & replace with a live match count, and the "
                     "everyday line tools (duplicate, move, delete, trim) — "
                     "without the pro clutter.\n\n"
                     "Your file's encoding (UTF-8, UTF-8 BOM, UTF-16, ANSI) "
                     "and line endings (CRLF/LF) are detected on open, shown "
                     "in the status bar, and preserved exactly on save — or "
                     "converted from the Format menu when you choose.\n\n"
                     "100% AI-built, open source, published on QuickOpen. "
                     "Nothing is ever uploaded anywhere.").pack(anchor="w")
            aura.Caption(card.body,
                         "Licensed under Apache-2.0. Built on tkinter and "
                         "CustomTkinter (MIT).").pack(anchor="w",
                                                      pady=(10, 4))
            aura.AuraButton(card.body, "Project page: quickopen.ai",
                            kind="ghost",
                            command=lambda: open_with_default_app(
                                PROJECT_URL)).pack(anchor="w", pady=(6, 0))

        # ---- shutdown
        def _on_close(self):
            for t in list(self.tabs):
                if not self._confirm_discard(t):
                    return
            self.destroy()

    return App


def main(path=None):
    """Entry point: build the root window and run.  Degrades on headless
    hosts.

    Importing this module does nothing; only this function creates a Tk
    root.  With no display (e.g. a server) or without customtkinter
    installed, it prints a friendly note and returns 0 instead of raising,
    so headless callers stay clean.
    """
    try:
        import tkinter as tk
    except Exception as exc:
        print(f"{APP_NAME}: a graphical environment with tkinter is required "
              f"to run the GUI ({exc}).")
        return 0

    try:
        App = build_app()
        app = App(path=path)
    except ImportError as exc:
        print(f"{APP_NAME}: the GUI needs the 'customtkinter' package "
              f"({exc}). Install it with:  pip install customtkinter")
        return 0
    except tk.TclError as exc:
        print(f"{APP_NAME}: no graphical display available — cannot start "
              f"the GUI here ({exc}). This app is intended for the desktop.")
        return 0
    except Exception as exc:
        print(f"{APP_NAME}: could not start the GUI ({exc}).")
        return 1

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
