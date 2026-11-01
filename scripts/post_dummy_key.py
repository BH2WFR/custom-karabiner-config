#!/usr/bin/env python3
"""Post a harmless keyboard event after a short delay."""

import argparse
import time
from keyboard_events import post_keystroke

F18_KEY_CODE = 79


def _post_key(key_code: int) -> None:
    post_keystroke(key_code)


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
