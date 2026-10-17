#!/usr/bin/env python3
"""Re-encode clipboard bitmap images as genuine PNG, including mislabeled data.

Adapted from PersonalScripts/tools/macos/rdp-clipboard-image-fix.py.
Runs once without confirmation or automatic paste. Only readable image items
are retained; all other representations are removed on a successful repair.
"""

import argparse
import importlib
import sys
from typing import Any

AppKit: Any = importlib.import_module("AppKit")

PNG_TYPE = "public.png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_DATA_BYTES = 128 * 1024 * 1024
MAX_ITEMS = 16
MAX_TYPES = 64


def prepare_png_items(items):
    """Decode by file contents and prepare all PNGs before changing the pasteboard."""
    if len(items) > MAX_ITEMS:
        raise RuntimeError("Too many clipboard items; clipboard unchanged.")

    supported = set(AppKit.NSBitmapImageRep.imageTypes()) | {PNG_TYPE, "public.tiff"}
    prepared = []
    for item in items:
        types = list(item.types() or [])
        if len(types) > MAX_TYPES:
            raise RuntimeError("Too many clipboard formats; clipboard unchanged.")
        image_types = sorted(
            (kind for kind in types if kind in supported),
            key=lambda kind: kind != PNG_TYPE,
        )
        selected = None
        for kind in image_types:
            data = item.dataForType_(kind)
            if data is None:
                continue
            if data.length() > MAX_DATA_BYTES:
                raise RuntimeError("Image exceeds 128 MiB limit; clipboard unchanged.")
            bitmap = AppKit.NSBitmapImageRep.imageRepWithData_(data)
            if selected is None and bitmap is not None:
                selected = bitmap

        if selected is None:
            continue
        png = selected.representationUsingType_properties_(
            AppKit.NSBitmapImageFileTypePNG, {}
        )
        if png is None or not bytes(png).startswith(PNG_SIGNATURE):
            raise RuntimeError("PNG encoding failed; clipboard unchanged.")
        verified = AppKit.NSBitmapImageRep.imageRepWithData_(png)
        if verified is None or (
            verified.pixelsWide(), verified.pixelsHigh()
        ) != (selected.pixelsWide(), selected.pixelsHigh()):
            raise RuntimeError("PNG validation failed; clipboard unchanged.")

        output = AppKit.NSPasteboardItem.alloc().init()
        if not output.setData_forType_(png, PNG_TYPE):
            raise RuntimeError("Cannot prepare PNG item; clipboard unchanged.")
        prepared.append(output)

    if not prepared:
        raise RuntimeError("Clipboard contains no readable bitmap image; clipboard unchanged.")
    return prepared


def repair_clipboard(pasteboard):
    before = pasteboard.changeCount()
    prepared = prepare_png_items(list(pasteboard.pasteboardItems() or []))
    if pasteboard.changeCount() != before:
        raise RuntimeError("Clipboard changed during reading; repair cancelled.")

    # Encoding and validation must finish before this destructive replacement.
    pasteboard.clearContents()
    if not pasteboard.writeObjects_(prepared):
        raise RuntimeError("Clipboard write failed after clearing. Copy the source image again.")

    written_count = pasteboard.changeCount()
    written = list(pasteboard.pasteboardItems() or [])
    if len(written) != len(prepared):
        raise RuntimeError("Clipboard changed or write verification failed.")
    for actual_item, expected_item in zip(written, prepared):
        actual = actual_item.dataForType_(PNG_TYPE)
        expected = expected_item.dataForType_(PNG_TYPE)
        if actual is None or not actual.isEqualToData_(expected):
            raise RuntimeError("Clipboard changed or PNG read-back verification failed.")
    if pasteboard.changeCount() != written_count:
        raise RuntimeError("Clipboard changed during write verification.")
    return len(prepared)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        count = repair_clipboard(AppKit.NSPasteboard.generalPasteboard())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Repaired {count} clipboard image(s) as PNG.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
