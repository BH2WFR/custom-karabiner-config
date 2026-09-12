#!/usr/bin/env python3
import argparse
import importlib
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

AppKit: Any = importlib.import_module("AppKit")
Foundation: Any = importlib.import_module("Foundation")

NSPasteboard = AppKit.NSPasteboard
NSPasteboardItem = AppKit.NSPasteboardItem
NSData = Foundation.NSData


DEFAULT_PASTEBOARD_NAME = "com.bh2wfr.secondary-clipboard"
TEXT_TYPE = "public.utf8-plain-text"
COPY_TIMEOUT_SECONDS = 1.0
PASTE_RESTORE_DELAY_SECONDS = 0.3


def parse_args():
    parser = argparse.ArgumentParser(
        description="Copy, cut, paste, or clear a named secondary pasteboard."
    )
    parser.add_argument("action", choices=("copy", "cut", "paste", "clear"))
    parser.add_argument(
        "--pasteboard-name",
        default=DEFAULT_PASTEBOARD_NAME,
        help=f"named pasteboard to use (default: {DEFAULT_PASTEBOARD_NAME})",
    )
    parser.add_argument(
        "--multi-items",
        action="store_true",
        help="preserve all readable pasteboard items and data types",
    )
    parser.add_argument(
        "--current-line",
        action="store_true",
        help="copy or cut the current line using plain text",
    )
    return parser.parse_args()


def snapshot_pasteboard(pasteboard):
    snapshot = []
    for item in pasteboard.pasteboardItems() or []:
        representations = []
        for pasteboard_type in item.types() or []:
            data = item.dataForType_(pasteboard_type)
            if data is not None:
                representations.append((str(pasteboard_type), bytes(data)))
        if representations:
            snapshot.append(representations)
    return snapshot


def restore_pasteboard(pasteboard, snapshot):
    pasteboard.clearContents()
    items = []
    for representations in snapshot:
        item = NSPasteboardItem.alloc().init()
        for pasteboard_type, payload in representations:
            data = NSData.dataWithBytes_length_(payload, len(payload))
            item.setData_forType_(data, pasteboard_type)
        items.append(item)
    if items:
        pasteboard.writeObjects_(items)


def text_snapshot(text):
    return [[(TEXT_TYPE, text.encode("utf-8"))]]


def post_shortcut(key_code):
    result = subprocess.run(
        [
            "/usr/bin/osascript",
            "-e",
            'tell application "System Events" to key up shift',
            "-e",
            'tell application "System Events" to key up option',
            "-e",
            'tell application "System Events" to key up command',
            "-e",
            f'tell application "System Events" to key code {key_code} using {{command down}}',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def select_current_line():
    result = subprocess.run(
        [
            "/usr/bin/osascript",
            "-e",
            'tell application "System Events" to key up shift',
            "-e",
            'tell application "System Events" to key up option',
            "-e",
            'tell application "System Events" to key up command',
            "-e",
            'tell application "System Events" to key code 124 using {command down}',
            "-e",
            'tell application "System Events" to key code 123 using {command down, shift down}',
            "-e",
            'tell application "System Events" to key code 123 using {command down, shift down}',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def finish_current_line(action):
    command = [
        "/usr/bin/osascript",
        "-e",
        'tell application "System Events" to key code 124 using {command down}',
    ]
    if action == "cut":
        command.extend(
            ["-e", 'tell application "System Events" to key code 51']
        )

    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def send_selection_to_general(pasteboard, key_code):
    previous_change_count = pasteboard.changeCount()
    if not post_shortcut(key_code):
        return False

    deadline = time.monotonic() + COPY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if pasteboard.changeCount() != previous_change_count:
            return True
        time.sleep(0.02)
    return False


def normalize_general_pasteboard_to_text():
    script = Path(__file__).with_name("paste_without_format.py")
    result = subprocess.run(
        [sys.executable, str(script), "--copy-only"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def copy_to_secondary(general, secondary, multi_items, *, cut=False):
    original = snapshot_pasteboard(general)
    try:
        if not send_selection_to_general(general, 8):
            print("Unable to copy the current selection.", file=sys.stderr)
            return 1

        if multi_items:
            copied = snapshot_pasteboard(general)
        else:
            if not normalize_general_pasteboard_to_text():
                print("Unable to convert the copied content to plain text.", file=sys.stderr)
                return 1
            text = general.stringForType_(TEXT_TYPE)
            copied = text_snapshot(str(text)) if text else []

        if not copied:
            print("The copied selection has no supported pasteboard data.", file=sys.stderr)
            return 1

        restore_pasteboard(secondary, copied)
        if cut and not send_selection_to_general(general, 7):
            print("Unable to cut the current selection.", file=sys.stderr)
            return 1
        return 0
    finally:
        restore_pasteboard(general, original)


def paste_from_secondary(general, secondary, multi_items):
    if multi_items:
        copied = snapshot_pasteboard(secondary)
    else:
        text = secondary.stringForType_(TEXT_TYPE)
        copied = text_snapshot(str(text)) if text is not None else []

    if not copied:
        print("The secondary pasteboard is empty or has no supported data.", file=sys.stderr)
        return 1

    original = snapshot_pasteboard(general)
    try:
        restore_pasteboard(general, copied)
        if not post_shortcut(9):
            print("Unable to send the paste shortcut.", file=sys.stderr)
            return 1
        time.sleep(PASTE_RESTORE_DELAY_SECONDS)
        return 0
    finally:
        restore_pasteboard(general, original)


def main():
    args = parse_args()
    general = NSPasteboard.generalPasteboard()
    secondary = NSPasteboard.pasteboardWithName_(args.pasteboard_name)

    if args.current_line and args.action not in ("copy", "cut"):
        print("--current-line requires copy or cut.", file=sys.stderr)
        return 2

    if args.action in ("copy", "cut"):
        if args.current_line and not select_current_line():
            print("Unable to select the current line.", file=sys.stderr)
            return 1
        result = copy_to_secondary(
            general,
            secondary,
            args.multi_items,
            cut=args.action == "cut",
        )
        if result == 0 and args.current_line and not finish_current_line(args.action):
            print("Unable to finish the current-line operation.", file=sys.stderr)
            return 1
        return result
    if args.action == "paste":
        return paste_from_secondary(general, secondary, args.multi_items)

    secondary.clearContents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
