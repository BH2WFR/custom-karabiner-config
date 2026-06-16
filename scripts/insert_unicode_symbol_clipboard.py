#!/usr/bin/env python3
import argparse
import html
import os
import subprocess
import sys
import time


RESTORE_CLIPBOARD_MAX_BYTES = 50000

TEXT_ALIASES = {
    "__": "\u3000",
}

SNAPSHOT_CLIPBOARD_SCRIPT = r"""
import base64
import json
import sys
from AppKit import NSPasteboard

max_bytes = int(sys.argv[1])
pasteboard = NSPasteboard.generalPasteboard()
items = []
total_size = 0

for item in pasteboard.pasteboardItems() or []:
    item_data = {}
    for value_type in item.types() or []:
        data = item.dataForType_(value_type)
        if data is None:
            continue

        raw_data = bytes(data)
        total_size += len(raw_data)
        if total_size > max_bytes:
            print(json.dumps({"ok": False, "reason": "too_large"}))
            sys.exit(0)

        item_data[str(value_type)] = base64.b64encode(raw_data).decode("ascii")

    if item_data:
        items.append(item_data)

print(json.dumps({"ok": True, "items": items}))
"""

RESTORE_CLIPBOARD_SCRIPT = r"""
import base64
import json
import sys
from AppKit import NSData, NSPasteboard, NSPasteboardItem

payload = json.load(sys.stdin)
pasteboard = NSPasteboard.generalPasteboard()
pasteboard.clearContents()

items = []
for item_data in payload.get("items", []):
    item = NSPasteboardItem.alloc().init()
    for value_type, encoded_data in item_data.items():
        raw_data = base64.b64decode(encoded_data)
        data = NSData.dataWithBytes_length_(raw_data, len(raw_data))
        item.setData_forType_(data, value_type)
    items.append(item)

if items:
    pasteboard.writeObjects_(items)
"""


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


def clipboard_snapshot(max_bytes, env):
    result = subprocess.run(
        [sys.executable, "-c", SNAPSHOT_CLIPBOARD_SCRIPT, str(max_bytes)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None

    try:
        import json

        snapshot = json.loads(result.stdout)
    except Exception:
        return None

    return snapshot if snapshot.get("ok") else None


def restore_clipboard_snapshot(snapshot, env):
    if not snapshot:
        return

    import json

    subprocess.run(
        [sys.executable, "-c", RESTORE_CLIPBOARD_SCRIPT],
        input=json.dumps(snapshot),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )


def make_html(text):
    escaped_text = html.escape(text, quote=False)
    return f'<meta charset="utf-8"><span>{escaped_text}</span>'


def pbcopy_html(text, env):
    html_text = make_html(text)
    subprocess.run(
        [
            "/usr/bin/osascript",
            "-e",
            'use framework "AppKit"',
            "-e",
            "on run argv",
            "-e",
            "set plainText to item 1 of argv",
            "-e",
            "set htmlText to item 2 of argv",
            "-e",
            "set pb to current application's NSPasteboard's generalPasteboard()",
            "-e",
            "pb's clearContents()",
            "-e",
            'pb\'s setString:plainText forType:"public.utf8-plain-text"',
            "-e",
            'pb\'s setString:htmlText forType:"public.html"',
            "-e",
            "end run",
            text,
            html_text,
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


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
    parser.add_argument("--restore-max-bytes", type=int, default=RESTORE_CLIPBOARD_MAX_BYTES)
    parser.add_argument("--use-html", action="store_true")
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
    text = TEXT_ALIASES.get(text, text)

    previous_clipboard = (
        clipboard_snapshot(max(args.restore_max_bytes, 0), env)
        if args.restore_clipboard
        else None
    )
    if args.use_html:
        pbcopy_html(text, env)
    else:
        pbcopy_text(text, env)

    time.sleep(0.15)
    paste()

    if previous_clipboard is not None:
        time.sleep(max(args.restore_delay, 0))
        restore_clipboard_snapshot(previous_clipboard, env)

    return 0


if __name__ == "__main__":
    sys.exit(main())
