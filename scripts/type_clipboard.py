#!/usr/bin/env python3
"""Type clipboard ASCII as US-layout key events, for browser VNC consoles."""

import argparse
import fcntl
import importlib
import sys
import time
from typing import Any

import keyboard_events as keys
from tooltip import notify

AppKit: Any = importlib.import_module("AppKit")
TEXT_TYPE = "public.utf8-plain-text"

# ANSI virtual keycodes from HIToolbox/Events.h, not character codes.
US_KEYS = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5,
    "z": 6, "x": 7, "c": 8, "v": 9, "b": 11,
    "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
    "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
    "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35,
    "\n": 36, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41,
    "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47,
    "\t": 48, " ": 49, "`": 50,
}
SHIFTED_KEYS = dict(zip('~!@#$%^&*()_+{}|:"<>?', "`1234567890-=[]\\;',./"))


def plan_keystrokes(text):
    """Validate everything before any event is posted; CRLF is one Return."""
    strokes = []
    for index, char in enumerate(text.replace("\r\n", "\n").replace("\r", "\n")):
        if "A" <= char <= "Z":
            base, shifted = char.lower(), True
        elif char in SHIFTED_KEYS:
            base, shifted = SHIFTED_KEYS[char], True
        else:
            base, shifted = char, False
        if base not in US_KEYS:
            raise ValueError(
                f"Unsupported character U+{ord(char):04X} at position {index + 1}; "
                "only printable ASCII, Tab and line breaks are supported."
            )
        strokes.append((US_KEYS[base], shifted))
    return strokes


def type_text(text, interval=0.01):
    strokes = plan_keystrokes(text)
    if not strokes:
        raise ValueError("The clipboard has no text to type.")
    workspace = AppKit.NSWorkspace.sharedWorkspace()
    target_pid = workspace.frontmostApplication().processIdentifier()
    # Lock the script itself: concurrent shortcuts cannot interleave, no temp file.
    with open(__file__, "rb") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Keyboard typing is already in progress.") from None
        if not keys.can_post_events():
            raise RuntimeError("Python needs Accessibility permission to type.")
        keys.release_modifiers()
        keys.release_keys(US_KEYS["z"])
        time.sleep(0.05)
        shifted = False
        try:
            for code, needs_shift in strokes:
                if (workspace.frontmostApplication().processIdentifier() != target_pid
                        or keys.is_key_down(keys.ESCAPE_KEY_CODE)):
                    raise RuntimeError("Typing stopped: focus changed or Escape was pressed.")
                if shifted != needs_shift:
                    shifted = needs_shift
                    keys.post_key_event(keys.LEFT_SHIFT_KEY_CODE, shifted,
                                        keys.SHIFT_FLAG if shifted else 0)
                    time.sleep(interval)
                flags = keys.SHIFT_FLAG if shifted else 0
                try:
                    keys.post_key_event(code, True, flags)
                    time.sleep(interval)
                finally:
                    keys.post_key_event(code, False, flags)
                time.sleep(interval)
        finally:
            if shifted:
                keys.release_keys(keys.LEFT_SHIFT_KEY_CODE)


def type_from_pasteboard(pasteboard, interval=0.01):
    text = pasteboard.stringForType_(TEXT_TYPE)
    try:
        type_text(str(text) if text is not None else "", interval)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        notify(str(exc), level="warning" if isinstance(exc, ValueError) else "error")
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasteboard-name", help="default: general clipboard")
    parser.add_argument("--interval-ms", type=float, default=10, help="delay between events")
    args = parser.parse_args()
    if not 1 <= args.interval_ms <= 1000:
        parser.error("--interval-ms must be between 1 and 1000")
    pasteboard = (AppKit.NSPasteboard.pasteboardWithName_(args.pasteboard_name)
                  if args.pasteboard_name else AppKit.NSPasteboard.generalPasteboard())
    return type_from_pasteboard(pasteboard, args.interval_ms / 1000)


if __name__ == "__main__":
    sys.exit(main())
