#!/usr/bin/env python3
"""Copy the selection before opening a PersonalScripts clipboard tool."""

import argparse
import fcntl
from pathlib import Path
import subprocess
import sys

from launch_external_tool import open_tool
from tooltip import notify


def copy_selection(*, text_only):
    import keyboard_events as keys
    import secondary_clipboard as clipboard
    from text_actions import _frontmost_pid

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
        if {"public.file-url", "NSFilenamesPboardType"} & set(board.types() or []):
            if text_only:
                raise RuntimeError("The selection contains files, not text.")
        elif not board.stringForType_(clipboard.TEXT_TYPE):
            raise RuntimeError("The selection contains no text.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    tool = parser.add_mutually_exclusive_group(required=True)
    tool.add_argument("--inspector", type=Path)
    tool.add_argument("--processor", type=Path)
    tool.add_argument("--copy-only", choices=("text", "text-or-files"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.copy_only:
        try:
            copy_selection(text_only=args.copy_only == "text")
        except Exception as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0
    try:
        script = (args.inspector or args.processor).expanduser().resolve(strict=True)
        error = None
        try:
            result = subprocess.run(
                [sys.executable, __file__, "--copy-only", "text" if args.inspector else "text-or-files"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode:
                error = result.stderr.strip() or "Cannot copy the selection."
        except subprocess.TimeoutExpired:
            error = "Copying the selection timed out."
        except OSError as exc:
            error = str(exc)
        if error:
            open_tool(script)
            notify(f"{error} Paste or enter text manually.", level="error")
        else:
            open_tool(script, "--clip")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        notify(str(exc), level="error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
