#!/usr/bin/env python3
"""Transform selected text or paste clipboard-derived text."""

import argparse
import fcntl
import re
import sys
import time

import keyboard_events as keys
import secondary_clipboard as clipboard
from paste_without_format import read_clipboard_text
from tooltip import notify

SELECTION_ACTIONS = ("wrap", "lower", "upper", "title")
LITERAL_ACTIONS = {"tab": "\t", "newline": "\n"}
WORDS = re.compile(r"\w+(?:['\u2019]\w+)*")


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(*SELECTION_ACTIONS, *LITERAL_ACTIONS, "setter", "getter"))
    args = parser.parse_args()
    try:
        with open(__file__, "rb") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("A text action is already in progress.") from None
            if not keys.can_post_events():
                raise RuntimeError("Python needs Accessibility permission for text actions.")
            perform_action(args.action, clipboard.NSPasteboard.generalPasteboard())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        notify(str(exc), level="warning" if isinstance(exc, ValueError) else "error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
