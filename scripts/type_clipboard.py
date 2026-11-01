#!/usr/bin/env python3
"""Type clipboard text using US-layout keys and experimental Unicode events."""

import argparse
import fcntl
import importlib
import sys
import threading
import time
import unicodedata
from typing import Any

import keyboard_events as keys
from tooltip import notify

AppKit: Any = importlib.import_module("AppKit")
TEXT_TYPE = "public.utf8-plain-text"
DEFAULT_INTERVAL = 0.008

US_KEYS = keys.US_KEY_CODES
SHIFTED_KEYS = dict(zip('~!@#$%^&*()_+{}|:"<>?', "`1234567890-=[]\\;',./"))


class _EscapeMonitor:
    """Cancel typing and swallow the cancelling Escape press through key-up."""

    def __init__(self):
        self.cancelled = threading.Event()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._escape_released = threading.Event()
        self._escape_released.set()
        self._loop = None
        self.failure = None

    def _callback(self, proxy, event_type, event, context):
        q = self._quartz
        if event_type in (q.kCGEventTapDisabledByTimeout, q.kCGEventTapDisabledByUserInput):
            self.failure = "Typing stopped: Escape monitoring was disabled."
            self.cancelled.set()
            self._escape_released.set()
        elif q.CGEventGetIntegerValueField(event, q.kCGKeyboardEventKeycode) == keys.ESCAPE_KEY_CODE:
            if event_type == q.kCGEventKeyDown:
                self._escape_released.clear()
                self.cancelled.set()
                return None
            if event_type == q.kCGEventKeyUp and not self._escape_released.is_set():
                self._escape_released.set()
                return None
        return event

    def _run(self):
        q = self._quartz
        added = False
        try:
            self._loop = q.CFRunLoopGetCurrent()
            q.CFRunLoopAddSource(self._loop, self._source, q.kCFRunLoopCommonModes)
            added = True
            self._ready.set()
            while not self._stop.is_set():
                q.CFRunLoopRunInMode(q.kCFRunLoopDefaultMode, 0.1, False)
        except Exception as exc:
            self.failure = f"Typing stopped: Escape monitor failed: {exc}"
            self.cancelled.set()
        finally:
            self._ready.set()
            self._escape_released.set()
            if added:
                q.CFRunLoopRemoveSource(self._loop, self._source, q.kCFRunLoopCommonModes)

    def __enter__(self):
        self._quartz = q = importlib.import_module("Quartz")
        self._tap = q.CGEventTapCreate(
            q.kCGSessionEventTap, q.kCGHeadInsertEventTap, q.kCGEventTapOptionDefault,
            (1 << q.kCGEventKeyDown) | (1 << q.kCGEventKeyUp), self._callback, None,
        )
        if self._tap is None:
            raise RuntimeError("Cannot intercept Escape. Check Python Accessibility and Input Monitoring permissions.")
        self._source = q.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        if self._source is None:
            q.CFMachPortInvalidate(self._tap)
            raise RuntimeError("Cannot start Escape monitoring.")
        self._thread = threading.Thread(target=self._run, name="typing-escape", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self.failure:
            self.__exit__()
            raise RuntimeError(self.failure)
        if keys.is_key_down(keys.ESCAPE_KEY_CODE):
            self.cancelled.set()
        return self

    def __exit__(self, *_):
        # Keep swallowing repeats and key-up after cancellation, until Esc is released.
        self._escape_released.wait()
        self._stop.set()
        if self._loop is not None:
            self._quartz.CFRunLoopStop(self._loop)
        self._thread.join()
        self._quartz.CFMachPortInvalidate(self._tap)


def plan_keystrokes(text, *, ascii_only=False):
    """Validate everything before any event is posted; CRLF is one Return."""
    strokes = []
    for index, char in enumerate(text.replace("\r\n", "\n").replace("\r", "\n")):
        if ord(char) > 127 and not ascii_only and unicodedata.category(char) not in ("Cc", "Cs"):
            strokes.append((0, False, char))
            continue
        if "A" <= char <= "Z":
            base, shifted = char.lower(), True
        elif char in SHIFTED_KEYS:
            base, shifted = SHIFTED_KEYS[char], True
        else:
            base, shifted = char, False
        if base not in US_KEYS:
            raise ValueError(
                f"Unsupported character U+{ord(char):04X} at position {index + 1}; "
                + ("ASCII-only mode is enabled." if ascii_only and ord(char) > 127
                   else "Control characters and unpaired surrogates are not supported.")
            )
        strokes.append((US_KEYS[base], shifted, None))
    return strokes


def type_text(text, interval=DEFAULT_INTERVAL, *, ascii_only=False):
    if not 0.001 <= interval <= 1:
        raise ValueError("Event interval must be between 1 and 1000 ms.")
    strokes = plan_keystrokes(text, ascii_only=ascii_only)
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
        with _EscapeMonitor() as monitor:
            keys.release_modifiers()
            keys.release_keys(US_KEYS["z"])
            monitor.cancelled.wait(0.05)
            try:
                for code, needs_shift, unicode_text in strokes:
                    if (workspace.frontmostApplication().processIdentifier() != target_pid
                            or keys.is_key_down(keys.ESCAPE_KEY_CODE)):
                        raise RuntimeError("Typing stopped: focus changed or Escape was pressed.")
                    keys.post_keystroke(code, keys.SHIFT_FLAG if needs_shift else 0,
                                        interval=interval, unicode_text=unicode_text,
                                        cancel_event=monitor.cancelled)
            except InterruptedError:
                raise RuntimeError(monitor.failure or "Typing stopped: Escape was pressed.") from None
            finally:
                # Keep the sender alive briefly after the last release, even in fast mode.
                time.sleep(keys.CHORD_EVENT_INTERVAL)


def type_from_pasteboard(pasteboard, interval=DEFAULT_INTERVAL, *, ascii_only=False):
    text = pasteboard.stringForType_(TEXT_TYPE)
    try:
        type_text(str(text) if text is not None else "", interval, ascii_only=ascii_only)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        notify(str(exc), level="warning" if isinstance(exc, ValueError) else "error")
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasteboard-name", help="default: general clipboard")
    parser.add_argument("--interval-ms", type=float, default=DEFAULT_INTERVAL * 1000,
                        help="delay after each key event, not each character (default: %(default)s ms)")
    parser.add_argument("--ascii-only", action="store_true",
                        help="reject non-ASCII text before typing (for incompatible remote consoles)")
    args = parser.parse_args()
    if not 1 <= args.interval_ms <= 1000:
        parser.error("--interval-ms must be between 1 and 1000")
    pasteboard = (AppKit.NSPasteboard.pasteboardWithName_(args.pasteboard_name)
                  if args.pasteboard_name else AppKit.NSPasteboard.generalPasteboard())
    return type_from_pasteboard(pasteboard, args.interval_ms / 1000, ascii_only=args.ascii_only)


if __name__ == "__main__":
    sys.exit(main())
