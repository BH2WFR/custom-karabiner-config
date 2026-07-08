#!/usr/bin/env python3
"""Post a harmless keyboard event after a short delay."""

import argparse
import importlib
import time
from typing import Any

CG: Any = importlib.import_module("Quartz.CoreGraphics")

F18_KEY_CODE = 79


def _post_key(key_code: int) -> None:
    down = CG.CGEventCreateKeyboardEvent(None, key_code, True)
    up = CG.CGEventCreateKeyboardEvent(None, key_code, False)
    CG.CGEventPost(CG.kCGHIDEventTap, down)
    CG.CGEventPost(CG.kCGHIDEventTap, up)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-code", type=int, default=F18_KEY_CODE)
    parser.add_argument("--delay-ms", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    time.sleep(max(args.delay_ms, 0) / 1000)
    _post_key(args.key_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
