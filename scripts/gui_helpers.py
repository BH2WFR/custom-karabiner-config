"""Shared Tk/macOS GUI behavior. Importing this module does not create a window."""

import importlib
from typing import Any

AppKit: Any = importlib.import_module("AppKit")


def activate_window(root):
    """Schedule one activation and return its Tk timer ID for optional cancellation."""
    def activate():
        options = (
            AppKit.NSApplicationActivateIgnoringOtherApps
            | AppKit.NSApplicationActivateAllWindows
        )
        AppKit.NSRunningApplication.currentApplication().activateWithOptions_(options)
        root.lift()
        root.focus_force()

    return root.after(100, activate)


def copy_text(root, text):
    root.clipboard_clear()
    root.clipboard_append(text)

