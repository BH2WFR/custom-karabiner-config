#!/usr/bin/env python3
"""Copy the selection and open the Unicode Inspector from PersonalScripts."""

import argparse
import fcntl
import json
from pathlib import Path
import runpy
import subprocess
import sys
import uuid

import keyboard_events as keys
import secondary_clipboard as clipboard
from gui_helpers import activate_window
from paste_without_format import read_clipboard_text
from text_actions import _frontmost_pid
from tooltip import notify


def capture_selection(pasteboard):
    if not keys.can_post_events():
        raise RuntimeError("Python needs Accessibility permission to copy selected text.")
    target = _frontmost_pid()
    original_count = pasteboard.changeCount()
    original = clipboard.snapshot_pasteboard(pasteboard)
    if pasteboard.changeCount() != original_count:
        raise RuntimeError("Clipboard changed. Please try again.")
    owned_count = None
    try:
        if not clipboard.send_selection_to_general(pasteboard, keys.C_KEY_CODE):
            raise RuntimeError("Cannot copy selected text.")
        owned_count = pasteboard.changeCount()
        if {"public.file-url", "NSFilenamesPboardType"} & set(pasteboard.types() or []):
            raise RuntimeError("The selection contains files, not text.")
        text = read_clipboard_text(prefer_paths=False)
        if _frontmost_pid() != target:
            raise RuntimeError("Active application changed. Copy cancelled.")
        if pasteboard.changeCount() != owned_count:
            raise RuntimeError("Clipboard changed. Copy cancelled.")
        if not text:
            raise RuntimeError("The selection contains no text.")
        return str(text)
    finally:
        if owned_count is not None and pasteboard.changeCount() == owned_count:
            clipboard.restore_pasteboard(pasteboard, original)


def launch_inspector(script, text, error_message=None):
    # Private pasteboard avoids temporary files, command-line text and argv limits.
    name = f"com.personal-scripts.unicode-inspector.{uuid.uuid4()}"
    board = clipboard.NSPasteboard.pasteboardWithName_(name)
    try:
        payload = json.dumps({"text": text, "error": error_message})
        clipboard.restore_pasteboard(board, clipboard.text_snapshot(payload))
        command = [
            "/usr/bin/open", "-F", "-n", "-a", str(Path(sys.prefix) / "python.app"),
            "--env", f"PYTHONEXECUTABLE={sys.executable}",
            "--args", str(Path(__file__).resolve()),
            "--inspector", str(script), "--pasteboard", name,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Cannot open Python.app.")
    except Exception:
        board.releaseGlobally()
        raise


def run_inspector(script, pasteboard_name):
    board = clipboard.NSPasteboard.pasteboardWithName_(pasteboard_name)
    try:
        payload = board.stringForType_(clipboard.TEXT_TYPE)
        data = json.loads(str(payload)) if payload is not None else {
            "text": "", "error": "Cannot read selected text. Paste or enter text manually."}
    finally:
        board.releaseGlobally()

    namespace = runpy.run_path(str(script))
    import tkinter as tk

    root = tk.Tk()
    try:
        namespace["UnicodeInspector"](root, data["text"])
        if data["error"]:
            def show_error():
                try:
                    subprocess.Popen(
                        [sys.executable, str(Path(__file__).with_name("tooltip.py")),
                         data["error"], "--level", "error"],
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
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspector", type=Path, required=True)
    parser.add_argument("--pasteboard", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.pasteboard:
            run_inspector(args.inspector, args.pasteboard)
            return 0
        script = args.inspector.expanduser().resolve(strict=True)
        # Share the text-action lock so selection copies do not overlap transforms.
        with open(Path(__file__).with_name("text_actions.py"), "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                text = capture_selection(clipboard.NSPasteboard.generalPasteboard())
                error = None
            except Exception as exc:
                print(str(exc), file=sys.stderr)
                text, error = "", f"{exc} Paste or enter text manually."
        launch_inspector(script, text, error)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        notify(str(exc), level="error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
