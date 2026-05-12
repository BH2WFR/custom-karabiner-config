#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time


def run(command, *, input_bytes=None, env=None):
    return subprocess.run(
        command,
        input=input_bytes,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def pbpaste_text(env):
    return run(["/usr/bin/pbpaste", "-Prefer", "txt"], env=env).stdout


def pbcopy_text(text, env):
    subprocess.run(
        [
            "/usr/bin/osascript",
            "-e",
            "on run argv",
            "-e",
            "set the clipboard to item 1 of argv",
            "-e",
            "end run",
            text,
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def pbcopy_bytes(value, env):
    run(["/usr/bin/pbcopy"], input_bytes=value, env=env)


def paste():
    subprocess.run(
        [
            "/usr/bin/osascript",
            "-e",
            'tell application "System Events" to key code 9 using {command down}',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--restore-clipboard", action="store_true")
    parser.add_argument("--restore-delay", type=float, default=0.15)
    parser.add_argument("--codepoint")
    parser.add_argument("text", nargs="?")
    return parser.parse_args()


def main():
    args = parse_args()
    env = os.environ.copy()
    env.setdefault("LC_CTYPE", "en_US.UTF-8")
    env.setdefault("LANG", "en_US.UTF-8")

    if args.codepoint:
        value = args.codepoint.removeprefix("U+").removeprefix("u+").removeprefix("0x")
        text = chr(int(value, 16))
    elif args.text is not None:
        text = args.text
    else:
        return 2

    previous_clipboard = pbpaste_text(env) if args.restore_clipboard else None
    pbcopy_text(text, env)

    time.sleep(0.15)
    paste()

    if previous_clipboard is not None:
        time.sleep(max(args.restore_delay, 0))
        pbcopy_bytes(previous_clipboard, env)

    return 0


if __name__ == "__main__":
    sys.exit(main())
