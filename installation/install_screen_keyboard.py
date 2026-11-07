#!/usr/bin/env python3
"""Build/register a local Dock launcher; does not change Dock or fallback settings."""

import argparse
import importlib
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ID = "com.personal-scripts.caps-keyboard"
LSREGISTER = Path("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister")


def make_icon(path):
    """Render the system keyboard symbol into an application icon."""
    a = importlib.import_module("AppKit")
    image = a.NSImage.alloc().initWithSize_((512, 512))
    image.lockFocus()
    a.NSColor.colorWithSRGBRed_green_blue_alpha_(.12, .43, .48, 1).setFill()
    a.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(((24, 24), (464, 464)), 92, 92).fill()
    symbol = a.NSImage.imageWithSystemSymbolName_accessibilityDescription_("keyboard", "Caps Keyboard")
    symbol.drawInRect_fromRect_operation_fraction_(((68, 140), (376, 232)), ((0, 0), (0, 0)),
                                                   a.NSCompositingOperationSourceOver, 1)
    image.unlockFocus()
    rep = a.NSBitmapImageRep.imageRepWithData_(image.TIFFRepresentation())
    png = rep.representationUsingType_properties_(a.NSBitmapImageFileTypePNG, {})
    # AppKit renders at the current backing scale (512 or 1024 pixels).
    data = bytes(png)
    kind = {512: b"ic09", 1024: b"ic10"}[rep.pixelsWide()]
    element = kind + (len(data) + 8).to_bytes(4, "big") + data
    path.write_bytes(b"icns" + (len(element) + 8).to_bytes(4, "big") + element)


def install(destination, python, *, register=True):
    destination = destination.expanduser().absolute()
    python = python.expanduser().absolute()
    if destination.suffix != ".app":
        raise ValueError("Destination must end in .app")
    if not python.is_file():
        raise ValueError(f"Python interpreter not found: {python}")
    if destination.exists():
        info = destination / "Contents/Info.plist"
        if not info.is_file() or plistlib.loads(info.read_bytes()).get("CFBundleIdentifier") != BUNDLE_ID:
            raise ValueError(f"Refusing to replace an unrelated application: {destination}")
    (ROOT / "tmp").mkdir(exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="keyboard-install-", dir=ROOT / "tmp") as temporary:
        stage = Path(temporary) / destination.name
        macos = stage / "Contents/MacOS"
        resources = stage / "Contents/Resources"
        macos.mkdir(parents=True)
        resources.mkdir()
        subprocess.run(["/usr/bin/swiftc", "-O", "-framework", "AppKit",
                        str(Path(__file__).with_name("CapsKeyboardLauncher.swift")),
                        "-o", str(macos / "CapsKeyboard")], check=True)
        info = {
            "CFBundleExecutable": "CapsKeyboard", "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleName": "Caps Keyboard", "CFBundleDisplayName": "Caps Keyboard",
            "CFBundlePackageType": "APPL", "CFBundleVersion": "1",
            "CFBundleShortVersionString": "1.0", "CFBundleIconFile": "Keyboard.icns",
            "LSUIElement": True, "NSHighResolutionCapable": True,
            "KeyboardPython": str(python), "KeyboardScript": str(ROOT / "scripts/screen_keyboard.py"),
        }
        (stage / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
        make_icon(resources / "Keyboard.icns")
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(stage)], check=True)
        backup = Path(temporary) / "previous.app"
        if destination.exists():
            shutil.move(str(destination), str(backup))
        try:
            shutil.move(str(stage), str(destination))
        except Exception:
            if backup.exists():
                shutil.move(str(backup), str(destination))
            raise
    if register:
        subprocess.run([str(LSREGISTER), "-f", str(destination)], check=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path.home() / "Applications/Caps Keyboard.app")
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    try:
        path = install(args.destination, args.python)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Installation failed: {exc}\n")
    print(f"Installed: {path}\nDrag this application to the Dock. Fallback was not changed.")


if __name__ == "__main__":
    main()
