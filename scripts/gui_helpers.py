"""Shared Tk/macOS GUI behavior. Importing this module does not create a window."""

import importlib
from typing import Any

AppKit: Any = importlib.import_module("AppKit")


def activate_window(root):
    """Activate once after Tk starts; leave the window at its normal level."""
    def activate():
        options = (
            AppKit.NSApplicationActivateIgnoringOtherApps
            | AppKit.NSApplicationActivateAllWindows
        )
        AppKit.NSRunningApplication.currentApplication().activateWithOptions_(options)
        root.lift()
        root.focus_force()

    root.after(100, activate)


def copy_text(root, text):
    root.clipboard_clear()
    root.clipboard_append(text)

