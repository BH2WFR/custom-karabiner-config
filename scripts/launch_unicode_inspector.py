#!/usr/bin/env python3
"""Copy the selection and open the Unicode Inspector from PersonalScripts."""

import argparse
import fcntl
from pathlib import Path
import subprocess
import sys

import keyboard_events as keys
import secondary_clipboard as clipboard
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


def prepare_transfer():
    # Share the text-action lock so selection copies do not overlap transforms.
    with open(Path(__file__).with_name("text_actions.py"), "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        text = capture_selection(clipboard.NSPasteboard.generalPasteboard())
    board = clipboard.NSPasteboard.pasteboardWithUniqueName()
    try:
        clipboard.restore_pasteboard(board, clipboard.text_snapshot(text))
        return board
    except Exception:
        board.releaseGlobally()
        raise


def launch_inspector(script, board):
    command = [
        "/usr/bin/open", "-g", "-n", "-a", str(Path(sys.prefix) / "python.app"),
        "--env", f"PYTHONEXECUTABLE={sys.executable}", "--args", str(script),
    ]
    try:
        if board is not None:
            command.extend(["--consume-pasteboard", str(board.name())])
        subprocess.run(command, check=True)
    except Exception:
        if board is not None:
            board.releaseGlobally()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspector", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        script = args.inspector.expanduser().resolve(strict=True)
        error = None
        try:
            board = prepare_transfer()
        except Exception as exc:
            board = None
            error = f"{exc} Paste or enter text manually."
            print(error, file=sys.stderr)
        launch_inspector(script, board)
        if error:
            notify(error, level="error")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        notify(str(exc), level="error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
