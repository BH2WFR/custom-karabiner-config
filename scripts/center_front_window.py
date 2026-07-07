#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportMissingModuleSource=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Move the focused frontmost window to the center of a display."""

import argparse
import importlib
import sys
from dataclasses import dataclass
from typing import Any

AS: Any = importlib.import_module("ApplicationServices")
AppKit: Any = importlib.import_module("AppKit")
CG: Any = importlib.import_module("Quartz.CoreGraphics")


@dataclass
class Rect:
    origin: Any
    size: Any


def _ax_copy(element: Any, attribute: str) -> Any:
    error, value = AS.AXUIElementCopyAttributeValue(element, attribute, None)
    if error != AS.kAXErrorSuccess:
        raise RuntimeError(f"AXUIElementCopyAttributeValue({attribute}) failed: {error}")
    return value


def _ax_value(value: Any, value_type: int) -> Any:
    ok, result = AS.AXValueGetValue(value, value_type, None)
    if not ok:
        raise RuntimeError("AXValueGetValue failed.")
    return result


def _focused_window() -> Any:
    app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        raise RuntimeError("No frontmost application.")

    app_ref = AS.AXUIElementCreateApplication(app.processIdentifier())
    return _ax_copy(app_ref, AS.kAXFocusedWindowAttribute)


def _main_display_bounds() -> Any:
    return CG.CGDisplayBounds(CG.CGMainDisplayID())


def _active_display_bounds() -> list[Any]:
    error, displays, _count = CG.CGGetActiveDisplayList(32, None, None)
    if error != CG.kCGErrorSuccess:
        raise RuntimeError(f"CGGetActiveDisplayList failed: {error}")
    return [CG.CGDisplayBounds(display) for display in displays]


def _point_in_rect(x: float, y: float, rect: Any) -> bool:
    return (
        rect.origin.x <= x < rect.origin.x + rect.size.width
        and rect.origin.y <= y < rect.origin.y + rect.size.height
    )


def _intersection_area(a: Any, b: Any) -> float:
    left = max(a.origin.x, b.origin.x)
    top = max(a.origin.y, b.origin.y)
    right = min(a.origin.x + a.size.width, b.origin.x + b.size.width)
    bottom = min(a.origin.y + a.size.height, b.origin.y + b.size.height)
    return max(0.0, right - left) * max(0.0, bottom - top)


def _current_window_display_bounds(position: Any, size: Any) -> Any:
    displays = _active_display_bounds()
    center_x = position.x + size.width / 2
    center_y = position.y + size.height / 2

    for bounds in displays:
        if _point_in_rect(center_x, center_y, bounds):
            return bounds

    window_rect = Rect(origin=position, size=size)
    return max(displays, key=lambda bounds: _intersection_area(window_rect, bounds), default=_main_display_bounds())


def _target_display_bounds(display: str, position: Any, size: Any) -> Any:
    if display == "main":
        return _main_display_bounds()
    return _current_window_display_bounds(position, size)


def _set_window_size(window: Any, width: float, height: float) -> None:
    size = AS.AXValueCreate(AS.kAXValueCGSizeType, (width, height))
    error = AS.AXUIElementSetAttributeValue(window, AS.kAXSizeAttribute, size)
    if error != AS.kAXErrorSuccess:
        raise RuntimeError(f"AXUIElementSetAttributeValue(AXSize) failed: {error}")


def _set_window_position(window: Any, x: float, y: float) -> None:
    position = AS.AXValueCreate(AS.kAXValueCGPointType, (x, y))
    error = AS.AXUIElementSetAttributeValue(window, AS.kAXPositionAttribute, position)
    if error != AS.kAXErrorSuccess:
        raise RuntimeError(f"AXUIElementSetAttributeValue(AXPosition) failed: {error}")


def _window_size(window: Any) -> Any:
    return _ax_value(_ax_copy(window, AS.kAXSizeAttribute), AS.kAXValueCGSizeType)


def _window_position(window: Any) -> Any:
    return _ax_value(_ax_copy(window, AS.kAXPositionAttribute), AS.kAXValueCGPointType)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fit",
        action="store_true",
        help="Shrink the window to fit within the target display before centering.",
    )
    parser.add_argument(
        "--display",
        choices=("current", "main"),
        default="current",
        help="Target display: the window's current display, or the macOS main display.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    window = _focused_window()
    position = _window_position(window)
    size = _window_size(window)
    bounds = _target_display_bounds(args.display, position, size)

    if args.fit:
        width = min(size.width, bounds.size.width)
        height = min(size.height, bounds.size.height)
        if width != size.width or height != size.height:
            _set_window_size(window, width, height)
            size = _window_size(window)
            position = _window_position(window)
            bounds = _target_display_bounds(args.display, position, size)

    x = bounds.origin.x + (bounds.size.width - size.width) / 2
    y = bounds.origin.y + (bounds.size.height - size.height) / 2

    _set_window_position(window, x, y)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
