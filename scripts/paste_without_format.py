#!/usr/bin/env python3
import argparse
import html
import json
import re
import subprocess
import sys
import time

import keyboard_events
from tooltip import notify


READ_CLIPBOARD_SCRIPT = r"""
import json
import plistlib
import sys
from AppKit import NSPasteboard, NSAttributedString

def valid_paths(value):
    if value is None or isinstance(value, (str, bytes)):
        return []
    try:
        paths = list(value)
    except TypeError:
        return []
    return [str(path) for path in paths if isinstance(path, str) and str(path).startswith("/")]

pasteboard = (NSPasteboard.pasteboardWithName_(sys.argv[1])
              if len(sys.argv) > 1 else NSPasteboard.generalPasteboard())
types = set(pasteboard.types() or [])
paths = (valid_paths(pasteboard.propertyListForType_("NSFilenamesPboardType"))
         if "NSFilenamesPboardType" in types else [])

if not paths:
    for item in pasteboard.pasteboardItems() or []:
        if "NSFilenamesPboardType" not in (item.types() or []):
            continue
        data = item.dataForType_("NSFilenamesPboardType")
        if data is not None:
            try:
                paths = valid_paths(plistlib.loads(bytes(data)))
            except Exception:
                paths = []
            if paths:
                break

        text = item.stringForType_("NSFilenamesPboardType")
        if text:
            try:
                paths = valid_paths(plistlib.loads(str(text).encode("utf-8")))
            except Exception:
                paths = []
            if paths:
                break

text = None
for kind in ("public.utf8-plain-text", "public.utf16-external-plain-text",
             "public.utf16-plain-text", "NSStringPboardType"):
    if kind not in types:
        continue
    text = pasteboard.stringForType_(kind)
    if text is not None:
        break
source_html = None
if text is None and "public.html" in types:
    source_html = pasteboard.stringForType_("public.html")
if text is None and source_html is None and "public.rtf" in types:
    rtf = pasteboard.dataForType_("public.rtf")
    if rtf is not None:
        attributed, _ = NSAttributedString.alloc().initWithRTF_documentAttributes_(rtf, None)
        if attributed is not None:
            text = attributed.string()

print(json.dumps({"paths": paths, "text": text, "html": source_html}, ensure_ascii=False))
"""


#* 高级粘贴功能，翻译自 windows 版的 AHK-SysUtil 项目
def advanced_text_processing(text):
    ZERO_WIDTH_SYMBOLS = "\u200b\u200c\u200d\u200e\u200f\u2060\ufeff\u202a\u202b\u202c\u202d\u202e\u206a\u206b\u206c\u206d\u206e\u206f"
    NARROW_SPACES = "\u00a0\u2000\u2002\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f"
    WIDE_SPACES = "\u2001\u2003\u3000"
    LIGATURES = {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "ft",
        "\ufb06": "st",
    }


    def delete_symbols(text, symbols, replacement=""):
        for symbol in symbols:
            text = text.replace(symbol, replacement)
        return text


    def delete_zero_width_symbols(text):
        return delete_symbols(text, ZERO_WIDTH_SYMBOLS)


    def convert_to_normal_space(text, wide_space_to_double=True):
        text = delete_symbols(text, NARROW_SPACES, " ")
        text = delete_symbols(text, WIDE_SPACES, "  " if wide_space_to_double else " ")
        return text.replace("\t", "    ")


    def split_ligature(text):
        for ligature, replacement in LIGATURES.items():
            text = text.replace(ligature, replacement)
        return text


    def is_quoted(text, prefix='"', suffix='"'):
        text = text.strip()
        return text.startswith(prefix) and text.endswith(suffix)


    def get_unquoted_string(text, unquote_nested=True):
        text = text.strip()
        for quote in ('"', "'"):
            while is_quoted(text, quote, quote):
                text = text[1:-1]
                if not unquote_nested:
                    break
        return text


    def get_quoted_string(text):
        text = text.strip()
        if not is_quoted(text):
            return f'"{text}"'
        return text


    def is_cjk_symbol(char):
        if len(char) != 1:
            return False

        value = ord(char)
        return (0x2E80 <= value <= 0x9FFF) or (0xFF01 <= value <= 0xFFEE)


    def convert_full_shape_to_half_shape(text, convert_chinese_punc=False):
        result = []
        for char in text:
            value = ord(char)
            if (
                not convert_chinese_punc
                and (
                    65282 <= value <= 65287
                    or 65290 <= value <= 65305
                    or 65308 <= value <= 65310
                    or 65312 <= value <= 65374
                )
            ):
                result.append(chr(value - 65248))
            elif convert_chinese_punc and 65282 <= value <= 65374:
                result.append(chr(value - 65248))
            elif value == 12288 or char == "\u00a0":
                result.append(" ")
            else:
                result.append(char)

        return "".join(result)


    def looks_like_path(text, multiline=False):
        path_pattern = re.compile(r"^(([A-Za-z]:)|\.(\.?)|~([A-Za-z]\w*)?)?(\\|/)(.*)")
        text = text.strip()

        if not multiline:
            return bool(path_pattern.match(text))

        lines = [line for line in re.split(r"\r\n|\r|\n", text) if line != ""]
        return bool(lines) and all(path_pattern.match(line.strip()) for line in lines)


    def replace_slash_in_path(text, mode=1):
        if mode == 0:
            return text
        if mode == 1:
            return text.replace("\\\\", "/").replace("\\", "/")
        if mode == 2:
            text = text.replace("/", "\\").replace("\\\\", "\\")
            return text.replace("\\", "\\\\")
        if mode == 3:
            return get_quoted_string(text)
        if mode == 4:
            text = text.replace("\\\\", "/").replace("\\", "/")
            return text.replace("/", "\\")
        if mode == 5:
            text = text.replace("\\", "/")
            match = re.match(r"^([A-Za-z]):(.*)$", text)
            if match:
                text = f"/{match.group(1).lower()}{match.group(2)}"
            return text
        if mode in (6, 7):
            match = re.match(r"^/([a-z])(.*)$", text)
            if match:
                text = f"{match.group(1).upper()}:{match.group(2)}"
            text = text.replace("/", "\\")
            if mode == 7:
                text = text.replace("\\", "/")
            return text
        if mode == 8:
            return "file:///" + text.replace("\\", "/").replace(" ", "%20")

        return text


    def remove_line_breaks(text):
        text = text.replace("\r\n", "\r").replace("\n", "\r").replace("\x02", "")
        result = []

        for index, char in enumerate(text):
            if char != "\r":
                result.append(char)
                continue

            previous_char = text[index - 1] if index > 0 else ""
            next_char = text[index + 1] if index + 1 < len(text) else ""

            if previous_char in ".。":
                result.append("\n")
            elif previous_char == " ":
                previous_previous_char = text[index - 2] if index > 1 else ""
                if previous_previous_char in ".。":
                    result.append("\n")
            elif not is_cjk_symbol(previous_char) and not is_cjk_symbol(next_char):
                result.append(" ")

        return "".join(result)
    text = text.strip()
    text = delete_zero_width_symbols(text)
    text = convert_to_normal_space(text)

    has_line_break = "\n" in text or "\r" in text
    if not has_line_break:
        text = get_unquoted_string(text)

        url_match = re.match(r"^(http|https|ftp)://(.+)", text, flags=re.I)
        if url_match:
            domain_match = re.search(r"//([\w.\d-]+)", text)
            if domain_match:
                text = domain_match.group(1)
        elif re.match(r"^file://[A-Za-z]:\\(.*)", text, flags=re.I):
            text = replace_slash_in_path(text[7:])
        elif re.match(r"^file:///[A-Za-z]:/(.*)", text, flags=re.I):
            text = text[8:]
        elif looks_like_path(text):
            text = replace_slash_in_path(text)
    elif looks_like_path(text, multiline=True):
        lines = re.split(r"\r\n|\r|\n", text)
        text = "\r\n".join(replace_slash_in_path(line.strip()) for line in lines if line != "")
    else:
        text = remove_line_breaks(text)

    text = convert_full_shape_to_half_shape(text)
    text = convert_to_normal_space(text, wide_space_to_double=False)
    text = split_ligature(text)
    return text




def run(command, *, input_text=None):
    return subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def read_clipboard_text(*, prefer_paths=True):
    # The configured -S entry point cannot import PyObjC. Read explicit formats
    # in a child using the same Python with site-packages enabled.
    result = subprocess.run(
        [sys.executable, "-c", READ_CLIPBOARD_SCRIPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError("Cannot read the clipboard. Check the Python Cocoa dependency.")
    try:
        content = json.loads(result.stdout)
        if prefer_paths and content["paths"]:
            return "\n".join(content["paths"])
        if content["text"] is not None:
            return content["text"]
        return html_to_text(content["html"]) if content["html"] else ""
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Cannot decode clipboard text.") from exc


def html_to_text(value):
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</(div|p|li|tr)\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<(div|p|li|tr)\b[^>]*>", "", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return html.unescape(value)



def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--advanced", action="store_true")
    parser.add_argument("--copy-only", action="store_true")
    parser.add_argument("--release-shift", action="store_true")
    return parser.parse_args()


def release_shift():
    keyboard_events.release_keys(
        keyboard_events.LEFT_SHIFT_KEY_CODE,
        keyboard_events.RIGHT_SHIFT_KEY_CODE,
    )


def paste():
    keyboard_events.release_keys(keyboard_events.V_KEY_CODE)
    keyboard_events.post_keystroke(
        keyboard_events.V_KEY_CODE,
        keyboard_events.COMMAND_FLAG,
    )


def main():
    args = parse_args()
    try:
        text = read_clipboard_text(prefer_paths=not args.advanced)
        if args.advanced:
            text = advanced_text_processing(text)
        if not text:
            message = "No text to paste. Clipboard unchanged."
            print(message, file=sys.stderr)
            if not args.copy_only:
                notify(message, level="warning")
            return 1
        if run(["/usr/bin/pbcopy"], input_text=text).returncode != 0:
            raise RuntimeError("Cannot write plain text to the clipboard.")
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        if not args.copy_only:
            message = "Clipboard reading timed out. Clipboard unchanged." if isinstance(exc, subprocess.TimeoutExpired) else str(exc)
            notify(message, level="error")
        return 1

    if args.copy_only:
        return 0

    # Give the triggering shortcut's modifiers and the pasteboard time to settle.
    try:
        if args.release_shift:
            release_shift()
        time.sleep(0.15)
        paste()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        notify("Cannot send the paste shortcut. Check Accessibility permission.", level="error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
