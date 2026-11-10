#!/usr/bin/env python3
"""Transform selected text, inspect text statistics, or paste clipboard-derived text."""

import argparse
import fcntl
import re
import subprocess
import sys
import time
import unicodedata
import uuid
from pathlib import Path

import keyboard_events as keys
import secondary_clipboard as clipboard
from paste_without_format import read_clipboard_text
from tooltip import notify
from gui_helpers import activate_window, copy_text

SELECTION_ACTIONS = ("wrap", "lower", "upper", "title", "stats")
LITERAL_ACTIONS = {"tab": "\t", "newline": "\n"}
WORDS = re.compile(r"\w+(?:['\u2019]\w+)*")
CHARACTER_LABELS = {
    "\x00": "[NUL]", "\x01": "[SOH]", "\x02": "[STX]", "\x03": "[ETX]",
    "\x04": "[EOT]", "\x05": "[ENQ]", "\x06": "[ACK]", "\x07": "[BEL]",
    "\x08": "[BS]", "\x09": "[TAB]", "\x0a": "[LF]", "\x0b": "[VT]",
    "\x0c": "[FF]", "\x0d": "[CR]", "\x0e": "[SO]", "\x0f": "[SI]",
    "\x10": "[DLE]", "\x11": "[DC1]", "\x12": "[DC2]", "\x13": "[DC3]",
    "\x14": "[DC4]", "\x15": "[NAK]", "\x16": "[SYN]", "\x17": "[ETB]",
    "\x18": "[CAN]", "\x19": "[EM]", "\x1a": "[SUB]", "\x1b": "[ESC]",
    "\x1c": "[FS]", "\x1d": "[GS]", "\x1e": "[RS]", "\x1f": "[US]",
    " ": "[SPACE]", "\x7f": "[DEL]", "\u00a0": "[NBSP]",
    "\u2000": "[EN QUAD]", "\u2001": "[EM QUAD]", "\u2002": "[EN SPACE]",
    "\u2003": "[EM SPACE]", "\u2004": "[THREE-PER-EM SPACE]",
    "\u2005": "[FOUR-PER-EM SPACE]", "\u2006": "[SIX-PER-EM SPACE]",
    "\u2007": "[FIGURE SPACE]", "\u2008": "[PUNCTUATION SPACE]",
    "\u2009": "[THIN SPACE]", "\u200a": "[HAIR SPACE]", "\u200b": "[ZWSP]",
    "\u200c": "[ZWNJ]", "\u200d": "[ZWJ]", "\u200e": "[LRM]",
    "\u200f": "[RLM]", "\u2028": "[LSEP]", "\u2029": "[PSEP]",
    "\u202a": "[LRE]", "\u202b": "[RLE]", "\u202c": "[PDF]",
    "\u202d": "[LRO]", "\u202e": "[RLO]", "\u202f": "[NARROW NBSP]",
    "\u205f": "[MEDIUM MATHEMATICAL SPACE]", "\u2060": "[WJ]",
    "\u3000": "[IDEOGRAPHIC SPACE]", "\ufeff": "[BOM/ZWNBSP]",
    "\ufff9": "[INTERLINEAR ANNOTATION ANCHOR]",
    "\ufffa": "[INTERLINEAR ANNOTATION SEPARATOR]",
    "\ufffb": "[INTERLINEAR ANNOTATION TERMINATOR]", "\ufffc": "[OBJECT]",
    "\ufffd": "[REPLACEMENT]", "\ufffe": "[NONCHARACTER]", "\uffff": "[NONCHARACTER]",
}
CATEGORY_NAMES = {
    "Cc": "Control", "Cf": "Format", "Cn": "Unassigned", "Co": "Private use",
    "Cs": "Surrogate", "Ll": "Lowercase letter", "Lm": "Modifier letter",
    "Lo": "Other letter", "Lt": "Titlecase letter", "Lu": "Uppercase letter",
    "Mc": "Spacing mark", "Me": "Enclosing mark", "Mn": "Nonspacing mark",
    "Nd": "Decimal number", "Nl": "Letter number", "No": "Other number",
    "Pc": "Connector punctuation", "Pd": "Dash punctuation", "Pe": "Close punctuation",
    "Pf": "Final punctuation", "Pi": "Initial punctuation", "Po": "Other punctuation",
    "Ps": "Open punctuation", "Sc": "Currency symbol", "Sk": "Modifier symbol",
    "Sm": "Math symbol", "So": "Other symbol", "Zl": "Line separator",
    "Zp": "Paragraph separator", "Zs": "Space separator",
}
PYTHON_APP = str(Path(sys.prefix) / "python.app")
PYTHON_EXECUTABLE = sys.executable
INSPECTOR_PASTEBOARD_PREFIX = "com.personal-scripts.unicode-inspector"


def transform_text(action, text):
    if action in LITERAL_ACTIONS:
        return LITERAL_ACTIONS[action]
    if not text:
        raise ValueError("No text is available.")
    if action == "wrap":
        return "${" + text + "}"
    if action == "lower":
        return text.lower()
    if action == "upper":
        return text.upper()
    if action == "title":
        return WORDS.sub(lambda match: match[0][:1].upper() + match[0][1:].lower(), text)
    if action in ("setter", "getter"):
        name = text.strip()
        if not name or any(char.isspace() for char in name):
            raise ValueError("Copy a single name without spaces or line breaks.")
        prefix = "set" if action == "setter" else "get"
        return prefix + name[:1].upper() + name[1:]
    raise ValueError(f"Unknown text action: {action}")


def text_statistics(text):
    return {
        "Characters": len(text),
        "UTF-8 bytes": len(text.encode("utf-8")),
        "UTF-16 bytes": len(text.encode("utf-16-le")),
        "Words": len(WORDS.findall(text)),
        "Lines": text.replace("\r\n", "\n").replace("\r", "\n").count("\n") + 1 if text else 0,
    }


def unicode_character_rows(text):
    rows = []
    for index, character in enumerate(text):
        codepoint = ord(character)
        category = unicodedata.category(character)
        rows.append({
            "Index": index,
            "Character": CHARACTER_LABELS.get(
                character, character if character.isprintable() else repr(character)[1:-1]
            ),
            "Code point": f"U+{codepoint:04X}" if codepoint <= 0xFFFF else f"U+{codepoint:06X}",
            "Decimal": codepoint,
            "UTF-8": " ".join(f"{byte:02X}" for byte in character.encode("utf-8")),
            "Category": f"{category} - {CATEGORY_NAMES.get(category, 'Unknown')}",
            "Name": unicodedata.name(character, "<no Unicode name>"),
        })
    return rows


def character_style(character):
    if ord(character) > 0xFFFF:
        return "non_bmp"
    category = unicodedata.category(character)
    if category == "Cc":
        return "control"
    if character in CHARACTER_LABELS or category in ("Cf", "Zl", "Zp", "Zs"):
        return "special"
    if not character.isascii():
        return "non_ascii"
    return ""


def inspect_text(text):
    return {
        "text": text,
        "statistics": text_statistics(text),
        "characters": unicode_character_rows(text),
    }


def _require_inspector_text(text):
    if text is None or text == "":
        raise RuntimeError("Clipboard is empty or contains no text.")
    return str(text)


def _frontmost_pid():
    app = clipboard.AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        raise RuntimeError("No frontmost application.")
    return app.processIdentifier()


def perform_action(action, pasteboard):
    target = _frontmost_pid()
    original_count = pasteboard.changeCount()
    original = clipboard.snapshot_pasteboard(pasteboard)
    if pasteboard.changeCount() != original_count:
        raise RuntimeError("Clipboard changed. Please try again.")
    owned_count = original_count
    changed = False
    try:
        if action in SELECTION_ACTIONS:
            if not clipboard.send_selection_to_general(pasteboard, keys.C_KEY_CODE):
                if action == "stats":
                    raise RuntimeError("No text copied. Select text to inspect.")
                raise ValueError("Cannot copy selected text. Select some text first.")
            owned_count = pasteboard.changeCount()
            changed = True
            if {"public.file-url", "NSFilenamesPboardType"} & set(pasteboard.types() or []):
                raise ValueError("The selection contains files, not text.")

        text = "" if action in LITERAL_ACTIONS else read_clipboard_text(prefer_paths=False)
        if _frontmost_pid() != target:
            raise RuntimeError("Active application changed. Text action cancelled.")
        if pasteboard.changeCount() != owned_count:
            raise RuntimeError("Clipboard changed. Text action cancelled.")
        if action == "stats":
            return inspect_text(_require_inspector_text(text))
        result = transform_text(action, text)
        changed = True
        try:
            clipboard.restore_pasteboard(pasteboard, clipboard.text_snapshot(result))
        finally:
            owned_count = pasteboard.changeCount()
        if not clipboard.post_shortcut(keys.V_KEY_CODE):
            raise RuntimeError("Cannot paste text. Check Accessibility permission.")
        time.sleep(clipboard.PASTE_RESTORE_DELAY_SECONDS)
        return None
    finally:
        # Do not overwrite a newer clipboard copied by the user during this action.
        if changed and pasteboard.changeCount() == owned_count:
            clipboard.restore_pasteboard(pasteboard, original)


def format_report(report):
    statistics = "\n".join(f"{key}: {value}" for key, value in report["statistics"].items())
    columns = tuple(report["characters"][0]) if report["characters"] else ()
    characters = "\n".join(
        "\t".join(str(row[column]) for column in columns)
        for row in report["characters"]
    )
    header = "\t".join(columns)
    return f"Original text:\n{report['text']}\n\n{statistics}\n\n{header}\n{characters}".rstrip()


def build_inspector_window(root, report):
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText

    root.title("Unicode Text Inspector")
    root.minsize(760, 500)
    root.geometry("1000x720")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    body = ttk.Frame(root, padding=12)
    body.grid(sticky="nsew")
    body.columnconfigure(0, weight=1)
    body.rowconfigure(3, weight=1)

    state = {"report": report}
    header = ttk.Frame(body)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)
    ttk.Label(header, text="Original text").grid(row=0, column=0, sticky="w")
    original = ScrolledText(body, height=6, wrap="word", font="TkFixedFont")
    original.insert("1.0", report["text"])
    original.grid(row=1, column=0, sticky="nsew", pady=(4, 10))
    original.focus_set()

    def commit():
        render_report(inspect_text(original.get("1.0", "end-1c")))

    ttk.Button(header, text="Commit", command=commit).grid(row=0, column=1, sticky="e")

    summary = ttk.Frame(body)
    summary.grid(row=2, column=0, sticky="ew", pady=(0, 10))
    statistic_values = {}
    for column, (label, value) in enumerate(report["statistics"].items()):
        if column:
            ttk.Separator(summary, orient="vertical").grid(
                row=0, column=column * 3 - 1, sticky="ns", padx=6, pady=2)
        ttk.Label(summary, text=label).grid(row=0, column=column * 3, padx=(0, 4))
        statistic_values[label] = tk.StringVar(value=str(value))
        field = ttk.Entry(
            summary, width=max(5, len(str(value)) + 1), justify="right",
            textvariable=statistic_values[label], state="readonly",
        )
        field.grid(row=0, column=column * 3 + 1)

    columns = ("Index", "Character", "Code point", "Decimal", "UTF-8", "Category", "Name")
    table_frame = ttk.Frame(body)
    table_frame.grid(row=3, column=0, sticky="nsew")
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)
    table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
    table.tag_configure("control", foreground="#c62828")
    table.tag_configure("special", foreground="#2e7d32")
    table.tag_configure("non_ascii", foreground="#1565c0")
    table.tag_configure("non_bmp", foreground="#8b4513")
    widths = {"Index": 60, "Character": 145, "Code point": 90, "Decimal": 75,
              "UTF-8": 120, "Category": 170, "Name": 330}
    for column in columns:
        table.heading(column, text=column)
        table.column(column, width=widths[column], minwidth=50, stretch=column in ("Character", "Category", "Name"))

    def render_report(updated_report):
        state["report"] = updated_report
        for label, value in updated_report["statistics"].items():
            statistic_values[label].set(str(value))
        table.delete(*table.get_children())
        for character, row in zip(updated_report["text"], updated_report["characters"]):
            style = character_style(character)
            table.insert(
                "", "end", values=tuple(row[column] for column in columns),
                tags=(style,) if style else (),
            )

    render_report(report)
    vertical = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=table.xview)
    table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    table.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")

    def copy(value):
        copy_text(root, value)
        root.update()

    def copy_rows(event=None):
        selected = table.selection()
        if not selected:
            return "break"
        copy("\n".join("\t".join(map(str, table.item(item, "values"))) for item in selected))
        return "break"

    buttons = ttk.Frame(body)
    buttons.grid(row=4, column=0, sticky="e", pady=(10, 0))
    ttk.Button(
        buttons, text="Copy Original",
        command=lambda: copy(original.get("1.0", "end-1c")),
    ).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Copy Selected Rows", command=copy_rows).grid(row=0, column=1, padx=(0, 8))
    ttk.Button(
        buttons, text="Copy Full Report",
        command=lambda: copy(format_report(state["report"])),
    ).grid(row=0, column=2)
    table.bind("<Command-c>", copy_rows)
    root.bind("<Escape>", lambda event: root.destroy())
    root.bind("<Command-w>", lambda event: root.destroy())


def show_inspector(report, error_message=None):
    import tkinter as tk

    root = tk.Tk()
    build_inspector_window(root, report)

    if error_message:
        def show_error():
            try:
                subprocess.Popen(
                    [PYTHON_EXECUTABLE, str(Path(__file__).with_name("tooltip.py")),
                     error_message, "--level", "error"],
                    stdin=subprocess.DEVNULL, start_new_session=True,
                )
            except OSError as exc:
                print(f"Tooltip unavailable: {exc}", file=sys.stderr)

        def on_visible(event):
            if event.widget is root:
                root.unbind("<Map>", binding)
                root.after_idle(show_error)

        binding = root.bind("<Map>", on_visible, add="+")

    activate_window(root)
    root.mainloop()


def _inspector_pasteboard(name):
    return clipboard.NSPasteboard.pasteboardWithName_(name)


def launch_inspector(text, error_message=None):
    name = f"{INSPECTOR_PASTEBOARD_PREFIX}.{uuid.uuid4()}"
    pasteboard = _inspector_pasteboard(name)
    clipboard.restore_pasteboard(pasteboard, clipboard.text_snapshot(text))
    command = [
        "/usr/bin/open", "-F", "-n", "-a", PYTHON_APP,
        "--env", f"PYTHONEXECUTABLE={PYTHON_EXECUTABLE}",
        "--args", str(Path(__file__).resolve()),
        "--inspector-pasteboard", name,
    ]
    if error_message:
        command.extend(["--inspector-error", error_message])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        pasteboard.releaseGlobally()
        detail = result.stderr.strip() or "LaunchServices could not open Python.app."
        raise RuntimeError(detail)


def run_inspector(pasteboard_name, error_message=None):
    pasteboard = _inspector_pasteboard(pasteboard_name)
    try:
        text = pasteboard.stringForType_(clipboard.TEXT_TYPE)
        if text is None:
            error_message = error_message or "Cannot read inspector text. Paste or enter text manually."
        report = inspect_text(str(text) if text is not None else "")
    finally:
        pasteboard.releaseGlobally()
    show_inspector(report, error_message=error_message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", nargs="?", choices=(*SELECTION_ACTIONS, *LITERAL_ACTIONS, "setter", "getter")
    )
    parser.add_argument("--inspector-pasteboard", help=argparse.SUPPRESS)
    parser.add_argument("--inspector-error", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.inspector_pasteboard:
            if args.action:
                parser.error("action cannot be combined with --inspector-pasteboard")
            run_inspector(args.inspector_pasteboard, error_message=args.inspector_error)
            return 0
        if args.action is None:
            parser.error("the following arguments are required: action")
        error_message = None
        with open(__file__, "rb") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("A text action is already in progress.") from None
            try:
                if not keys.can_post_events():
                    raise RuntimeError("Python needs Accessibility permission for text actions.")
                report = perform_action(args.action, clipboard.NSPasteboard.generalPasteboard())
            except Exception as exc:
                if args.action != "stats":
                    raise
                print(str(exc), file=sys.stderr)
                error_message = f"{exc} Paste or enter text manually."
                report = inspect_text("")
        # Restore the original clipboard before opening an interactive Tk window.
        if report is not None:
            launch_inspector(report["text"], error_message=error_message)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        notify(str(exc), level="warning" if isinstance(exc, ValueError) else "error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
