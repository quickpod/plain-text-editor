#!/usr/bin/env python3
r"""Plain Text Editor -- an Aura (QuickOpen design system) GUI over the
``plaintexteditor`` core.

A single Aura window with two sidebar sections:

  * **Editor** -- the whole point: one clean text surface (native selection,
    real undo/redo) with a slide-in find & replace bar and a live status
    strip (Ln/Col, character count, encoding, line endings, font size).
  * **About** -- app / licence info.

Design goals baked in here (mirrors the QuickOpen house style):
  * built on the vendored ``plaintexteditor/aura.py`` design system (deep
    space + light over CustomTkinter) for the chrome -- but the editing
    surface itself is a plain ``tk.Text``: monospace-optional, native
    selection and cursor behavior, no styling games with your text.
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
APP_VERSION = "1.0.0"
WINDOW_TITLE = "Plain Text Editor — by QuickOpen (quickopen.ai)"
PROJECT_URL = "https://quickopen.ai"
ACCENT = "#5b86f7"      # publish/specs/plain-text-editor.json accent


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


# ---------------------------------------------------------------------------
# The app (built lazily; tkinter/customtkinter imported only inside build_app)
# ---------------------------------------------------------------------------
def build_app():
    """Construct and return the App class bound to live GUI imports.

    Kept inside a function so this module imports cleanly without a display
    (and without customtkinter installed).
    """
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
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

    class App(aura.AuraApp):

        def __init__(self, path=None):
            super().__init__(
                title=WINDOW_TITLE, app_name=APP_NAME, accent=ACCENT,
                theme=guiconfig.get_theme(),
                icon_png=asset_path("plain-text-editor.png"),
                version=APP_VERSION, tagline="plain text, kept plain",
                on_theme_change=guiconfig.set_theme,
                size=(1180, 720), min_size=(900, 560))

            self.doc = textio.Document()
            self.path = None                  # None until saved/opened
            self._dirty = False
            self._img_refs = []
            self._font_size = guiconfig.get_font_size()
            self._wrap = guiconfig.get_wrap()
            self._mono = guiconfig.get_mono()
            self._last_find = None            # remembered find-bar state

            self._set_icon()
            self._build_menu()
            self.add_section("editor", "Editor", "✎", self._build_editor)
            self.add_section("about", "About", "ℹ", self._build_about)
            self.show("editor")
            self.protocol("WM_DELETE_WINDOW", self._on_close)
            self.set_status("Ready")
            if path:
                self.after(80, lambda: self._open_path(path))

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
        # Menu — Notepad's layout, Notepad's accelerators
        # =================================================================
        def _build_menu(self):
            bar = tk.Menu(self)

            filem = tk.Menu(bar, tearoff=0)
            filem.add_command(label="New", accelerator="Ctrl+N",
                              command=self._new_file)
            filem.add_command(label="Open…", accelerator="Ctrl+O",
                              command=self._open_dialog)
            self._recent_menu = tk.Menu(filem, tearoff=0,
                                        postcommand=self._fill_recent)
            filem.add_cascade(label="Open Recent", menu=self._recent_menu)
            filem.add_command(label="Save", accelerator="Ctrl+S",
                              command=self._save)
            filem.add_command(label="Save As…", accelerator="Ctrl+Shift+S",
                              command=self._save_as)
            filem.add_separator()
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
            fmtm = tk.Menu(bar, tearoff=0)
            fmtm.add_checkbutton(label="Word Wrap", variable=self._wrap_var,
                                 command=self._apply_wrap)
            fmtm.add_checkbutton(label="Monospace Font",
                                 variable=self._mono_var,
                                 command=self._apply_font)
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

        def _fill_recent(self):
            m = self._recent_menu
            m.delete(0, "end")
            recent = guiconfig.get_recent()
            if not recent:
                m.add_command(label="(no recent files)", state="disabled")
                return
            for path in recent:
                label = path if len(path) <= 60 else "…" + path[-59:]
                m.add_command(label=label,
                              command=lambda p=path: self._open_path(p))
            m.add_separator()
            m.add_command(label="Clear list", command=guiconfig.clear_recent)

        # =================================================================
        # Editor section
        # =================================================================
        def _build_editor(self, frame):
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(2, weight=1)

            # ---- toolbar row
            bar = ctk.CTkFrame(frame, fg_color="transparent")
            bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
            aura.AuraButton(bar, "New", kind="ghost", height=28, width=64,
                            command=self._new_file).pack(side="left")
            aura.AuraButton(bar, "Open…", kind="ghost", height=28, width=72,
                            command=self._open_dialog).pack(side="left",
                                                            padx=(6, 0))
            aura.AuraButton(bar, "Save", kind="primary", height=28, width=72,
                            command=self._save).pack(side="left", padx=(6, 0))
            self._file_caption = aura.Caption(bar, "Untitled")
            self._file_caption.pack(side="left", padx=(14, 0))

            self._mono_switch = aura.Switch(
                bar, text="Monospace", command=self._on_mono_switch)
            self._mono_switch.pack(side="right")
            (self._mono_switch.select if self._mono
             else self._mono_switch.deselect)()
            self._wrap_switch = aura.Switch(
                bar, text="Word wrap", command=self._on_wrap_switch)
            self._wrap_switch.pack(side="right", padx=(0, 16))
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
            fb.grid_columnconfigure(1, weight=1)

            row1 = ctk.CTkFrame(fb, fg_color="transparent")
            row1.grid(row=0, column=0, columnspan=2, sticky="ew",
                      padx=10, pady=(8, 2))
            self.find_entry = aura.AuraEntry(row1, placeholder="Find…")
            self.find_entry.pack(side="left", fill="x", expand=True)
            self.find_entry.bind("<Return>", lambda _e: self._find_step(False))
            self.find_entry.bind("<Shift-Return>",
                                 lambda _e: self._find_step(True))
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
            row2.grid(row=1, column=0, columnspan=2, sticky="ew",
                      padx=10, pady=(2, 8))
            self.replace_entry = aura.AuraEntry(row2,
                                                placeholder="Replace with…")
            self.replace_entry.pack(side="left", fill="x", expand=True)
            aura.AuraButton(row2, "Replace", kind="secondary", height=28,
                            width=76, command=self._replace_one
                            ).pack(side="left", padx=(8, 0))
            aura.AuraButton(row2, "Replace All", kind="ghost", height=28,
                            width=96, command=self._replace_all
                            ).pack(side="left", padx=(6, 0))
            self._case_switch = aura.Switch(row2, text="Match case")
            self._case_switch.pack(side="left", padx=(12, 0))
            self._word_switch = aura.Switch(row2, text="Whole word")
            self._word_switch.pack(side="left", padx=(10, 0))

            # ---- the editing surface: a plain tk.Text, nothing between the
            # user and their characters (native selection, real undo/redo).
            surface = ctk.CTkFrame(frame, fg_color=pair("surface"),
                                   corner_radius=10, border_width=1,
                                   border_color=pair("border"))
            surface.grid(row=2, column=0, sticky="nsew")
            surface.grid_columnconfigure(0, weight=1)
            surface.grid_rowconfigure(0, weight=1)

            self.text = tk.Text(
                surface, undo=True, autoseparators=True, maxundo=-1,
                wrap="word" if self._wrap else "none",
                relief="flat", borderwidth=0, highlightthickness=0,
                padx=10, pady=8, tabs=("1c",))
            ysb = aura.AuraScrollbar(surface, command=self.text.yview)
            self._xsb = aura.AuraScrollbar(surface, orientation="horizontal",
                                           command=self.text.xview)
            self.text.configure(yscrollcommand=ysb.set,
                                xscrollcommand=self._xsb.set)
            self.text.grid(row=0, column=0, sticky="nsew", padx=(6, 0),
                           pady=6)
            ysb.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=6)
            self._xsb.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 4))
            if self._wrap:
                self._xsb.grid_remove()
            aura.track(self.text, "text")
            self._apply_font()

            # ---- status strip (right side of the Aura status bar)
            act = self.statusbar.actions
            self._pos_lbl = aura.Caption(act, "Ln 1, Col 1")
            self._count_lbl = aura.Caption(act, "0 chars")
            self._enc_lbl = aura.Caption(act, self.doc.encoding_label)
            self._eol_lbl = aura.Caption(act, self.doc.eol_label)
            self._zoom_lbl = aura.Caption(act, f"{self._font_size} pt")
            for lbl in (self._pos_lbl, self._count_lbl, self._enc_lbl,
                        self._eol_lbl, self._zoom_lbl):
                lbl.pack(side="left", padx=(0, 14))

            self._bind_keys()
            self.text.edit_modified(False)
            self.text.bind("<<Modified>>", self._on_modified)
            self.text.focus_set()
            self._refresh_position()

        # ---- key bindings.  tk.Text ships emacs-style class bindings for
        # Ctrl+O (insert line), Ctrl+F (cursor forward), Ctrl+H (backspace)…
        # Binding on the widget and returning "break" beats them all.
        def _bind_keys(self):
            t = self.text

            def on(widget, seq, fn):
                widget.bind(seq, lambda _e, f=fn: (f(), "break")[1])

            on(t, "<Control-n>", self._new_file)
            on(t, "<Control-o>", self._open_dialog)
            on(t, "<Control-s>", self._save)
            on(t, "<Control-S>", self._save_as)          # Ctrl+Shift+S
            on(t, "<Control-f>", lambda: self._show_find(False))
            on(t, "<Control-h>", lambda: self._show_find(True))
            on(t, "<Control-g>", self._goto_line)
            on(t, "<Control-a>", self._select_all)
            on(t, "<Control-y>", lambda: self._edit_event("<<Redo>>"))
            on(t, "<F5>", self._insert_timestamp)
            on(t, "<F3>", lambda: self._find_step(False))
            on(t, "<Shift-F3>", lambda: self._find_step(True))
            for seq in ("<Control-equal>", "<Control-plus>",
                        "<Control-KP_Add>"):
                on(t, seq, lambda: self._zoom(+1))
            for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
                on(t, seq, lambda: self._zoom(-1))
            for seq in ("<Control-0>", "<Control-KP_0>"):
                on(t, seq, lambda: self._zoom(0))
            t.bind("<Control-MouseWheel>",
                   lambda e: (self._zoom(+1 if e.delta > 0 else -1),
                              "break")[1])
            t.bind("<Control-Button-4>",
                   lambda _e: (self._zoom(+1), "break")[1])
            t.bind("<Control-Button-5>",
                   lambda _e: (self._zoom(-1), "break")[1])
            for seq in ("<KeyRelease>", "<ButtonRelease-1>"):
                t.bind(seq, lambda _e: self._refresh_position(), add="+")
            # window-level fallbacks so shortcuts work outside the Text too
            for seq, fn in (("<Control-n>", self._new_file),
                            ("<Control-o>", self._open_dialog),
                            ("<Control-s>", self._save),
                            ("<Control-S>", self._save_as),
                            ("<Control-g>", self._goto_line),
                            ("<F5>", self._insert_timestamp)):
                self.bind(seq, lambda _e, f=fn: (f(), "break")[1])
            self.bind("<Escape>", lambda _e: self._hide_find())

        # =================================================================
        # Document plumbing
        # =================================================================
        def _get_text(self):
            return self.text.get("1.0", "end-1c")

        def _set_text(self, value):
            self.text.delete("1.0", "end")
            self.text.insert("1.0", value)
            self.text.edit_reset()
            self.text.edit_modified(False)
            self._dirty = False
            self.text.mark_set("insert", "1.0")
            self.text.see("insert")

        def _on_modified(self, _e=None):
            if self.text.edit_modified():
                self.text.edit_modified(False)
                if not self._dirty:
                    self._dirty = True
                    self._refresh_title()
            self._refresh_position()

        def _display_name(self):
            return os.path.basename(self.path) if self.path else "Untitled"

        def _refresh_title(self):
            star = "• " if self._dirty else ""
            self.title(f"{star}{self._display_name()} — {WINDOW_TITLE}")
            if hasattr(self, "_file_caption"):
                self._file_caption.configure(
                    text=star + (self.path or "Untitled"))

        def _refresh_position(self):
            if not hasattr(self, "_pos_lbl"):
                return
            line, col = self.text.index("insert").split(".")
            self._pos_lbl.configure(text=f"Ln {line}, Col {int(col) + 1}")
            c = textio.counts(self._get_text())
            self._count_lbl.configure(
                text=f"{c['chars']} chars · {c['words']} words")

        def _refresh_doc_labels(self):
            self._enc_lbl.configure(text=self.doc.encoding_label)
            self._eol_lbl.configure(text=self.doc.eol_label)
            self._refresh_title()
            self._refresh_position()

        def _confirm_discard(self):
            """True when it is safe to drop the buffer (saving if asked)."""
            if not self._dirty:
                return True
            answer = messagebox.askyesnocancel(
                APP_NAME,
                f"Do you want to save changes to {self._display_name()}?",
                parent=self)
            if answer is None:
                return False
            if answer:
                return self._save()
            return True

        # =================================================================
        # File commands
        # =================================================================
        def _new_file(self):
            if not self._confirm_discard():
                return
            self.doc = textio.Document()
            self.path = None
            self._set_text("")
            self._refresh_doc_labels()
            self.set_status("New file")

        def _open_dialog(self):
            if not self._confirm_discard():
                return
            path = filedialog.askopenfilename(
                parent=self, title="Open text file",
                initialdir=guiconfig.default_open_dir(),
                filetypes=FILETYPES)
            if path:
                self._open_path(path, confirmed=True)

        def _open_path(self, path, confirmed=False):
            if not confirmed and not self._confirm_discard():
                return
            path = guiconfig.norm_path(path)
            try:
                self.doc = textio.load_file(path)
            except PlainTextEditorError as exc:
                guiconfig.remove_recent(path)
                self.set_error(str(exc))
                return
            self.path = path
            self._set_text(self.doc.text)
            guiconfig.add_recent(path)
            guiconfig.set_last_dir(os.path.dirname(path))
            self._refresh_doc_labels()
            self.set_status(
                f"Opened {self._display_name()} "
                f"({self.doc.encoding_label}, {self.doc.eol_label})")

        def _save(self):
            if not self.path:
                return self._save_as()
            return self._write_to(self.path)

        def _save_as(self):
            path = filedialog.asksaveasfilename(
                parent=self, title="Save as",
                initialdir=(os.path.dirname(self.path) if self.path
                            else guiconfig.default_open_dir()),
                initialfile=self._display_name()
                if self.path else "Untitled.txt",
                defaultextension=".txt", filetypes=FILETYPES)
            if not path:
                return False
            return self._write_to(guiconfig.norm_path(path))

        def _write_to(self, path):
            self.doc.text = self._get_text()
            try:
                textio.save_file(path, self.doc)
            except PlainTextEditorError as exc:
                self.set_error(str(exc))
                return False
            self.path = path
            self._dirty = False
            self.doc.mixed_eol = False   # saved uniformly in the dominant EOL
            self.text.edit_modified(False)
            guiconfig.add_recent(path)
            guiconfig.set_last_dir(os.path.dirname(path))
            self._refresh_doc_labels()
            self.set_success(
                f"Saved {self._display_name()} "
                f"({self.doc.encoding_label}, {self.doc.eol_label})")
            return True

        # =================================================================
        # Edit commands
        # =================================================================
        def _edit_event(self, virtual):
            try:
                self.text.event_generate(virtual)
            except tk.TclError:
                pass  # empty undo/redo stack or empty clipboard

        def _select_all(self):
            self.text.tag_add("sel", "1.0", "end-1c")
            self.text.mark_set("insert", "end-1c")

        def _insert_timestamp(self):
            self.text.insert("insert", editing.f5_stamp())
            self._refresh_position()

        def _goto_line(self):
            total = editing.line_count(self._get_text())
            line = simpledialog.askinteger(
                "Go To Line", f"Line number (1–{total}):", parent=self,
                minvalue=1, maxvalue=total)
            if line is None:
                return
            self.text.mark_set("insert", f"{line}.0")
            self.text.see("insert")
            self.text.focus_set()
            self._refresh_position()

        # ---- find & replace --------------------------------------------
        def _show_find(self, replace=False):
            self._find_bar.grid()
            try:  # pre-fill with the current selection
                sel = self.text.get("sel.first", "sel.last")
                if sel and "\n" not in sel:
                    self.find_entry.delete(0, "end")
                    self.find_entry.insert(0, sel)
            except tk.TclError:
                pass
            (self.replace_entry if replace else self.find_entry).focus_set()

        def _hide_find(self):
            self._find_bar.grid_remove()
            self.text.focus_set()

        def _find_args(self):
            needle = self.find_entry.get()
            if not needle:
                self.set_status("Type something to find")
                return None
            return {"needle": needle,
                    "match_case": bool(self._case_switch.get()),
                    "whole_word": bool(self._word_switch.get())}

        def _insert_offset(self):
            return len(self.text.get("1.0", "insert"))

        def _select_span(self, span):
            start, end = span
            self.text.tag_remove("sel", "1.0", "end")
            self.text.tag_add("sel", f"1.0+{start}c", f"1.0+{end}c")
            self.text.mark_set("insert", f"1.0+{end}c")
            self.text.see("insert")
            self._refresh_position()

        def _find_step(self, backwards):
            args = self._find_args()
            if not args:
                return
            text = self._get_text()
            start = self._insert_offset()
            if backwards:
                try:  # step over the current selection so Prev moves
                    if self.text.get("sel.first", "sel.last"):
                        start = len(self.text.get("1.0", "sel.first")) \
                            + len(args["needle"])
                except tk.TclError:
                    pass
            span = editing.find_next(text, start=start,
                                     backwards=backwards, **args)
            if span is None:
                self.set_status(f"Cannot find \"{args['needle']}\"")
                return
            self._select_span(span)
            self.set_status("")

        def _replace_one(self):
            args = self._find_args()
            if not args:
                return
            replacement = self.replace_entry.get()
            try:
                sel = self.text.get("sel.first", "sel.last")
            except tk.TclError:
                sel = None
            if sel is not None:
                matches = editing.find_all(sel, args["needle"],
                                           args["match_case"],
                                           args["whole_word"])
                if matches == [(0, len(sel))]:
                    self.text.delete("sel.first", "sel.last")
                    self.text.insert("insert", replacement)
            self._find_step(False)

        def _replace_all(self):
            args = self._find_args()
            if not args:
                return
            new_text, count = editing.replace_all(
                self._get_text(), args["needle"],
                self.replace_entry.get(), args["match_case"],
                args["whole_word"])
            if not count:
                self.set_status(f"Cannot find \"{args['needle']}\"")
                return
            self.text.edit_separator()
            insert = self.text.index("insert")
            self.text.delete("1.0", "end")
            self.text.insert("1.0", new_text)
            self.text.mark_set("insert", insert)
            self.text.see("insert")
            self.set_success(f"Replaced {count} occurrence(s)")
            self._refresh_position()

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
            self.text.configure(wrap="word" if self._wrap else "none")
            if self._wrap:
                self._xsb.grid_remove()
            else:
                self._xsb.grid()
            guiconfig.set_wrap(self._wrap)

        def _on_mono_switch(self):
            self._mono_var.set(bool(self._mono_switch.get()))
            self._apply_font()

        def _apply_font(self):
            self._mono = bool(self._mono_var.get())
            if hasattr(self, "_mono_switch"):
                (self._mono_switch.select if self._mono
                 else self._mono_switch.deselect)()
            family = MONO_FAMILY if self._mono else UI_FAMILY
            self.text.configure(font=(family, self._font_size))
            guiconfig.set_mono(self._mono)

        def _zoom(self, direction):
            if direction == 0:
                self._font_size = guiconfig.DEFAULT_FONT
            else:
                self._font_size = max(guiconfig.MIN_FONT,
                                      min(guiconfig.MAX_FONT,
                                          self._font_size + direction))
            guiconfig.set_font_size(self._font_size)
            self._apply_font()
            self._zoom_lbl.configure(text=f"{self._font_size} pt")

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
                text="A fast, clean, offline plain-text editor in the "
                     "spirit of Windows Notepad: open, edit and save text "
                     "files — nothing between you and your characters.\n\n"
                     "Your file's encoding (UTF-8, UTF-8 BOM, UTF-16, ANSI) "
                     "and line endings (CRLF/LF) are detected on open, shown "
                     "in the status bar, and preserved exactly on save.\n\n"
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
            if not self._confirm_discard():
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
              f"the GUI here ({exc}). This app is intended for the Windows "
              f"desktop.")
        return 0
    except Exception as exc:
        print(f"{APP_NAME}: could not start the GUI ({exc}).")
        return 1

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
