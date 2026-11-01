#!/usr/bin/env python3
"""Show the current frontmost app and observed session modifiers."""

import argparse
import importlib
from typing import Any

from keyboard_events import current_modifier_flags, format_modifier_flags
from tooltip import notify


def collect_input_info(layer=None):
    flags = current_modifier_flags()
    AppKit: Any = importlib.import_module("AppKit")
    app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    name = str(app.localizedName() or "Unknown") if app else "Unknown"
    bundle = str(app.bundleIdentifier() or "Unbundled") if app else "Unknown"
    layer_line = f"Layer: {layer.title()}\n" if layer else ""
    if layer == "secondary":
        layer_line += "Layer trigger: modifier output suppressed\n"
    return (
        f"App: {name}\n{bundle}\n"
        f"{layer_line}"
        f"Modifiers: {format_modifier_flags(flags, include_sides=True)}\n"
        f"Session flags: 0x{flags:08X}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", dest="print_only", action="store_true")
    parser.add_argument("--layer", choices=("primary", "secondary"))
    args = parser.parse_args()
    text = collect_input_info(args.layer)
    if args.print_only:
        print(text)
    else:
        notify(text, duration_ms=2500)


if __name__ == "__main__":
    main()
