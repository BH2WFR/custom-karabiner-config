#!/usr/bin/env python3
"""Launch an external Python GUI through macOS Launch Services."""

import argparse
from pathlib import Path
import subprocess
import sys

from tooltip import notify


def open_tool(script, *arguments, background=False):
    command = ["/usr/bin/open"]
    if background:
        command.append("-g")
    command.extend([
        "-n", "-a", str(Path(sys.prefix) / "python.app"),
        "--env", f"PYTHONEXECUTABLE={sys.executable}", "--args",
        str(Path(script).expanduser().resolve(strict=True)), *arguments,
    ])
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background", action="store_true")
    parser.add_argument("script", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        open_tool(args.script, *args.arguments, background=args.background)
    except (OSError, subprocess.CalledProcessError) as exc:
        notify(str(exc), level="error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
