#!/usr/bin/env python3
"""Post keyboard events through CoreGraphics using only the standard library."""

import ctypes
import time


_CG = ctypes.CDLL(
    "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
)
_CF = ctypes.CDLL(
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
)

_CG.CGEventCreateKeyboardEvent.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint16,
    ctypes.c_bool,
]
_CG.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
_CG.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
_CG.CGEventSetFlags.restype = None
_CG.CGEventSetType.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
_CG.CGEventSetType.restype = None
_CG.CGEventKeyboardSetUnicodeString.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]
_CG.CGEventKeyboardSetUnicodeString.restype = None
_CG.CGEventSourceFlagsState.argtypes = [ctypes.c_int]
_CG.CGEventSourceFlagsState.restype = ctypes.c_uint64
_CG.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_CG.CGEventPost.restype = None
_CG.CGPreflightPostEventAccess.argtypes = []
_CG.CGPreflightPostEventAccess.restype = ctypes.c_bool
_CG.CGRequestPostEventAccess.argtypes = []
_CG.CGRequestPostEventAccess.restype = ctypes.c_bool
_CG.CGEventSourceKeyState.argtypes = [ctypes.c_int, ctypes.c_uint16]
_CG.CGEventSourceKeyState.restype = ctypes.c_bool
_CF.CFRelease.argtypes = [ctypes.c_void_p]
_CF.CFRelease.restype = None

HID_EVENT_TAP = 0
SESSION_EVENT_TAP = 1
FLAGS_CHANGED_EVENT = 12
CHORD_EVENT_INTERVAL = 0.01

CAPS_LOCK_FLAG = 1 << 16
SHIFT_FLAG = 1 << 17
CONTROL_FLAG = 1 << 18
OPTION_FLAG = 1 << 19
COMMAND_FLAG = 1 << 20
FN_FLAG = 1 << 23

X_KEY_CODE = 7
C_KEY_CODE = 8
V_KEY_CODE = 9
DELETE_KEY_CODE = 51
ESCAPE_KEY_CODE = 53
RIGHT_COMMAND_KEY_CODE = 54
LEFT_COMMAND_KEY_CODE = 55
LEFT_SHIFT_KEY_CODE = 56
CAPS_LOCK_KEY_CODE = 57
LEFT_OPTION_KEY_CODE = 58
LEFT_CONTROL_KEY_CODE = 59
RIGHT_SHIFT_KEY_CODE = 60
RIGHT_OPTION_KEY_CODE = 61
RIGHT_CONTROL_KEY_CODE = 62
FN_KEY_CODE = 63
ONE_KEY_CODE = 18
SIX_KEY_CODE = 22
LEFT_ARROW_KEY_CODE = 123
RIGHT_ARROW_KEY_CODE = 124
MODIFIER_KEY_CODES = (
    LEFT_SHIFT_KEY_CODE, RIGHT_SHIFT_KEY_CODE,
    LEFT_OPTION_KEY_CODE, RIGHT_OPTION_KEY_CODE,
    LEFT_COMMAND_KEY_CODE, RIGHT_COMMAND_KEY_CODE,
    LEFT_CONTROL_KEY_CODE, RIGHT_CONTROL_KEY_CODE,
)

# Side-specific masks from Apple's IOLLEvent.h; fallback uses these to decode
# flags-changed events. Each entry is (key code, generic flag, side flag).
MODIFIER_KEYS = {
    "LCtrl": (LEFT_CONTROL_KEY_CODE, CONTROL_FLAG, 0x0001),
    "RCtrl": (RIGHT_CONTROL_KEY_CODE, CONTROL_FLAG, 0x2000),
    "LOpt": (LEFT_OPTION_KEY_CODE, OPTION_FLAG, 0x0020),
    "ROpt": (RIGHT_OPTION_KEY_CODE, OPTION_FLAG, 0x0040),
    "LCmd": (LEFT_COMMAND_KEY_CODE, COMMAND_FLAG, 0x0008),
    "RCmd": (RIGHT_COMMAND_KEY_CODE, COMMAND_FLAG, 0x0010),
    "LShift": (LEFT_SHIFT_KEY_CODE, SHIFT_FLAG, 0x0002),
    "RShift": (RIGHT_SHIFT_KEY_CODE, SHIFT_FLAG, 0x0004),
    "Fn": (FN_KEY_CODE, FN_FLAG, 0),
}

# ANSI virtual keycodes from HIToolbox/Events.h, not character codes.
US_KEY_CODES = {
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
KEY_CODES = {
    **US_KEY_CODES,
    "non_us_backslash": 10, "return_or_enter": 36, "quote": 39,
    "semicolon": 41, "backslash": 42, "comma": 43, "period": 47, "tab": 48,
    "spacebar": 49, "delete_or_backspace": DELETE_KEY_CODE,
    "escape": ESCAPE_KEY_CODE,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "f13": 105, "f14": 107, "f15": 113, "f18": 79, "f19": 80,
    "insert": 114, "home": 115, "page_up": 116,
    "delete_forward": 117, "end": 119, "page_down": 121,
    "application": 110,
    "left_arrow": LEFT_ARROW_KEY_CODE, "right_arrow": RIGHT_ARROW_KEY_CODE,
    "down_arrow": 125, "up_arrow": 126,
}


def current_modifier_flags():
    """Read the combined session flags, not the original physical key state."""
    return _CG.CGEventSourceFlagsState(0)


def format_modifier_flags(flags, *, include_sides=False):
    names = [("Ctrl", CONTROL_FLAG), ("Opt", OPTION_FLAG),
             ("Cmd", COMMAND_FLAG), ("Shift", SHIFT_FLAG),
             ("Fn", FN_FLAG), ("CapsLock", CAPS_LOCK_FLAG)]
    result = []
    for name, mask in names:
        if not flags & mask:
            continue
        sides = [label for label, (_, generic, side) in MODIFIER_KEYS.items()
                 if generic == mask and side and flags & side] if include_sides else []
        if sides:
            result.extend(sides)
        elif include_sides and name not in ("Fn", "CapsLock"):
            result.append(f"{name} (side unavailable)")
        else:
            result.append(name)
    return " + ".join(result) or "None"


def can_post_events():
    return _CG.CGPreflightPostEventAccess()


def request_post_events():
    """Request system authorization only when event-posting access is missing."""
    return can_post_events() or _CG.CGRequestPostEventAccess()


def is_key_down(key_code):
    return _CG.CGEventSourceKeyState(0, key_code)  # Combined session state.


def post_key_event(key_code, key_down, flags: int | None = 0, *, flags_changed=False,
                   event_tap=SESSION_EVENT_TAP, unicode_text=None):
    """Post Session output by default; flags=None preserves native event flags."""
    event = _CG.CGEventCreateKeyboardEvent(None, key_code, key_down)
    if not event:
        raise RuntimeError("Unable to create keyboard event.")

    try:
        if flags_changed:
            _CG.CGEventSetType(event, FLAGS_CHANGED_EVENT)
        if flags is not None:
            _CG.CGEventSetFlags(event, flags)
        if unicode_text is not None:
            encoded = unicode_text.encode("utf-16-le")
            buffer = (ctypes.c_ubyte * len(encoded)).from_buffer_copy(encoded)
            _CG.CGEventKeyboardSetUnicodeString(event, len(encoded) // 2, buffer)
        _CG.CGEventPost(event_tap, event)
    finally:
        _CF.CFRelease(event)


def tap_caps_lock():
    """Send a short native Caps Lock press, including its generated lock flags."""
    post_key_event(CAPS_LOCK_KEY_CODE, True, flags=None)
    try:
        time.sleep(.2)
    finally:
        post_key_event(CAPS_LOCK_KEY_CODE, False, flags=None)
        time.sleep(CHORD_EVENT_INTERVAL)


def release_keys(*key_codes):
    for key_code in key_codes:
        if key_code in MODIFIER_KEY_CODES or key_code == FN_KEY_CODE:
            post_key_event(key_code, False, flags_changed=True)
        else:
            post_key_event(key_code, False)


def release_modifiers():
    release_keys(*MODIFIER_KEY_CODES)


def post_keystroke(key_code, flags=0, *, interval=CHORD_EVENT_INTERVAL,
                   unicode_text=None, cancel_event=None):
    """Send a paced chord, optionally attaching Unicode to the main key pair."""
    def check_cancelled():
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Keyboard input cancelled.")

    def pause():
        if cancel_event is None:
            time.sleep(interval)
        elif cancel_event.wait(interval):
            check_cancelled()

    def send(code, down, active_flags, *, modifier=False):
        post_key_event(code, down, active_flags, flags_changed=modifier,
                       unicode_text=None if modifier else unicode_text)

    modifiers = []
    for left, right in (("LCtrl", "RCtrl"), ("LOpt", "ROpt"),
                        ("LCmd", "RCmd"), ("LShift", "RShift")):
        pair = (MODIFIER_KEYS[left], MODIFIER_KEYS[right])
        if flags & pair[0][1]:
            modifiers.extend([item for item in pair if flags & item[2]] or [pair[0]])
    if flags & FN_FLAG:
        modifiers.append(MODIFIER_KEYS["Fn"])
    active_flags = flags
    for _, generic, side in modifiers:
        active_flags &= ~(generic | side)
    pressed = []
    try:
        for code, generic, side in modifiers:
            check_cancelled()
            active_flags |= generic | side
            send(code, True, active_flags, modifier=True)
            pressed.append((code, generic, side))
            pause()
        check_cancelled()
        try:
            send(key_code, True, active_flags)
            pause()
        finally:
            send(key_code, False, active_flags)
        pause()
    finally:
        while pressed:
            code, generic, side = pressed.pop()
            active_flags &= ~side
            if not any(other_generic == generic for _, other_generic, _ in pressed):
                active_flags &= ~generic
            send(code, False, active_flags, modifier=True)
            # Cleanup must finish even after cancellation; retain normal pacing otherwise.
            if cancel_event is None:
                time.sleep(interval)
            else:
                cancel_event.wait(interval)


def main():
    import argparse
    from tooltip import notify
    from toggle_caps_lock import LockState

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-modifiers", action="store_true", required=True)
    parser.parse_args()
    try:
        if not can_post_events():
            raise RuntimeError("Python needs Accessibility permission to release modifiers.")
        release_modifiers()
        with LockState() as lock:
            lock.set(False)
    except RuntimeError as exc:
        notify(str(exc), level="error")
        return 1
    notify("Modifiers released. \nCaps Lock: OFF.")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
