#!/opt/miniconda3/bin/python3 -S
"""Post synthetic macOS trackpad pinch-zoom gesture events.

This follows LinearMouse/GestureKit's approach: post NSEventTypeGesture events
with the private CoreGraphics gesture fields used for IOHID zoom gestures.
It is intentionally not a scroll-wheel zoom or Cmd+plus/minus fallback.
"""

import argparse
import ctypes
import ctypes.util
import time


# NSEvent.EventType.gesture.rawValue
CG_EVENT_TYPE_GESTURE = 29
# NSEvent.EventType.magnify.rawValue
CG_EVENT_TYPE_MAGNIFY = 30

# Private CGEventField values used by WebKit tests and LinearMouse GestureKit.
FIELD_GESTURE_HID_TYPE = 110
FIELD_GESTURE_ZOOM_VALUE = 113
FIELD_GESTURE_PHASE = 132

# CGEvent fields used by the magnify-event compatibility path.
FIELD_DELTA_AXIS3 = 13
FIELD_SCROLL_PHASE = 88
FIELD_IS_CONTINUOUS = 90

# IOHIDEventType.zoom
IOHID_EVENT_TYPE_ZOOM = 8

# CGSGesturePhase values.
GESTURE_PHASE_BEGAN = 1
GESTURE_PHASE_CHANGED = 2
GESTURE_PHASE_ENDED = 4
CG_HID_EVENT_TAP = 0
CG_SESSION_EVENT_TAP = 1

CG_SCROLL_EVENT_UNIT_PIXEL = 0


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


_cglib = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))

_cglib.CGEventCreate.argtypes = [ctypes.c_void_p]
_cglib.CGEventCreate.restype = ctypes.c_void_p

_cglib.CGEventCreateScrollWheelEvent2.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_uint32,
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.c_int32,
]
_cglib.CGEventCreateScrollWheelEvent2.restype = ctypes.c_void_p

_cglib.CGEventSetType.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
_cglib.CGEventSetType.restype = None

_cglib.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
_cglib.CGEventSetFlags.restype = None

_cglib.CGEventGetLocation.argtypes = [ctypes.c_void_p]
_cglib.CGEventGetLocation.restype = CGPoint

_cglib.CGEventSetLocation.argtypes = [ctypes.c_void_p, CGPoint]
_cglib.CGEventSetLocation.restype = None

_cglib.CGEventSetIntegerValueField.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int64,
]
_cglib.CGEventSetIntegerValueField.restype = None

_cglib.CGEventSetDoubleValueField.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_double,
]
_cglib.CGEventSetDoubleValueField.restype = None

_cglib.CGEventPost.argtypes = [ctypes.c_int, ctypes.c_void_p]
_cglib.CGEventPost.restype = None

_cglib.CFRelease.argtypes = [ctypes.c_void_p]
_cglib.CFRelease.restype = None


def _tap_locations(tap: str) -> list[int]:
    if tap == "hid":
        return [CG_HID_EVENT_TAP]
    if tap == "both":
        return [CG_SESSION_EVENT_TAP, CG_HID_EVENT_TAP]
    return [CG_SESSION_EVENT_TAP]


def _current_mouse_location() -> CGPoint:
    event = _cglib.CGEventCreate(None)
    if not event:
        return CGPoint(0, 0)
    try:
        return _cglib.CGEventGetLocation(event)
    finally:
        _cglib.CFRelease(event)


def _post_event(event: int, tap: str) -> None:
    for location in _tap_locations(tap):
        _cglib.CGEventPost(location, event)


def _post_gesture_zoom_event(
    phase: int,
    magnification: float,
    location: CGPoint,
    tap: str,
) -> bool:
    event = _cglib.CGEventCreate(None)
    if not event:
        return False

    try:
        _cglib.CGEventSetType(event, CG_EVENT_TYPE_GESTURE)
        _cglib.CGEventSetFlags(event, 0)
        _cglib.CGEventSetLocation(event, location)
        _cglib.CGEventSetIntegerValueField(event, FIELD_GESTURE_HID_TYPE, IOHID_EVENT_TYPE_ZOOM)
        _cglib.CGEventSetIntegerValueField(event, FIELD_GESTURE_PHASE, phase)
        _cglib.CGEventSetDoubleValueField(event, FIELD_GESTURE_ZOOM_VALUE, magnification)
        _post_event(event, tap)
        return True
    finally:
        _cglib.CFRelease(event)


def _post_magnify_event(
    phase: int,
    magnification: float,
    location: CGPoint,
    tap: str,
) -> bool:
    event = _cglib.CGEventCreateScrollWheelEvent2(
        None,
        CG_SCROLL_EVENT_UNIT_PIXEL,
        3,
        0,
        0,
        0,
    )
    if not event:
        return False

    try:
        _cglib.CGEventSetType(event, CG_EVENT_TYPE_MAGNIFY)
        _cglib.CGEventSetFlags(event, 0)
        _cglib.CGEventSetLocation(event, location)
        _cglib.CGEventSetDoubleValueField(event, FIELD_DELTA_AXIS3, magnification)
        _cglib.CGEventSetDoubleValueField(event, FIELD_GESTURE_ZOOM_VALUE, magnification)
        _cglib.CGEventSetIntegerValueField(event, FIELD_SCROLL_PHASE, phase)
        _cglib.CGEventSetIntegerValueField(event, FIELD_IS_CONTINUOUS, 1)
        _post_event(event, tap)
        return True
    finally:
        _cglib.CFRelease(event)


def _post_zoom_event(
    phase: int,
    magnification: float,
    location: CGPoint,
    style: str,
    tap: str,
) -> bool:
    ok = True
    if style in ("gesture", "both"):
        ok = _post_gesture_zoom_event(phase, magnification, location, tap) and ok
    if style in ("magnify", "both"):
        ok = _post_magnify_event(phase, magnification, location, tap) and ok
    return ok


def simulate_pinch_zoom(
    magnification: float,
    steps: int,
    interval: float,
    style: str,
    tap: str,
) -> bool:
    """Post a short began/changed/ended pinch gesture at the cursor position."""
    if steps < 1:
        steps = 1

    location = _current_mouse_location()
    if not _post_zoom_event(GESTURE_PHASE_BEGAN, 0.0, location, style, tap):
        return False

    per_step = magnification / steps
    for _ in range(steps):
        if interval > 0:
            time.sleep(interval)
        if not _post_zoom_event(GESTURE_PHASE_CHANGED, per_step, location, style, tap):
            return False

    if interval > 0:
        time.sleep(interval)
    return _post_zoom_event(GESTURE_PHASE_ENDED, 0.0, location, style, tap)


def simulate_scroll(direction: str, amount: int, tap: str) -> bool:
    """Post a plain vertical scroll wheel event for delivery testing."""
    wheel1 = abs(amount) if direction == "up" else -abs(amount)
    event = _cglib.CGEventCreateScrollWheelEvent2(
        None,
        CG_SCROLL_EVENT_UNIT_PIXEL,
        1,
        wheel1,
        0,
        0,
    )
    if not event:
        return False

    try:
        _cglib.CGEventSetLocation(event, _current_mouse_location())
        _cglib.CGEventSetIntegerValueField(event, FIELD_IS_CONTINUOUS, 1)
        _cglib.CGEventSetIntegerValueField(event, FIELD_SCROLL_PHASE, GESTURE_PHASE_CHANGED)
        _post_event(event, tap)
        return True
    finally:
        _cglib.CFRelease(event)


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate trackpad zoom or test scroll delivery")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--zoom-in", action="store_true", help="Pinch open / zoom in")
    group.add_argument("--zoom-out", action="store_true", help="Pinch close / zoom out")
    group.add_argument("--scroll", choices=["up", "down"], help="Post a plain scroll event for testing")
    parser.add_argument(
        "--amount",
        type=float,
        default=0.8,
        help="Total magnification delta to send (default: 0.8)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=4,
        help="Number of changed events in the gesture (default: 4)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.01,
        help="Delay between gesture events in seconds (default: 0.01)",
    )
    parser.add_argument(
        "--style",
        choices=["gesture", "magnify", "both"],
        default="both",
        help="Synthetic event style to post (default: both)",
    )
    parser.add_argument(
        "--tap",
        choices=["session", "hid", "both"],
        default="session",
        help="CGEvent tap location to post to (default: session)",
    )
    parser.add_argument(
        "--scroll-amount",
        type=int,
        default=400,
        help="Scroll delta for --scroll testing (default: 400)",
    )
    args = parser.parse_args()

    if args.scroll:
        return 0 if simulate_scroll(args.scroll, args.scroll_amount, args.tap) else 1

    delta = args.amount if args.zoom_in else -args.amount
    ok = simulate_pinch_zoom(delta, args.steps, args.interval, args.style, args.tap)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
