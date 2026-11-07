#!/usr/bin/env python3
"""Non-activating keyboard panel for testing Karabiner's CGEventTap fallback."""

import argparse
import fcntl
import importlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from keyboard_events import (
    CAPS_LOCK_FLAG, C_KEY_CODE, HID_EVENT_TAP, MODIFIER_KEYS, ONE_KEY_CODE, SIX_KEY_CODE, V_KEY_CODE, can_post_events,
    current_modifier_flags, post_key_event,
)
from tooltip import notify

ROOT = Path(__file__).resolve().parent.parent
CLI = "/Library/Application Support/org.pqrs/Karabiner-Elements/bin/karabiner_cli"
CAPS_VARIABLE = "caps_primary_layer"
TAP_KEYS = {"1": ONE_KEY_CODE, "C": C_KEY_CODE, "V": V_KEY_CODE, "6": SIX_KEY_CODE}


def set_caps_layer(enabled):
    subprocess.run(
        [CLI, "--set-variables", json.dumps({CAPS_VARIABLE: int(enabled)})],
        check=True, capture_output=True, text=True, timeout=3,
    )


def check_setup():
    config = json.loads((ROOT / "karabiner.json").read_text(encoding="utf-8"))
    if not config.get("global", {}).get("enable_cgeventtap_fallback", False):
        raise RuntimeError("Enable CGEventTap fallback in Karabiner first.")
    if not Path(CLI).is_file():
        raise RuntimeError("Karabiner command-line tool was not found.")
    if not can_post_events():
        raise RuntimeError("Python needs Accessibility permission to send keys.")


class KeyboardState:
    def __init__(self, event_keys=None, *, event_tap=HID_EVENT_TAP):
        self.held = []
        self.caps = False
        self.event_keys = MODIFIER_KEYS if event_keys is None else event_keys
        self.event_tap = event_tap

    def flags(self):
        flags = current_modifier_flags() & CAPS_LOCK_FLAG
        for name in self.held:
            _, generic, side = self.event_keys[name]
            flags |= generic | side
        return flags

    def toggle(self, name):
        if name == "Caps" and name not in self.event_keys:
            set_caps_layer(not self.caps)
            self.caps = not self.caps
            return self.caps
        old = self.held.copy()
        down = name not in self.held
        if down:
            self.held.append(name)
        else:
            self.held.remove(name)
        try:
            code, generic, _ = self.event_keys[name]
            post_key_event(code, down, self.flags(),
                           flags_changed=bool(generic), event_tap=self.event_tap)
        except Exception:
            self.held = old
            raise
        return down

    def release(self, *, keep=()):
        """Release transient keys and Caps, optionally retaining named modifiers."""
        errors = []
        # Reverse press order, keeping Caps active until Option has been released.
        for name in self.held.copy()[::-1]:
            if name in keep:
                continue
            try:
                self.toggle(name)
            except Exception as exc:
                errors.append(str(exc))
        if self.caps:
            try:
                set_caps_layer(False)
                self.caps = False
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))


def create_panel(state):
    AppKit: Any = importlib.import_module("AppKit")
    Foundation: Any = importlib.import_module("Foundation")
    objc: Any = importlib.import_module("objc")

    class TestKeyboardPanel(AppKit.NSPanel):
        def canBecomeKeyWindow(self):
            return False

        def canBecomeMainWindow(self):
            return False

    class TestKeyboardButton(AppKit.NSButton):
        def acceptsFirstMouse_(self, event):
            return True

        def needsPanelToBecomeKey(self):
            return False

    class TestKeyboardController(Foundation.NSObject):
        @objc.python_method
        def setup(self, panel):
            self.panel = panel
            self.buttons = {}
            self.timer = None
            self.key_down = None
            self.closed = False

        @objc.python_method
        def sync_buttons(self):
            for name, button in self.buttons.items():
                button.setEnabled_(self.key_down is None)
                if name not in TAP_KEYS:
                    active = state.caps if name == "Caps" else name in state.held
                    button.setState_(AppKit.NSControlStateValueOn if active else AppKit.NSControlStateValueOff)

        def clicked_(self, sender):
            try:
                name = str(sender.title())
                if name in TAP_KEYS:
                    if self.key_down is not None:
                        return
                    post_key_event(TAP_KEYS[name], True, state.flags(), event_tap=HID_EVENT_TAP)
                    self.key_down = TAP_KEYS[name]
                    self.sync_buttons()
                    self.timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                        0.1, self, "releaseKey:", None, False,
                    )
                else:
                    active = state.toggle(name)
                    sender.setState_(AppKit.NSControlStateValueOn if active else AppKit.NSControlStateValueOff)
            except Exception as exc:
                notify(str(exc), level="error")
                self.sync_buttons()

        def releaseKey_(self, timer):
            try:
                self.release()
            except Exception as exc:
                notify(str(exc), level="error")

        @objc.python_method
        def release(self):
            if self.timer:
                self.timer.invalidate()
                self.timer = None
            try:
                if self.key_down is not None:
                    post_key_event(self.key_down, False, state.flags(), event_tap=HID_EVENT_TAP)
                    self.key_down = None
            finally:
                try:
                    state.release()
                finally:
                    self.sync_buttons()

        def windowWillClose_(self, notification):
            self.closed = True

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    width, height = 536, 88
    bounds = AppKit.NSScreen.mainScreen().visibleFrame()
    frame = ((bounds.origin.x + (bounds.size.width - width) / 2,
              bounds.origin.y + 60), (width, height))
    panel = TestKeyboardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable
        | AppKit.NSWindowStyleMaskNonactivatingPanel, AppKit.NSBackingStoreBuffered, False,
    )
    panel.setTitle_("Keyboard Test")
    panel.setReleasedWhenClosed_(False)
    panel.setHidesOnDeactivate_(False)
    panel.setBecomesKeyOnlyIfNeeded_(True)
    panel.setLevel_(AppKit.NSFloatingWindowLevel)
    panel.setCollectionBehavior_(
        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        | AppKit.NSWindowCollectionBehaviorIgnoresCycle
    )
    controller = TestKeyboardController.alloc().init()
    controller.setup(panel)
    panel.setDelegate_(controller)
    rows = [("LCtrl", "LOpt", "LCmd", "LShift", "RCtrl", "ROpt", "RCmd", "RShift"),
            ("Caps", "Fn", "1", "C", "V", "6")]
    for row, names in enumerate(rows):
        for column, name in enumerate(names):
            button = TestKeyboardButton.alloc().initWithFrame_(((8 + column * 66, 46 - row * 38), (60, 32)))
            button.setTitle_(name)
            button.setFont_(AppKit.NSFont.systemFontOfSize_(13))
            button.setBezelStyle_(AppKit.NSBezelStyleRegularSquare)
            button.setButtonType_(AppKit.NSButtonTypeMomentaryPushIn if name in TAP_KEYS else AppKit.NSButtonTypePushOnPushOff)
            button.setRefusesFirstResponder_(True)
            button.setToolTip_(f"Send {name} and release modifiers" if name in TAP_KEYS else f"Toggle {name}")
            button.setTarget_(controller)
            button.setAction_("clicked:")
            panel.contentView().addSubview_(button)
            controller.buttons[name] = button
    return app, panel, controller


def run_panel(app, controller):
    AppKit: Any = importlib.import_module("AppKit")
    Foundation: Any = importlib.import_module("Foundation")
    # NSApplication.run() activates a fresh unbundled Python process at launch.
    # Dispatch events directly instead, blocking while idle (no polling timer).
    while not controller.closed:
        event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
            AppKit.NSEventMaskAny, Foundation.NSDate.distantFuture(),
            Foundation.NSDefaultRunLoopMode, True,
        )
        if event:
            app.sendEvent_(event)
        app.updateWindows()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check prerequisites without opening a window")
    args = parser.parse_args()
    try:
        check_setup()
        if args.check:
            print("CGEventTap fallback enabled; event-posting permission available.")
            return 0
        (ROOT / "tmp").mkdir(exist_ok=True)
        with (ROOT / "tmp" / "test_keyboard.lock").open("a", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Keyboard Test is already running.") from None
            state = KeyboardState()
            app, panel, controller = create_panel(state)
            try:
                panel.orderFrontRegardless()
                run_panel(app, controller)
            finally:
                controller.release()
                panel.orderOut_(None)
        return 0
    except Exception as exc:
        if args.check:
            print(str(exc), file=sys.stderr)
        else:
            notify(str(exc), level="error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
