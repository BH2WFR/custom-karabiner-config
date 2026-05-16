#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import insert_unicode_symbol


INDENT_SPACES = "    "
INDENT_TAB = "\t"


def run(command, *, input_text=None):
    return subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def clipboard(preferred_type="txt"):
    result = run(["/usr/bin/pbpaste", "-Prefer", preferred_type])
    return result.stdout if result.returncode == 0 else ""


def set_clipboard(text):
    run(["/usr/bin/pbcopy"], input_text=text)


def key_code(code, modifiers=None):
    modifiers = modifiers or []
    if modifiers:
        modifier_text = " using {" + ", ".join(f"{key} down" for key in modifiers) + "}"
    else:
        modifier_text = ""

    subprocess.run(
        [
            "/usr/bin/osascript",
            "-e",
            f'tell application "System Events" to key code {code}{modifier_text}',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def copy_selection():
    key_code(8, ["command"])
    time.sleep(0.12)
    return clipboard("txt")


def paste_text(text):
    set_clipboard(text)
    time.sleep(0.08)
    key_code(9, ["command"])


def split_lines_keepends(text):
    return re.findall(r".*?(?:\r\n|\n|\r|$)", text)[:-1]


def line_body_and_newline(line):
    match = re.match(r"^(.*?)(\r\n|\n|\r)?$", line, flags=re.S)
    if not match:
        return line, ""
    return match.group(1), match.group(2) or ""


def leading_indent(line):
    match = re.match(r"^[ \t]*", line)
    return match.group(0) if match else ""


def choose_indent_unit(text):
    tab_score = 0
    space_score = 0

    for line in split_lines_keepends(text):
        body, _newline = line_body_and_newline(line)
        if not body.strip():
            continue

        indent = leading_indent(body)
        if indent.startswith(INDENT_TAB):
            tab_score += 1
        if len(indent) >= len(INDENT_SPACES) and indent[: len(INDENT_SPACES)] == INDENT_SPACES:
            space_score += 1

    return INDENT_TAB if tab_score > space_score else INDENT_SPACES


def is_indented_line(body):
    if not body.strip():
        return True
    indent = leading_indent(body)
    return indent.startswith(INDENT_TAB) or indent.startswith(INDENT_SPACES)


def indent_text(text):
    indent_unit = choose_indent_unit(text)
    result = []

    for line in split_lines_keepends(text):
        body, newline = line_body_and_newline(line)
        if body:
            body = indent_unit + body
        result.append(body + newline)

    return "".join(result)


def unindent_body(body):
    if body.startswith(INDENT_TAB):
        return body[1:]
    if body.startswith(INDENT_SPACES):
        return body[len(INDENT_SPACES) :]
    return body


def unindent_text(text):
    result = []

    for line in split_lines_keepends(text):
        body, newline = line_body_and_newline(line)
        result.append(unindent_body(body) + newline)

    return "".join(result)


def toggle_indent_text(text):
    lines = split_lines_keepends(text)
    should_unindent = bool(lines) and all(
        is_indented_line(line_body_and_newline(line)[0])
        for line in lines
    )
    return unindent_text(text) if should_unindent else indent_text(text)


def parse_args():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--indent", action="store_true")
    action.add_argument("--unindent", action="store_true")
    action.add_argument("--toggle", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    env = os.environ.copy()
    previous_clipboard = insert_unicode_symbol.clipboard_snapshot(
        insert_unicode_symbol.RESTORE_CLIPBOARD_MAX_BYTES,
        env,
    )

    text = copy_selection()
    if not text:
        return 0

    if args.indent:
        text = indent_text(text)
    elif args.unindent:
        text = unindent_text(text)
    else:
        text = toggle_indent_text(text)

    paste_text(text)
    if previous_clipboard is not None:
        time.sleep(0.15)
        insert_unicode_symbol.restore_clipboard_snapshot(previous_clipboard, env)

    return 0


if __name__ == "__main__":
    sys.exit(main())
