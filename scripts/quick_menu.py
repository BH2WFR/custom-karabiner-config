#!/usr/bin/env python3
"""Open a native menu of macOS folders, settings and utilities at the pointer."""

from dataclasses import dataclass
import fcntl
import importlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time
from typing import Any

from tooltip import notify

AppKit: Any = importlib.import_module("AppKit")
Foundation: Any = importlib.import_module("Foundation")
CONFIG_PATH = Path(__file__).with_suffix(".json")


@dataclass
class Entry:
    title: str
    target: str | dict = ""
    children: tuple = ()
    enabled: bool = True


def folder(title, path):
    path = Path(path).expanduser()
    return Entry(title, str(path), enabled=path.is_dir())


def homebrew_cache():
    # Karabiner's PATH may omit both standard Homebrew installation locations.
    brew = shutil.which("brew") or next(
        (path for path in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew")
         if os.access(path, os.X_OK)), None,
    )
    if not brew:
        return None
    try:
        result = subprocess.run(
            [brew, "--cache"], capture_output=True, text=True, check=True,
            timeout=2, env={**os.environ, "HOMEBREW_NO_AUTO_UPDATE": "1"},
        )
        path = Path(result.stdout.strip())
        return path if path.is_absolute() else None
    except (OSError, subprocess.SubprocessError):
        return None


def application(title, name, bundle_id=None):
    if bundle_id:
        url = AppKit.NSWorkspace.sharedWorkspace().URLForApplicationWithBundleIdentifier_(bundle_id)
        if url is not None and Path(url.path()).is_dir():
            return Entry(title, str(url.path()))
    for directory in (
        Path("/System/Applications/Utilities"), Path("/System/Applications"),
        Path("/System/Library/CoreServices/Applications"), Path("/Applications"),
        Path.home() / "Applications",
    ):
        path = directory / f"{name}.app"
        if path.is_dir():
            return Entry(title, str(path))
    return None


def cloud_folders():
    home = Path.home()
    entries = []
    icloud = home / "Library/Mobile Documents/com~apple~CloudDocs"
    if icloud.is_dir():
        entries.append(folder("iCloud Drive", icloud))
    for name, bundle_id, pattern in (
        ("OneDrive", "com.microsoft.OneDrive", "OneDrive*"),
        ("Dropbox", "com.getdropbox.dropbox", "Dropbox*"),
        ("Google Drive", "com.google.drivefs", "GoogleDrive*"),
        ("Box", "com.box.desktop", "Box*"),
    ):
        if application(name, name, bundle_id) is not None:
            entries.extend(folder(path.name, path) for path in
                           sorted((home / "Library/CloudStorage").glob(pattern)) if path.is_dir())
    return entries


def configured_entries(section, config_path=CONFIG_PATH):
    try:
        with config_path.open(encoding="utf-8") as stream:
            config = json.load(stream)
    except FileNotFoundError:
        return ()
    if not isinstance(config, dict) or not isinstance(config.get(section, []), list):
        raise ValueError(f"{section} must be a JSON array")
    entries = []
    key = {"applications": "name", "commands": "command"}.get(section, "path")
    for item in config.get(section, []):
        if not isinstance(item, dict) or not all(
            isinstance(item.get(field), str) and item[field].strip() for field in ("title", key)
        ):
            raise ValueError(f"Each {section} entry needs a nonempty title and {key}")
        if section == "commands":
            if "\0" in item["command"]:
                raise ValueError("Command must not contain NUL characters")
            output = item.get("output", "gui")
            cwd = item.get("cwd", "~")
            if output not in ("gui", "terminal"):
                raise ValueError("Command output must be gui or terminal")
            if not isinstance(cwd, str) or not cwd.strip():
                raise ValueError("Command cwd must be a nonempty path")
            path = Path(cwd).expanduser()
            if not path.is_absolute():
                path = config_path.resolve().parent / path
            entries.append(Entry(item["title"], {
                "title": item["title"], "command": item["command"],
                "output": output, "cwd": str(path.resolve()),
            }))
            continue
        if section == "applications":
            bundle_id = item.get("bundle_id")
            if bundle_id is not None and (not isinstance(bundle_id, str) or not bundle_id.strip()):
                raise ValueError("bundle_id must be a nonempty string")
            entry = application(item["title"], item["name"], bundle_id)
            if entry is not None:
                entries.append(entry)
            continue
        path = Path(item["path"]).expanduser()
        if not path.is_absolute():
            path = config_path.resolve().parent / path
        if path.is_dir():
            entries.append(folder(item["title"], path.resolve()))
    return tuple(entries)


def settings_entries():
    entries = []
    for title, name in (
        ("Network", "Network"), ("Bluetooth", "Bluetooth"),
        ("Keyboard / Input Sources", "Keyboard"), ("Mouse", "Mouse"),
        ("Trackpad", "Trackpad"), ("Displays", "Displays"),
        ("Sound", "Sound"), ("Privacy & Security", "Security"),
        ("Accessibility", "UniversalAccessPref"), ("Users & Groups", "Accounts"),
        ("Battery", "Battery"), ("Sharing", "SharingPref"),
        ("Software Update", "SoftwareUpdate"),
    ):
        path = Path("/System/Library/PreferencePanes") / f"{name}.prefPane"
        if path.exists():
            entries.append(Entry(title, str(path)))
    info = Path("/System/Library/ExtensionKit/Extensions/LoginItems.appex/Contents/Info.plist")
    if info.is_file():
        with info.open("rb") as stream:
            bundle_id = plistlib.load(stream).get("CFBundleIdentifier")
        if bundle_id:
            entries.append(Entry("Login Items & Extensions", f"x-apple.systempreferences:{bundle_id}"))
    return tuple(entries)


def menu_entries():
    home = Path.home()
    paths = [folder(name, home / name) for name in
             ("Desktop", "Documents", "Pictures", "Music", "Movies")]
    clouds = cloud_folders()
    if clouds:
        paths.append(Entry(""))
        paths.extend(clouds)
    paths.append(Entry(""))
    paths.extend(folder(title, path) for title, path in (
        ("User Library", home / "Library"),
        ("Application Support", home / "Library/Application Support"),
        ("Preferences", home / "Library/Preferences"),
        ("Caches", home / "Library/Caches"),
        ("App Containers", home / "Library/Containers"),
        ("Group Containers", home / "Library/Group Containers"),
        ("User Applications", home / "Applications"),
        ("Temporary Files", Foundation.NSTemporaryDirectory()),
    ))
    cache = homebrew_cache()
    if cache is not None:
        paths.append(folder("Homebrew Cache", cache))
    paths.append(Entry(""))
    paths.extend(folder(title, path) for title, path in (
        ("Shared Application Support", "/Library/Application Support"),
        ("System Applications", "/System/Applications"),
        ("Disks / Volumes", "/Volumes"), ("Root", "/"), ("System", "/System"),
    ))
    paths.append(Entry(""))
    paths.extend(folder(title, path) for title, path in (
        ("User Launch Agents", home / "Library/LaunchAgents"),
        ("Shared Launch Agents", "/Library/LaunchAgents"),
        ("Launch Daemons", "/Library/LaunchDaemons"),
    ))
    utilities = tuple(entry for name in (
        "Activity Monitor", "Console", "Disk Utility", "System Information",
        "Keychain Access", "Terminal", "Calculator", "TextEdit", "Preview",
        "Screenshot", "Digital Color Meter", "Audio MIDI Setup", "Screen Sharing",
    ) if (entry := application(name, name)) is not None)
    try:
        personal = configured_entries("personal_folders")
        custom_apps = configured_entries("applications")
        commands = configured_entries("commands")
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Quick menu configuration: {exc}", file=sys.stderr)
        notify("Invalid quick_menu.json. Custom entries skipped.", level="warning")
        personal, custom_apps, commands = (), (), ()
    if custom_apps:
        utilities += ((Entry(""),) if utilities else ()) + custom_apps
    return (
        Entry("Finder", "/System/Library/CoreServices/Finder.app"),
        folder("Home", home), folder("Downloads", home / "Downloads"),
        folder("Applications", "/Applications"), Entry("Trash", "trash:"),
        Entry("System Settings", "/System/Applications/System Settings.app"),
        Entry(""), Entry("Common Folders", children=tuple(paths)),
        Entry("Settings Pages", children=settings_entries()),
        Entry("Utilities", children=utilities),
        *((Entry("Personal Folders", children=personal),) if personal else ()),
        *((Entry("Commands", children=commands),) if commands else ()),
        Entry(""), Entry("Exit", "exit:"),
    )


class MenuTarget(Foundation.NSObject):
    def choose_(self, sender):
        self.selected = sender.representedObject()
        if self.selected == "exit:":
            self.selected = None


def build_menu(entries, target):
    menu = AppKit.NSMenu.alloc().initWithTitle_("Quick Access")
    menu.setAutoenablesItems_(False)
    workspace = AppKit.NSWorkspace.sharedWorkspace()
    for entry in entries:
        if not entry.title:
            menu.addItem_(AppKit.NSMenuItem.separatorItem())
            continue
        item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            entry.title, "choose:" if entry.target else None, "",
        )
        item.setEnabled_(entry.enabled and bool(entry.target or entry.children))
        if entry.children:
            item.setSubmenu_(build_menu(entry.children, target))
        elif entry.target:
            item.setTarget_(target)
            item.setRepresentedObject_(entry.target)
            destination = entry.target
            if isinstance(destination, dict):
                item.setToolTip_(destination["command"])
                icon = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_("terminal", None)
            else:
                item.setToolTip_("Close menu" if destination == "exit:" else destination)
                icon = (workspace.iconForFile_(destination) if destination.startswith("/")
                        else AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                            {"trash:": "trash", "exit:": "xmark"}.get(destination, "gearshape"), None))
            if icon is not None:
                icon = icon.copy()
                icon.setSize_((16, 16))
                item.setImage_(icon)
        menu.addItem_(item)
    return menu


def open_target(target):
    if not isinstance(target, str):
        from menu_command import launch_command
        launch_command(target)
        return
    if target == "trash:":
        subprocess.run(
            ["/usr/bin/osascript", "-e", 'tell application "Finder" to open trash',
             "-e", 'tell application "Finder" to activate'],
            check=True, capture_output=True, timeout=10,
        )
        return
    if target.startswith("/"):
        if not Path(target).exists():
            raise RuntimeError("This location is no longer available.")
        url = Foundation.NSURL.fileURLWithPath_(target)
    else:
        url = Foundation.NSURL.URLWithString_(target)
    if not AppKit.NSWorkspace.sharedWorkspace().openURL_(url):
        raise RuntimeError("Could not open the selected item.")


def show_menu():
    app = AppKit.NSApplication.sharedApplication()
    previous = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    target = MenuTarget.alloc().init()
    target.selected = None
    menu = build_menu(menu_entries(), target)
    # A standalone menu needs an active application to keep tracking mouse events.
    app.finishLaunching()
    app.activateIgnoringOtherApps_(True)
    deadline = time.monotonic() + 0.5
    while not app.isActive() and time.monotonic() < deadline:
        Foundation.NSRunLoop.currentRunLoop().runUntilDate_(
            Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.01))
    try:
        menu.popUpMenuPositioningItem_atLocation_inView_(None, AppKit.NSEvent.mouseLocation(), None)
    finally:
        if not target.selected and app.isActive() and previous is not None:
            previous.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
    # Launch only after menu tracking ends, so it cannot steal focus back.
    if target.selected:
        open_target(target.selected)


def main():
    try:
        with open(__file__, "rb") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            show_menu()
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Quick menu: {exc}", file=sys.stderr)
        notify("Could not open the quick menu item.", level="error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
