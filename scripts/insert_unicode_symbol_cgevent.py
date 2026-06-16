#!/usr/bin/env python3
"""
Insert Unicode text as simulated keystrokes via CGEventKeyboardSetUnicodeString.

Replaces the old clipboard-round-trip approach:
  - No side effects — the clipboard is never touched.
  - No timing / sleep — no race with clipboard restore.
  - ctypes-only (stdlib) — works under `python3 -S`.
"""
import argparse
import ctypes
import sys


# ── CoreGraphics bridge ────────────────────────────────────────────

_CG = ctypes.CDLL(
    "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
)

_CG.CGEventCreateKeyboardEvent.argtypes = [
    ctypes.c_void_p,   # CGEventSourceRef (NULL → default)
    ctypes.c_uint16,   # CGKeyCode (ignored when unicode string is set)
    ctypes.c_bool,     # keyDown
]
_CG.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p  # CGEventRef

_CG.CGEventKeyboardSetUnicodeString.argtypes = [
    ctypes.c_void_p,   # CGEventRef
    ctypes.c_uint64,   # UniCharCount (number of UTF-16 code units)
    ctypes.c_void_p,   # const UniChar *
]

_CG.CGEventPost.argtypes = [
    ctypes.c_uint32,   # CGEventTapLocation
    ctypes.c_void_p,   # CGEventRef
]

kCGHIDEventTap = 0


def insert(text: str) -> None:
    """Post *text* as HID keyboard events — no clipboard involved."""
    if not text:
        return

    utf16 = text.encode("utf-16-le")
    char_count = len(utf16) // 2
    buf = (ctypes.c_ubyte * len(utf16)).from_buffer_copy(utf16)

    down = _CG.CGEventCreateKeyboardEvent(None, 0, True)
    _CG.CGEventKeyboardSetUnicodeString(down, char_count, buf)
    _CG.CGEventPost(kCGHIDEventTap, down)

    up = _CG.CGEventCreateKeyboardEvent(None, 0, False)
    _CG.CGEventPost(kCGHIDEventTap, up)


# ── Text aliases ───────────────────────────────────────────────────

TEXT_ALIASES = {
    # "__": "　",  # full-width space
}


# ── CLI ────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=False)

    # Backward-compat no-ops (old clipboard flags now ignored)
    p.add_argument("--restore-clipboard", action="store_true")
    p.add_argument("--restore-delay", type=float, default=0.15)
    p.add_argument("--restore-max-bytes", type=int, default=50000)
    p.add_argument("--use-html", action="store_true")

    p.add_argument("--codepoint")
    p.add_argument("text", nargs="?")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.codepoint:
        value = (
            args.codepoint.removeprefix("U+")
            .removeprefix("u+")
            .removeprefix("0x")
        )
        text = chr(int(value, 16))
    elif args.text is not None:
        text = args.text
    else:
        return 2

    text = TEXT_ALIASES.get(text, text)
    insert(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
