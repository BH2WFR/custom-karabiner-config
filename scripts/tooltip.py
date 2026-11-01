#!/usr/bin/env python3
"""Show a native macOS panel that cannot take keyboard or mouse focus."""

import argparse
from functools import lru_cache
import importlib
import math
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

STYLES = {
    "info": ("#303030", 600),
    "warning": ("#805500", 1200),
    "error": ("#9b3036", 1600),
}


@lru_cache(maxsize=1)
def _panel_class():
    AppKit: Any = importlib.import_module("AppKit")

    class KarabinerTooltipPanel(AppKit.NSPanel):
        def canBecomeKeyWindow(self):
            return False

        def canBecomeMainWindow(self):
            return False

    return KarabinerTooltipPanel


def _tooltip_frame(mouse, bounds, width, height):
    margin, gap = 8, 16
    left, bottom = bounds.origin.x + margin, bounds.origin.y + margin
    right = bounds.origin.x + bounds.size.width - margin
    top = bounds.origin.y + bounds.size.height - margin
    width, height = min(width, right - left), min(height, top - bottom)
    # AppKit coordinates start at the bottom left. Prefer below/right, then flip.
    x, y = mouse.x + gap, mouse.y - gap - height
    if x + width > right:
        x = mouse.x - gap - width
    if y < bottom:
        y = mouse.y + gap
    x = max(left, min(x, right - width))
    y = max(bottom, min(y, top - height))
    return ((x, y), (width, height))


def _create_panel(text, level):
    AppKit: Any = importlib.import_module("AppKit")
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    screen = AppKit.NSScreen.mainScreen()
    mouse = AppKit.NSEvent.mouseLocation()
    for candidate in AppKit.NSScreen.screens():
        if AppKit.NSPointInRect(mouse, candidate.frame()):
            screen = candidate
            break
    bounds = screen.visibleFrame()
    font = AppKit.NSFont.systemFontOfSize_(14)
    label = AppKit.NSTextField.wrappingLabelWithString_(text)
    label.setFont_(font)
    label.setTextColor_(AppKit.NSColor.whiteColor())
    label.setSelectable_(False)
    label.setEditable_(False)
    label.setDrawsBackground_(False)
    label.setMaximumNumberOfLines_(0)
    size = label.cell().cellSizeForBounds_(
        ((0, 0), (min(480, bounds.size.width - 64), 10000))
    )
    width, height = math.ceil(size.width), math.ceil(size.height)
    frame = _tooltip_frame(mouse, bounds, width + 32, height + 20)
    label.setFrame_(((16, 10), (frame[1][0] - 32, frame[1][1] - 20)))
    panel = _panel_class().alloc().initWithContentRect_styleMask_backing_defer_(
        frame, AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
        AppKit.NSBackingStoreBuffered, False,
    )
    panel.setReleasedWhenClosed_(False)
    panel.setBecomesKeyOnlyIfNeeded_(True)
    panel.setHidesOnDeactivate_(False)
    panel.setIgnoresMouseEvents_(True)
    panel.setLevel_(AppKit.NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        | AppKit.NSWindowCollectionBehaviorIgnoresCycle
    )
    color = STYLES[level][0].lstrip("#")
    red, green, blue = (int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    panel.setBackgroundColor_(AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(red, green, blue, 1))
    panel.contentView().addSubview_(label)
    return panel


def show_tooltip(text, duration_ms=None, *, level="info"):
    if duration_ms is None:
        duration_ms = STYLES[level][1]
    # Keep the existing stdlib-only/-S callers; only their UI child loads Cocoa.
    if sys.flags.no_site:
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), text,
             "--level", level, "--duration-ms", str(duration_ms)],
            check=True,
        )
        return

    Foundation: Any = importlib.import_module("Foundation")
    panel = _create_panel(text, level)
    try:
        # Never activate NSApp or call makeKeyAndOrderFront, even temporarily.
        panel.orderFrontRegardless()
        deadline = time.monotonic() + duration_ms / 1000
        while time.monotonic() < deadline:
            Foundation.NSRunLoop.currentRunLoop().runUntilDate_(
                Foundation.NSDate.dateWithTimeIntervalSinceNow_(.01)
            )
    finally:
        panel.orderOut_(None)
        panel.close()


def notify(text, duration_ms=None, *, level="info"):
    """A missing GUI must not turn a completed operation into a failure."""
    try:
        show_tooltip(text, duration_ms, level=level)
    except Exception as exc:
        print(f"{text} (tooltip unavailable: {exc})", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text")
    parser.add_argument("--duration-ms", type=int)
    parser.add_argument("--level", choices=STYLES, default="info")
    args = parser.parse_args()
    if args.duration_ms is not None and args.duration_ms <= 0:
        parser.error("--duration-ms must be positive")
    show_tooltip(args.text, args.duration_ms, level=args.level)
