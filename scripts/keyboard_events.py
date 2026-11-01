#!/usr/bin/env python3
"""Post keyboard events through CoreGraphics using only the standard library."""

import ctypes


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
_CG.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_CG.CGEventPost.restype = None
_CG.CGPreflightPostEventAccess.argtypes = []
_CG.CGPreflightPostEventAccess.restype = ctypes.c_bool
_CG.CGEventSourceKeyState.argtypes = [ctypes.c_int, ctypes.c_uint16]
_CG.CGEventSourceKeyState.restype = ctypes.c_bool
_CF.CFRelease.argtypes = [ctypes.c_void_p]
_CF.CFRelease.restype = None

HID_EVENT_TAP = 0

SHIFT_FLAG = 1 << 17
COMMAND_FLAG = 1 << 20

X_KEY_CODE = 7
C_KEY_CODE = 8
V_KEY_CODE = 9
DELETE_KEY_CODE = 51
ESCAPE_KEY_CODE = 53
RIGHT_COMMAND_KEY_CODE = 54
LEFT_COMMAND_KEY_CODE = 55
LEFT_SHIFT_KEY_CODE = 56
LEFT_OPTION_KEY_CODE = 58
LEFT_CONTROL_KEY_CODE = 59
RIGHT_SHIFT_KEY_CODE = 60
RIGHT_OPTION_KEY_CODE = 61
RIGHT_CONTROL_KEY_CODE = 62
LEFT_ARROW_KEY_CODE = 123
RIGHT_ARROW_KEY_CODE = 124
MODIFIER_KEY_CODES = (
    LEFT_SHIFT_KEY_CODE, RIGHT_SHIFT_KEY_CODE,
    LEFT_OPTION_KEY_CODE, RIGHT_OPTION_KEY_CODE,
    LEFT_COMMAND_KEY_CODE, RIGHT_COMMAND_KEY_CODE,
    LEFT_CONTROL_KEY_CODE, RIGHT_CONTROL_KEY_CODE,
)


def can_post_events():
    return _CG.CGPreflightPostEventAccess()


def is_key_down(key_code):
    return _CG.CGEventSourceKeyState(0, key_code)  # Combined session state.


def post_key_event(key_code, key_down, flags=0):
    event = _CG.CGEventCreateKeyboardEvent(None, key_code, key_down)
    if not event:
        raise RuntimeError("Unable to create keyboard event.")

    try:
        _CG.CGEventSetFlags(event, flags)
        _CG.CGEventPost(HID_EVENT_TAP, event)
    finally:
        _CF.CFRelease(event)


def release_keys(*key_codes):
    for key_code in key_codes:
        post_key_event(key_code, False)


def release_modifiers():
    release_keys(*MODIFIER_KEY_CODES)


def post_keystroke(key_code, flags=0):
    post_key_event(key_code, True, flags)
    post_key_event(key_code, False, flags)


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
