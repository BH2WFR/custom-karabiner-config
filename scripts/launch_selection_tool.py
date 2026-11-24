#!/usr/bin/env python3
"""Copy the selection before opening a PersonalScripts clipboard tool."""

import argparse
import fcntl
from pathlib import Path
import subprocess
import sys

import keyboard_events as keys
import secondary_clipboard as clipboard
from text_actions import _frontmost_pid
from tooltip import notify


def copy_selection(*, text_only):
    if not keys.can_post_events():
        raise RuntimeError("Python needs Accessibility permission to copy selected text.")
    with open(Path(__file__).with_name("text_actions.py"), "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        target = _frontmost_pid()
        board = clipboard.NSPasteboard.generalPasteboard()
        if not clipboard.send_selection_to_general(board, keys.C_KEY_CODE):
            raise RuntimeError("Cannot copy selected text.")
        if _frontmost_pid() != target:
            raise RuntimeError("Active application changed.")
        if text_only:
            if {"public.file-url", "NSFilenamesPboardType"} & set(board.types() or []):
                raise RuntimeError("The selection contains files, not text.")
            if not board.stringForType_(clipboard.TEXT_TYPE):
                raise RuntimeError("The selection contains no text.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    tool = parser.add_mutually_exclusive_group(required=True)
    tool.add_argument("--inspector", type=Path)
    tool.add_argument("--processor", type=Path)
    args = parser.parse_args(argv)
    try:
        script = (args.inspector or args.processor).expanduser().resolve(strict=True)
        command = [
            "/usr/bin/open", "-n", "-a", str(Path(sys.prefix) / "python.app"),
            "--env", f"PYTHONEXECUTABLE={sys.executable}", "--args", str(script),
        ]
        error = None
        try:
            copy_selection(text_only=args.inspector is not None)
        except Exception as exc:
            error = f"{exc} Paste or enter text manually."
            print(exc, file=sys.stderr)
        if args.processor or error is None:
            command.append("--clip")
        subprocess.run(command, check=True)
        if error and args.inspector:
            notify(error, level="error")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        notify(str(exc), level="error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
