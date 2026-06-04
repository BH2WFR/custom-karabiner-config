#!/usr/bin/env python3
"""Toggle built-in display on/off via CoreGraphics private API.
Minimal script for Karabiner-Elements keybinding. Apple Silicon only."""

import sys
import os
import ctypes

if sys.platform != "darwin":
    print(f"ERROR: macOS only. Current: {sys.platform}", file=sys.stderr)
    sys.exit(1)

if os.uname().machine != "arm64":
    print(f"ERROR: Apple Silicon only. Current: {os.uname().machine}", file=sys.stderr)
    sys.exit(1)

libc = ctypes.CDLL('/usr/lib/libSystem.dylib')
libc.dlopen.argtypes = [ctypes.c_char_p, ctypes.c_int]
libc.dlopen.restype = ctypes.c_void_p
libc.dlsym.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
libc.dlsym.restype = ctypes.c_void_p

_cgs_handle = libc.dlopen(
    b'/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics', 1)
if not _cgs_handle:
    print("ERROR: Cannot load CoreGraphics framework.", file=sys.stderr)
    sys.exit(1)


def _lookup(name: str):
    name_bytes = name.encode()
    ptr = libc.dlsym(_cgs_handle, name_bytes)
    if not ptr:
        ptr = libc.dlsym(ctypes.c_void_p(-2), name_bytes)
    if not ptr:
        print(f"ERROR: symbol `{name}` not found.", file=sys.stderr)
        sys.exit(1)
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


def _get_all_displays():
    ids = (ctypes.c_uint32 * MAX_DISPLAYS)()
    count = ctypes.c_uint32(0)
    CGSGetDisplayList(MAX_DISPLAYS, ids, ctypes.byref(count))
    return [ids[i] for i in range(count.value)]


def _get_active_displays():
    ids = (ctypes.c_uint32 * MAX_DISPLAYS)()
    count = ctypes.c_uint32(0)
    CGGetActiveDisplayList(MAX_DISPLAYS, ids, ctypes.byref(count))
    return {ids[i] for i in range(count.value)}


def _find_builtin():
    for did in _get_all_displays():
        if CGDisplayIsBuiltin(did):
            return did
    return 1


def main():
    builtin_id = _find_builtin()

    active_set = _get_active_displays()
    all_displays = _get_all_displays()
    builtin_active = builtin_id in active_set

    external_active_count = sum(
        1 for did in all_displays if did != builtin_id and did in active_set)

    if external_active_count == 0 and builtin_active:
        print("Built-in is the only active display. Refusing to disable.",
              file=sys.stderr)
        sys.exit(1)

    target = not builtin_active

    config = ctypes.c_void_p(0)
    if CGBeginDisplayConfiguration(ctypes.byref(config)) != 0:
        print("CGBeginDisplayConfiguration failed.", file=sys.stderr)
        sys.exit(1)

    if CGSConfigureDisplayEnabled(config, builtin_id, target) != 0:
        print("CGSConfigureDisplayEnabled failed.", file=sys.stderr)
        sys.exit(1)

    if CGSCompleteDisplayConfiguration(config) != 0:
        print("CGSCompleteDisplayConfiguration failed.", file=sys.stderr)
        sys.exit(1)

    action = "enabled" if target else "disabled"
    print(f"Built-in display {action}.")


if __name__ == "__main__":
    main()
