#!/usr/bin/env python3
"""Toggle local Caps Lock directly, without switching input sources."""

import argparse
import ctypes as c
import sys

from tooltip import notify


IO = c.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
SYSTEM = c.CDLL("/usr/lib/libSystem.B.dylib")
IO.IOServiceMatching.argtypes = [c.c_char_p]
IO.IOServiceMatching.restype = c.c_void_p
IO.IOServiceGetMatchingService.argtypes = [c.c_uint, c.c_void_p]
IO.IOServiceGetMatchingService.restype = c.c_uint
IO.IOServiceOpen.argtypes = [c.c_uint, c.c_uint, c.c_uint, c.POINTER(c.c_uint)]
IO.IOServiceOpen.restype = c.c_int
IO.IOObjectRelease.argtypes = [c.c_uint]
IO.IOServiceClose.argtypes = [c.c_uint]
IO.IOHIDGetModifierLockState.argtypes = [c.c_uint, c.c_int, c.POINTER(c.c_bool)]
IO.IOHIDGetModifierLockState.restype = c.c_int
IO.IOHIDSetModifierLockState.argtypes = [c.c_uint, c.c_int, c.c_bool]
IO.IOHIDSetModifierLockState.restype = c.c_int
SYSTEM.mach_task_self.restype = c.c_uint

# IOHIDParameter.h and IOHIDShared.h in the macOS SDK.
CAPS_LOCK_STATE = 1
PARAM_CONNECT_TYPE = 1


def check_result(result):
    if result:
        raise RuntimeError(f"IOKit error 0x{result & 0xffffffff:08x}")


class LockState:
    def __enter__(self):
        service = IO.IOServiceGetMatchingService(0, IO.IOServiceMatching(b"IOHIDSystem"))
        if not service:
            raise RuntimeError("IOHIDSystem is unavailable")
        self.connection = c.c_uint()
        try:
            check_result(IO.IOServiceOpen(
                service, SYSTEM.mach_task_self(), PARAM_CONNECT_TYPE,
                c.byref(self.connection),
            ))
        finally:
            IO.IOObjectRelease(service)
        return self

    def __exit__(self, *exc):
        IO.IOServiceClose(self.connection)

    def get(self):
        state = c.c_bool()
        check_result(IO.IOHIDGetModifierLockState(
            self.connection, CAPS_LOCK_STATE, c.byref(state),
        ))
        return state.value

    def set(self, enabled):
        check_result(IO.IOHIDSetModifierLockState(
            self.connection, CAPS_LOCK_STATE, enabled,
        ))
        if self.get() != enabled:
            raise RuntimeError("Caps Lock did not change on this system")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-tooltip", action="store_true")
    args = parser.parse_args()
    try:
        with LockState() as lock:
            enabled = not lock.get()
            lock.set(enabled)
        message = f"Caps Lock: {'ON' if enabled else 'OFF'}"
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        if not args.no_tooltip:
            notify("Caps Lock: unavailable", level="error")
        return 1
    if not args.no_tooltip:
        notify(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
