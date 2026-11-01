#!/usr/bin/env python3
"""Send an ordered sequence of key chords and Unicode text without the clipboard."""

import argparse
import fcntl
import time
from typing import NamedTuple

import keyboard_events as keys

MODIFIERS = {
    "command": keys.COMMAND_FLAG,
    "control": keys.CONTROL_FLAG,
    "option": keys.OPTION_FLAG,
    "shift": keys.SHIFT_FLAG,
    "fn": keys.FN_FLAG,
}


class Step(NamedTuple):
    code: int
    flags: int = 0
    text: str | None = None


def parse_key(value):
    parts = value.lower().split("+")
    if parts[-1] not in keys.KEY_CODES or any(m not in MODIFIERS for m in parts[:-1]):
        raise argparse.ArgumentTypeError(f"Unknown key chord: {value}")
    flags = 0
    for modifier in parts[:-1]:
        flags |= MODIFIERS[modifier]
    return Step(keys.KEY_CODES[parts[-1]], flags)


def parse_text(value):
    try:
        value.encode("utf-16-le")
    except UnicodeEncodeError:
        raise argparse.ArgumentTypeError("Text contains an unpaired surrogate.") from None
    if not value:
        raise argparse.ArgumentTypeError("Text cannot be empty.")
    return Step(0, text=value)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", dest="steps", action="append", type=parse_key,
                        metavar="CHORD", help="e.g. command+control+f13; repeat in execution order")
    parser.add_argument("--text", dest="steps", action="append", type=parse_text,
                        metavar="TEXT", help="Unicode text, in order with --key")
    parser.add_argument("--inherit-modifiers", action="store_true",
                        help="include mapped modifiers held when this command starts")
    parser.add_argument("--exclude-modifiers", nargs="+", choices=MODIFIERS, default=[])
    parser.add_argument("--release-key", choices=keys.KEY_CODES,
                        help="release the triggering key before sending the sequence")
    args = parser.parse_args(argv)
    if not args.steps:
        parser.error("at least one --key or --text is required")
    return args


def send_sequence(steps, *, inherited_flags=0, trigger_code=None):
    """Run one macro at a time; the lock stores no user or clipboard data."""
    if not keys.can_post_events():
        raise RuntimeError("Python needs Accessibility permission to send keys.")
    with open(__file__, "rb") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        keys.release_modifiers()
        if trigger_code is not None:
            keys.release_keys(trigger_code)
        time.sleep(keys.CHORD_EVENT_INTERVAL)
        for step in steps:
            flags = (step.flags | inherited_flags) if step.text is None else 0
            keys.post_keystroke(step.code, flags, unicode_text=step.text)


def main(argv=None):
    args = parse_args(argv)
    inherited = keys.current_modifier_flags() & sum(MODIFIERS.values()) if args.inherit_modifiers else 0
    for modifier in args.exclude_modifiers:
        inherited &= ~MODIFIERS[modifier]
    try:
        send_sequence(args.steps, inherited_flags=inherited,
                      trigger_code=keys.KEY_CODES[args.release_key] if args.release_key else None)
    except (RuntimeError, OSError) as exc:
        from tooltip import notify

        notify(str(exc), level="error")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
