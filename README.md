# Plain Text Editor

A fast, **offline**, **100% open-source** plain-text editor for Windows. Nothing is uploaded anywhere. Built entirely by AI with human testing and guidance, and published on [QuickOpen](https://quickopen.ai/projects/plain-text-editor).

> **100% AI-built and open source.** Apache-2.0.

## What it does

Open, edit and save plain text files the way Windows Notepad does — instantly, with zero clutter and zero lock-in. Find & replace, go-to-line, word wrap, font zoom and an F5 time/date stamp cover the essentials, while the status bar always shows your line, column, encoding and line endings. UTF-8, UTF-16 and ANSI files keep their exact encoding, BOM and CRLF/LF endings on save. Recent files, unsaved-change prompts and full keyboard shortcuts included. No rich text, no telemetry — just text.

## Install

Download **`PlainTextEditor-Setup.exe`** from the [QuickOpen page](https://quickopen.ai/projects/plain-text-editor) or the [GitHub release](https://github.com/quickpod/plain-text-editor/releases/latest) and double-click it. It installs per-user, adds Desktop and Start Menu shortcuts, and can optionally trust the QuickOpen Root CA. Authenticode-signed by the QuickOpen Code Signing CA — verify at [quickopen.ai/trust](https://quickopen.ai/trust).

## Run from source

```sh
pip install -r requirements.txt
python plain_text_editor_app.py              # GUI
python plain_text_editor_app.py notes.txt    # GUI, opening a file
python -m plaintexteditor --help             # CLI
```


## Features

- **Notepad, done right** — new / open / save / save-as, recent files, unsaved-change prompts, and a plain editing surface with native selection and real undo/redo. No rich text, no Markdown rendering — plain text only.
- **Encoding-faithful** — UTF-8 (default), UTF-8 BOM, UTF-16 LE/BE and legacy ANSI files are detected on open, shown in the status bar, and written back **byte-for-byte identical** (BOM included) on save.
- **Line endings preserved** — CRLF vs LF (even lone CR) is detected, displayed, and kept exactly as it was; new files use your platform's native ending.
- **Find & replace** — slide-in bar with next/previous, match case, whole word, and replace one/all. `F3`/`Shift+F3` repeat the search.
- **Go to line** (`Ctrl+G`), **word wrap** toggle, **monospace/proportional** font toggle, and **zoom** (`Ctrl+=` / `Ctrl+-` / `Ctrl+0`, or Ctrl+scroll).
- **Status bar** — line & column, character/word count, encoding, line endings and font size, always visible.
- **`F5` time/date stamp** — inserts `10:35 PM 8/12/2026` at the cursor, just like Notepad.
- **Open from anywhere** — pass a file on the command line (or use "Open with" / drag onto the exe) and it opens in the editor.
- **Everything offline** — nothing is ever uploaded, no telemetry. Dark and light themes.
- **Library + CLI + GUI** — the tested `plaintexteditor` package powers the desktop app and a scriptable command line.

## Keyboard shortcuts

| Shortcut | Action | Shortcut | Action |
|---|---|---|---|
| `Ctrl+N` | New file | `Ctrl+F` | Find |
| `Ctrl+O` | Open… | `Ctrl+H` | Replace |
| `Ctrl+S` | Save | `F3` / `Shift+F3` | Find next / previous |
| `Ctrl+Shift+S` | Save As… | `Ctrl+G` | Go to line |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo | `F5` | Insert time/date |
| `Ctrl+A` | Select all | `Ctrl+=` / `Ctrl+-` / `Ctrl+0` | Zoom in / out / reset |

## CLI examples

```sh
python -m plaintexteditor cat notes.txt          # print a file, decoded like the editor
python -m plaintexteditor cat -n notes.txt       # ...with line numbers
python -m plaintexteditor count notes.txt        # lines / words / chars
python -m plaintexteditor detect *.txt           # encoding + BOM + line endings
python -m plaintexteditor recent                 # recently opened files
python -m plaintexteditor recent --clear
```

Commands exit cleanly with a one-line `error: ...` message (never a traceback) when something goes wrong.

## License

Apache-2.0 — see [LICENSE](LICENSE). A 100% AI-built project published on QuickOpen.
