#!/usr/bin/env python3
"""Toggle built-in display on/off via CoreGraphics private API.
Minimal script for Karabiner-Elements keybinding. Apple Silicon only."""

import sys
import os
import ctypes
from typing import NoReturn

from tooltip import notify


def fail(message, *, level="error") -> NoReturn:
    print(message, file=sys.stderr)
    notify(message, level=level)
    raise SystemExit(1)


if sys.platform != "darwin":
    fail("Display toggle is only available on macOS.")

if os.uname().machine != "arm64":
    fail("Display toggle requires Apple Silicon.")

libc = ctypes.CDLL('/usr/lib/libSystem.dylib')
libc.dlopen.argtypes = [ctypes.c_char_p, ctypes.c_int]
libc.dlopen.restype = ctypes.c_void_p
libc.dlsym.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
libc.dlsym.restype = ctypes.c_void_p

_cgs_handle = libc.dlopen(
    b'/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics', 1)
if not _cgs_handle:
    fail("Cannot load CoreGraphics framework.")

_ds_handle = libc.dlopen(
    b'/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices', 1)
if not _ds_handle:
    fail("Cannot load DisplayServices framework.")


def _lookup(name: str):
    name_bytes = name.encode()
    ptr = libc.dlsym(_cgs_handle, name_bytes)
    if not ptr:
        ptr = libc.dlsym(ctypes.c_void_p(-2), name_bytes)
    if not ptr:
        fail(f"Display API unavailable: {name}.")
    return ptr


MAX_DISPLAYS = 64

CGSGetDisplayList = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
)(_lookup('CGSGetDisplayList'))

CGGetActiveDisplayList = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
)(_lookup('CGGetActiveDisplayList'))

CGDisplayIsBuiltin = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_uint32)(
    _lookup('CGDisplayIsBuiltin'))

CGBeginDisplayConfiguration = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p),
)(_lookup('CGBeginDisplayConfiguration'))

CGSConfigureDisplayEnabled = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_bool,
)(_lookup('CGSConfigureDisplayEnabled'))

CGSCompleteDisplayConfiguration = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p,
)(_lookup('CGSCompleteDisplayConfiguration'))

DisplayServicesGetBrightness = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_float),
)(_lookup('DisplayServicesGetBrightness'))

DisplayServicesSetBrightness = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.c_uint32, ctypes.c_float,
)(_lookup('DisplayServicesSetBrightness'))


def _get_all_displays():
    ids = (ctypes.c_uint32 * MAX_DISPLAYS)()
    count = ctypes.c_uint32(0)
    if CGSGetDisplayList(MAX_DISPLAYS, ids, ctypes.byref(count)) != 0:
        fail("Cannot read the display list.")
    return [ids[i] for i in range(count.value)]


def _get_active_displays():
    ids = (ctypes.c_uint32 * MAX_DISPLAYS)()
    count = ctypes.c_uint32(0)
    if CGGetActiveDisplayList(MAX_DISPLAYS, ids, ctypes.byref(count)) != 0:
        fail("Cannot read the active display list.")
    return {ids[i] for i in range(count.value)}


def _find_builtin():
    for did in _get_all_displays(): 
        if CGDisplayIsBuiltin(did):
            return did
    fail("No built-in display found.", level="warning")


def _get_brightness(display_id):
    """Return brightness as 0.0-1.0 float, or None on failure."""
    val = ctypes.c_float(0)
    if DisplayServicesGetBrightness(display_id, ctypes.byref(val)) == 0:
        return val.value
    return None


def _set_brightness(display_id, level):
    """Set brightness to level (0.0-1.0)."""
    return DisplayServicesSetBrightness(display_id, ctypes.c_float(level)) == 0


def _adjust_low_brightness(display_id):
    cur = _get_brightness(display_id)
    if cur is not None and cur < 0.2:
        _set_brightness(display_id, 0.35)


def main():
    builtin_id = _find_builtin()

    active_set = _get_active_displays()
    all_displays = _get_all_displays()
    builtin_active = builtin_id in active_set

    external_active_count = sum(
        1 for did in all_displays if did != builtin_id and did in active_set)

    if external_active_count == 0 and builtin_active:
        _adjust_low_brightness(builtin_id)
        fail("Connect an external display before disabling the built-in display.", level="warning")

    target = not builtin_active

    config = ctypes.c_void_p(0)
    if CGBeginDisplayConfiguration(ctypes.byref(config)) != 0:
        fail("Cannot begin display configuration.")

    if CGSConfigureDisplayEnabled(config, builtin_id, target) != 0:
        fail("Cannot change the built-in display state.")

    if CGSCompleteDisplayConfiguration(config) != 0:
        fail("Cannot apply the display configuration.")

    action = "enabled" if target else "disabled"
    print(f"Built-in display {action}.")

    if target:
        _adjust_low_brightness(builtin_id)
    notify(f"Built-in display {action}.")


if __name__ == "__main__":
    main()
