#!/usr/bin/env python3
"""Capture the source window before opening the pinned inspector in the foreground."""

import argparse
from pathlib import Path
import sys

from launch_external_tool import open_tool
from tooltip import notify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inspector", type=Path)
    args = parser.parse_args()
    try:
        inspector = args.inspector.expanduser().resolve(strict=True)
        # Reuse the inspector's AX and WindowServer lookup without loading its GUI.
        sys.path[:0] = [str(inspector.parent), str(inspector.parents[2])]
        from window_inspector.macos import foreground

        target = foreground()
        window_id, pid = (target.id, target.pid) if target and target.id > 0 else (0, 0)
        open_tool(inspector, "--startup-window", str(window_id), str(pid), "--top")
    except Exception as exc:
        notify(str(exc), level="error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
