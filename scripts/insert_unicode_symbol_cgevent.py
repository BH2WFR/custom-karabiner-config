#!/usr/bin/env python3
"""
Insert Unicode text as simulated keystrokes via CGEventKeyboardSetUnicodeString.

Replaces the old clipboard-round-trip approach:
  - No side effects — the clipboard is never touched.
  - Paced key-down/key-up delivery — no clipboard restore race.
  - ctypes-only (stdlib) — works under `python3 -S`.
"""
import argparse
import sys
import keyboard_events


def insert(text: str) -> None:
    """Post Unicode text after the HID fallback, without using the clipboard."""
    if not text:
        return

    keyboard_events.post_keystroke(0, unicode_text=text)


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
