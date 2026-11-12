#!/usr/bin/env python3
"""Non-activating keyboard with optional Karabiner function layers."""

import argparse
from collections.abc import Sequence
import fcntl
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
from typing import Any

import keyboard_events as keys
from input_sources import switch_input_source
from test_keyboard import CLI, KeyboardState, ROOT, run_panel
from tooltip import notify, panel_frame_near_pointer

NOTIFICATION = "com.personal-scripts.caps-keyboard.command"
DEFAULT_SIZE = (533, 207)
MINIMUM_SIZE = (456, 186)
MODIFIER_LOCK_DELAY = .5
LOCKED_BACKGROUND = (122, 32, 42)
LOCKED_TEXT = (255, 225, 96)
NUMPAD_UNITS = 4
NUMPAD_MODE_COLORS = {"off": (232, 160, 125), "on": (159, 73, 41), "pressed": (244, 189, 157)}
# Name, number-mode label/key, navigation label/key, column, row, width, height.
NUMPAD = [
    ("pad_mode", "Num", None, "Nav", None, 0, 0, 1, 1),
    ("pad_divide", "/", "keypad_divide", "/", "keypad_divide", 1, 0, 1, 1),
    ("pad_multiply", "*", "keypad_multiply", "*", "keypad_multiply", 2, 0, 1, 1),
    ("pad_minus", "-", "keypad_minus", "-", "keypad_minus", 3, 0, 1, 1),
    ("pad_7", "7", "7", "Home", "home", 0, 1, 1, 1),
    ("pad_8", "8", "8", "\u2191", "up_arrow", 1, 1, 1, 1),
    ("pad_9", "9", "9", "PgUp", "page_up", 2, 1, 1, 1),
    ("pad_plus", "+", "keypad_plus", "+", "keypad_plus", 3, 1, 1, 2),
    ("pad_4", "4", "4", "\u2190", "left_arrow", 0, 2, 1, 1),
    ("pad_5", "5", "5", "\u00b7", None, 1, 2, 1, 1),
    ("pad_6", "6", "6", "\u2192", "right_arrow", 2, 2, 1, 1),
    ("pad_1", "1", "1", "End", "end", 0, 3, 1, 1),
    ("pad_2", "2", "2", "\u2193", "down_arrow", 1, 3, 1, 1),
    ("pad_3", "3", "3", "PgDn", "page_down", 2, 3, 1, 1),
    ("pad_enter", "\u21a9", "keypad_enter", "\u21a9", "keypad_enter", 3, 3, 1, 2),
    ("pad_0", "0", "0", "Ins", "insert", 0, 4, 2, 1),
    ("pad_decimal", ".", ".", "Del", "delete_forward", 2, 4, 1, 1),
]


def numpad_output(name, numeric):
    row = next(row for row in NUMPAD if row[0] == name)
    key = row[2 if numeric else 4]
    if key is None:
        return None
    return keys.KEY_CODES[key], keys.NUMERIC_PAD_FLAG if key.startswith("keypad_") else 0


def resized_width(width, was_expanded, expanded):
    before = ROW_UNITS + (NUMPAD_UNITS if was_expanded else 0)
    after = ROW_UNITS + (NUMPAD_UNITS if expanded else 0)
    return (width - 5) * after / before + 5

# Use existing device-independent inputs to obtain external-keyboard semantics.
# Physical Fn -> Cmd/Ctrl; external RCtrl -> RCmd/RCtrl; Menu -> held Fn.
EVENT_KEYS = {
    "LCtrl": keys.MODIFIER_KEYS["Fn"],
    "LOpt": keys.MODIFIER_KEYS["LOpt"],
    "LCmd": keys.MODIFIER_KEYS["LCmd"],
    "RCmd": keys.MODIFIER_KEYS["RCmd"],
    "Fn": (keys.KEY_CODES["application"], 0, 0),
    "ROpt": keys.MODIFIER_KEYS["RCtrl"],
    "LShift": keys.MODIFIER_KEYS["LShift"],
    "RShift": keys.MODIFIER_KEYS["RShift"],
}
NORMAL_LABELS: dict[str, str] = {"LCtrl": "LCmd", "LOpt": "LOpt", "LCmd": "LCtrl",
                 "RCmd": "ROpt", "Fn": "Fn", "ROpt": "RCmd"}
RDP_LABELS: dict[str, str] = {**NORMAL_LABELS, "LCtrl": "LCtrl", "LOpt": "LCmd",
              "LCmd": "LOpt", "Fn": "RCmd", "ROpt": "RCtrl"}
RDP_KEYS = {name: keys.MODIFIER_KEYS[RDP_LABELS.get(name, name)] for name in EVENT_KEYS}
RDP_KEYS["Caps"] = (keys.KEY_CODES["f1"], 0, 0)
DIRECT_KEYS = {name: keys.MODIFIER_KEYS[name] for name in EVENT_KEYS}
DIRECT_LABELS = {name: name for name in NORMAL_LABELS}
MAC_SYMBOLS: dict[str, str] = {
    "escape": "\u238b", "tab": "\u21e5",
    "delete_or_backspace": "\u232b", "delete_forward": "\u2326",
    "return_or_enter": "\u21a9", "spacebar": "\u2423",
    "home": "\u2196", "end": "\u2198", "page_up": "\u21de", "page_down": "\u21df",
    "LCtrl": "\u2303", "LOpt": "\u2325", "LCmd": "\u2318",
    "RCmd": "\u2318", "ROpt": "\u2325", "LShift": "\u21e7", "RShift": "\u21e7",
}
WINDOWS_LABELS: dict[str, str] = {name: label.removeprefix("L").removeprefix("R").replace("Cmd", "Win").replace("Opt", "Alt")
                  for name, label in RDP_LABELS.items()}
WINDOWS_LABELS.update({"Caps": "Layer(F1)", "delete_forward": "Del", "spacebar": "Space"})
PALETTE = {
    "letters": (170, 222, 246), "symbols": (255, 220, 104),
    "modifiers": (89, 193, 231), "caps": (247, 139, 181),
    "arrows": (235, 167, 244), "navigation": (153, 219, 157),
    "commands": (100, 205, 124), "extended": (24, 83, 55),
}


def key_label(name: str, label: str, *, remote: bool = False, compact: bool = False) -> str:
    if name == "Caps":
        return "Layer(F1)" if remote else "Layer"
    text = label.replace("  ", " ") if compact else label
    if remote:
        return WINDOWS_LABELS.get(name, MAC_SYMBOLS.get(name, text))
    return MAC_SYMBOLS.get(name, text)


def key_color(name):
    if name == "Caps":
        group = "caps"
    elif name in EVENT_KEYS:
        group = "modifiers"
    elif name.endswith("_arrow"):
        group = "arrows"
    elif name == "input_source":
        group = "extended"
    elif name == "pad_enter":
        group = "commands"
    elif name.startswith("pad_"):
        group = "symbols"
    elif len(name) == 1 and name.isalpha():
        group = "letters"
    elif len(name) == 1 or name in ("spacebar", "non_us_backslash"):
        group = "symbols"
    elif name in ("escape", "tab", "return_or_enter", "delete_or_backspace", "delete_forward", "insert"):
        group = "commands"
    else:
        group = "navigation"
    return PALETTE[group]


def mapped_modifier_flags(held, labels):
    """Translate screen positions to final modifiers, not HID aliases."""
    flags = 0
    for name in held:
        mapped = labels.get(name, name)
        if mapped in keys.MODIFIER_KEYS:
            _, generic, side = keys.MODIFIER_KEYS[mapped]
            flags |= generic | side
    return flags


def extended_keys(remote):
    """Return the extra keys available in the current context."""
    if remote:
        return [
            ("F13", "f13", 0),
            ("Menu (Shift+F10)", "f10", keys.SHIFT_FLAG),
        ]
    return [
        ("Screenshot", "5", keys.COMMAND_FLAG | keys.SHIFT_FLAG),
        ("Menu (application key)", "application", 0),
        ("F13", "f13", 0),
    ]


def reset_window_size(panel, *, numpad=False):
    """Use the same default size at startup and on explicit reset."""
    panel.setContentSize_((resized_width(DEFAULT_SIZE[0], False, numpad), DEFAULT_SIZE[1]))
    panel.setFrame_display_(panel.constrainFrameRect_toScreen_(panel.frame(), panel.screen()), False)


def report_error(exc, *, message=None):
    traceback.print_exception(exc, file=sys.stderr)
    notify(str(exc) if message is None else message, level="error")


def keyboard_status():
    """Inspect configured fallback and its live tap only when the UI is used."""
    config = {}
    permitted = keys.can_post_events()
    if not permitted:
        return config, "Accessibility permission required", False
    try:
        config = json.loads((ROOT / "karabiner.json").read_text(encoding="utf-8"))
        if not config.get("global", {}).get("enable_cgeventtap_fallback", False):
            return config, "Fallback off: ordinary Caps Lock", permitted
        if not any(p.get("selected") and p.get("name") == "ZL" for p in config["profiles"]):
            return config, "ZL profile inactive: ordinary Caps Lock", permitted
        if not Path(CLI).is_file():
            return config, "Karabiner CLI missing: ordinary Caps Lock", permitted
        is_remote(None, config)  # Validate remote patterns before enabling layers.
        Q: Any = importlib.import_module("Quartz")
        A: Any = importlib.import_module("AppKit")
        error, taps, _ = Q.CGGetEventTapList(128, None, None)
        required = sum(1 << event for event in (10, 11, 12))
        if error:
            raise RuntimeError("Cannot inspect event taps")
        for tap in taps:
            if tap.tapPoint != keys.HID_EVENT_TAP or not tap.enabled or tap.options:
                continue
            if tap.eventsOfInterest & required != required:
                continue
            process = A.NSRunningApplication.runningApplicationWithProcessIdentifier_(tap.tappingProcess)
            url = process.executableURL() if process else None
            if url and str(url.path()).endswith("/Karabiner-Core-Service.app/Contents/MacOS/Karabiner-Core-Service"):
                return config, "", permitted
        return config, "Karabiner tap unavailable: ordinary Caps Lock", permitted
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError, re.error) as exc:
        traceback.print_exception(exc, file=sys.stderr)
        return config, "Karabiner status error: ordinary Caps Lock", permitted

# All six rows share a 16-unit grid.
ROW_UNITS = 16
ROWS: list[Sequence[tuple[str, str, float]]] = [
    [("escape", "Esc", 1)] + [(f"f{i}", f"F{i}", 1) for i in range(1, 13)]
    + [("input_source", "", 1), ("insert", "Ins", 1), ("delete_forward", "Del", 1)],
    [(char, label, 1) for char, label in zip("`1234567890-=",
      ["`  ~", "1  !", "2  @", "3  #", "4  $", "5  %", "6  ^",
       "7  &", "8  *", "9  (", "0  )", "-  _", "=  +"])]
    + [("delete_or_backspace", "Backspace", 2), ("home", "Home", 1)],
    [("tab", "Tab", 1.5)] + [(c, c.upper(), 1) for c in "qwertyuiop"]
    + [("[", "[  {", 1), ("]", "]  }", 1), ("\\", "\\  |", 1.5), ("end", "End", 1)],
    [("Caps", "Layer", 2)] + [(c, c.upper(), 1) for c in "asdfghjkl"]
    + [(";", ";  :", 1), ("'", "'  \"", 1), ("return_or_enter", "Enter", 2), ("page_up", "PgUp", 1)],
    [("LShift", "Shift", 1.5), ("non_us_backslash", "\\  |", 1)]
    + [(c, c.upper(), 1) for c in "zxcvbnm"]
    + [(",", ",  <", 1), (".", ".  >", 1), ("/", "/  ?", 1), ("RShift", "Shift", 1.5),
       ("up_arrow", "\u2191", 1), ("page_down", "PgDn", 1)],
    [("LCtrl", "Ctrl", 1.25), ("LOpt", "Opt", 1.25), ("LCmd", "Cmd", 1.25),
     ("spacebar", "Space", 5.5), ("RCmd", "Cmd", 1.25), ("Fn", "Fn", 1.25), ("ROpt", "Opt", 1.25),
     ("left_arrow", "\u2190", 1), ("down_arrow", "\u2193", 1), ("right_arrow", "\u2192", 1)],
]


def is_remote(app, config):
    """Use the same remote-window patterns as the active ZL layer rule."""
    bundle = str(app.bundleIdentifier() or "") if app else ""
    executable = str(app.executableURL().path()) if app and app.executableURL() else ""
    profile = next((p for p in config.get("profiles", []) if p.get("name") == "ZL"), {})
    rule = next((r for r in profile.get("complex_modifications", {}).get("rules", [])
                 if r.get("description") == "[Map][RDP]: [Caps] to [F1]"), {})
    return any(
        any(re.search(pattern, bundle) for pattern in condition.get("bundle_identifiers", []))
        or any(re.search(pattern, executable) for pattern in condition.get("file_paths", []))
        for m in rule.get("manipulators", []) for condition in m.get("conditions", [])
        if condition["type"] == "frontmost_application_if"
    )


def send_command(command):
    foundation: Any = importlib.import_module("Foundation")
    foundation.NSDistributedNotificationCenter.defaultCenter().postNotificationName_object_userInfo_deliverImmediately_(
        NOTIFICATION, str(os.getuid()), {"command": command}, True,
    )


def create_panel(state, *, remember_frame=True):
    A: Any = importlib.import_module("AppKit")
    F: Any = importlib.import_module("Foundation")
    Q: Any = importlib.import_module("Quartz")
    objc: Any = importlib.import_module("objc")

    class CapsKeyboardPanel(A.NSPanel):
        def canBecomeKeyWindow(self):
            return False

        def canBecomeMainWindow(self):
            return False

        def zoom_(self, sender):
            pass

        def toggleFullScreen_(self, sender):
            pass

    class CapsKeyboardButton(A.NSButton):
        @objc.python_method
        def update_appearance(self):
            name = str(self.identifier() or "")
            # AppKit may leave momentary controls ON after their action returns.
            held_key = bool(name) and name not in ("input_source", "pad_mode") and bool(self.state())
            active = held_key or (self.toggle_button and bool(self.state())) or self.pointer_down
            locked = self.locked
            hovered = self.hovered and self.isEnabled()
            appearance = (name, active, locked, hovered, bool(self.state()) if name == "pad_mode" else None)
            if appearance == self.appearance:
                return
            base = key_color(name) if name else (210, 215, 220)
            if name == "pad_mode":
                rgb = NUMPAD_MODE_COLORS["pressed" if active else "on" if self.state() else "off"]
            else:
                rgb = LOCKED_BACKGROUND if locked else tuple(
                    channel * .42 if active else channel + (255 - channel) * .35 if hovered else channel
                    for channel in base)
            color = A.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                *(channel / 255 for channel in rgb), 1 if name or active or hovered else 0)
            self.layer().setBackgroundColor_(color.CGColor())
            self.layer().setBorderWidth_(2 if active else 1 if hovered else .5 if name else 0)
            if not name:
                self.setContentTintColor_(A.NSColor.whiteColor() if active else A.NSColor.labelColor())
                self.appearance = appearance
                return
            title = self.attributedTitle().mutableCopy()
            light_text = bool(self.state()) and not active if name == "pad_mode" else active or name == "input_source"
            text_color = (A.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                *(channel / 255 for channel in LOCKED_TEXT), 1) if locked else
                A.NSColor.colorWithCalibratedWhite_alpha_(1 if light_text else .12, 1))
            title.addAttribute_value_range_(A.NSForegroundColorAttributeName, text_color, (0, title.length()))
            self.setAttributedTitle_(title)
            self.appearance = appearance

        def mouseEntered_(self, event):
            self.hovered = True
            self.update_appearance()

        def mouseExited_(self, event):
            self.hovered = False
            self.update_appearance()

        def cursorUpdate_(self, event):
            A.NSCursor.arrowCursor().set()

        def mouseDown_(self, event):
            if not self.isEnabled():
                return
            self.pointer_down = True
            self.lock_timer = None
            self.update_appearance()
            self.displayIfNeeded()
            Q.CATransaction.flush()
            try:
                objc.super(CapsKeyboardButton, self).mouseDown_(event)
            finally:
                if self.lock_timer:
                    self.lock_timer.invalidate()
                    self.lock_timer = None
                self.pointer_down = False
                name = str(self.identifier() or "")
                if (not name and not self.toggle_button) or name == "input_source":
                    self.setState_(0)
                window = self.window()
                self.hovered = bool(window and window.isVisible() and A.NSPointInRect(
                    self.convertPoint_fromView_(window.mouseLocationOutsideOfEventStream(), None), self.bounds()))
                if (name in keys.KEY_CODES and name not in EVENT_KEYS) or (name.startswith("pad_") and name != "pad_mode"):
                    self.target().release_safely(preserve_locked=True)
                elif self.identifier():
                    self.target().sync_buttons()
                else:
                    self.update_appearance()

        def acceptsFirstMouse_(self, event):
            return True

        def needsPanelToBecomeKey(self):
            return False

        def mouseDownCanMoveWindow(self):
            return False

    class CapsKeyboardController(F.NSObject):
        @objc.python_method
        def setup(self, panel):
            self.panel = panel
            self.buttons = {}
            self.legends = {}
            self.timer = None
            self.key_down = None
            self.key_down_name = None
            self.key_flags = 0
            self.key_tap = keys.SESSION_EVENT_TAP
            self.closed = False
            self.remote = False
            self.secondary_triggers = set()
            self.locked_modifiers = set()
            self.config = {}
            self.warning = ""
            self.permitted = True
            self.remapping = True
            self.runtime_warning = ""
            self.previous_input_source = None
            self.numpad_visible = False
            self.numeric_mode = True
            self.label_layout = None

        @objc.python_method
        def refresh_status(self):
            config, warning, permitted = keyboard_status()
            warning = warning or self.runtime_warning
            remapping = not warning
            if remapping != self.remapping:
                held = state.held.copy()
                labels = RDP_LABELS if self.remote else NORMAL_LABELS
                secondary = bool(self.secondary_triggers)
                was_hid = state.event_tap == keys.HID_EVENT_TAP
                self.release_safely()
                # If the HID tap disappeared while keys were held, release their
                # mapped outputs directly too. Do not release unrelated keys.
                if self.remapping and was_hid:
                    for name in reversed(held):
                        if secondary and name in ("LOpt", "LCmd", "RCmd"):
                            continue
                        mapped = labels.get(name, name)
                        if mapped in keys.MODIFIER_KEYS:
                            code, _, _ = keys.MODIFIER_KEYS[mapped]
                            keys.post_key_event(code, False, state.flags() & keys.CAPS_LOCK_FLAG,
                                                flags_changed=True)
                state.held.clear()
                state.caps = False
                state.event_keys = EVENT_KEYS if remapping else DIRECT_KEYS
                state.event_tap = keys.HID_EVENT_TAP if remapping else keys.SESSION_EVENT_TAP
            self.config, self.warning, self.permitted = config, warning, permitted
            self.remapping = remapping
            self.sync_buttons()

        @objc.python_method
        def update_context(self):
            target = A.NSWorkspace.sharedWorkspace().frontmostApplication()
            was_remote = self.remote
            self.remote = self.remapping and is_remote(target, self.config)
            if self.remote != was_remote and (state.held or state.caps or self.key_down is not None):
                self.release_safely()
            state.event_keys = RDP_KEYS if self.remote else EVENT_KEYS if self.remapping else DIRECT_KEYS
            state.event_tap = keys.HID_EVENT_TAP if self.remapping and not self.remote else keys.SESSION_EVENT_TAP
            labels = (RDP_LABELS if self.remote else NORMAL_LABELS) if self.remapping else DIRECT_LABELS
            for name, label in self.legends.items():
                label.setStringValue_(labels[name])
                label.setHidden_(self.remote)
            secondary = not self.remote and state.caps and bool(self.secondary_triggers)
            layer = "Secondary" if secondary else "Primary" if state.caps else "F1 held" if "Caps" in state.held else "Normal"
            name = str(target.localizedName()) if target else "No target"
            text = self.warning or f"{name}  /  {'RDP' if self.remote else 'macOS'}  /  {layer}"
            self.status.setStringValue_(text)
            self.status.setToolTip_(text)
            self.status.setTextColor_(A.NSColor.systemRedColor() if not self.permitted else
                                      A.NSColor.systemOrangeColor() if self.warning else
                                      A.NSColor.secondaryLabelColor())
            self.buttons["Caps"].setToolTip_(
                "Remote F1 layer" if self.remote else
                "Caps function layer" if self.remapping else "Ordinary Caps Lock")
            if self.remote != was_remote:
                self.layout()
            else:
                self.update_labels()

        @objc.python_method
        def update_labels(self):
            size = self.panel.contentView().bounds().size
            label_layout = (size.width, size.height, self.remote, self.numpad_visible, self.numeric_mode)
            if label_layout == self.label_layout:
                return
            main_width = resized_width(size.width, self.numpad_visible, False)
            compact = main_width < 640 or size.height < 260
            pad_labels = [(row[0], row[1 if self.numeric_mode else 3], row[7]) for row in NUMPAD]
            for row in [*ROWS, pad_labels]:
                for name, label, units in row:
                    if not name:
                        continue
                    text = key_label(name, label, remote=self.remote, compact=compact)
                    symbol = name in MAC_SYMBOLS and text == MAC_SYMBOLS[name]
                    points = (14 if compact else 19) if symbol else (
                        (7 if len(text) > 3 and units == 1 else 9 if len(text) > 2
                         else 10 if len(text) == 2 else 11)
                        if compact else (11 if len(text) > 3 else 13))
                    button = self.buttons[name]
                    if name.startswith("pad_") and self.numpad_visible:
                        width = (size.width - 5) / (ROW_UNITS + NUMPAD_UNITS) * units - 3
                    else:
                        width = (main_width - 5) / ROW_UNITS * units - 3
                    font = A.NSFont.systemFontOfSize_(points)
                    measured = F.NSAttributedString.alloc().initWithString_attributes_(
                        text, {A.NSFontAttributeName: font}).size().width
                    if measured > width - 4:
                        font = A.NSFont.systemFontOfSize_(points * max(1, width - 4) / measured)
                    button.setFont_(font)
                    button.setAttributedTitle_(F.NSAttributedString.alloc().initWithString_attributes_(text, {
                        A.NSFontAttributeName: font,
                        A.NSForegroundColorAttributeName: A.NSColor.colorWithCalibratedWhite_alpha_(
                            1 if name == "input_source" else .12, 1),
                    }))
                    button.appearance = None
                    button.update_appearance()
                    if name == "input_source":
                        button.setToolTip_("Switch input source")
                    elif name == "pad_mode":
                        button.setToolTip_("Local keypad mode: numbers" if self.numeric_mode else "Local keypad mode: navigation")
                    elif name != "Caps":
                        button.setToolTip_(f"{label} ({name})")
            self.label_layout = label_layout

        @objc.python_method
        def sync_buttons(self):
            for name, button in self.buttons.items():
                active = (name == "Caps" and state.caps) or name in state.held or (
                    self.key_down is not None and name == self.key_down_name)
                enabled = self.permitted and not (name == "pad_5" and not self.numeric_mode)
                selected = int(self.numeric_mode if name == "pad_mode" else active)
                if button.isEnabled() != enabled:
                    button.setEnabled_(enabled)
                if button.state() != selected:
                    button.setState_(selected)
                button.locked = name in self.locked_modifiers and name in state.held
                button.update_appearance()
            self.update_context()

        def clicked_(self, sender):
            try:
                name = str(sender.identifier())
                tracking = getattr(sender, "pointer_down", False)
                self.refresh_status()
                if not self.permitted:
                    return
                if self.key_down is not None:
                    self.release(preserve_locked=True)
                if name == "input_source":
                    self.inputSource_(sender)
                    return
                if name == "pad_mode":
                    self.release()
                    self.numeric_mode = not self.numeric_mode
                    self.sync_buttons()
                    return
                if name == "Caps" and not self.remapping:
                    self.release_safely()
                    keys.tap_caps_lock()
                    return
                if name == "Caps" or name in EVENT_KEYS:
                    # Secondary is intentionally Caps-first, matching physical keys.
                    active = state.toggle(name)
                    if not active:
                        self.locked_modifiers.discard(name)
                    elif tracking and (name in EVENT_KEYS or (name == "Caps" and self.remote)):
                        sender.lock_timer = F.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
                            MODIFIER_LOCK_DELAY, self, "lockModifier:", sender, False)
                        F.NSRunLoop.mainRunLoop().addTimer_forMode_(sender.lock_timer, F.NSRunLoopCommonModes)
                    if name in ("LOpt", "LCmd", "RCmd"):
                        if active and state.caps and not self.remote:
                            self.secondary_triggers.add(name)
                        elif not active:
                            # Karabiner clears Secondary when any trigger is released.
                            self.secondary_triggers.clear()
                    self.sync_buttons()
                    return
                flags, tap = state.flags(), state.event_tap
                if name.startswith("pad_"):
                    output = numpad_output(name, self.numeric_mode)
                    if output is None:
                        return
                    code, extra_flags = output
                    labels = (RDP_LABELS if self.remote else NORMAL_LABELS) if self.remapping else DIRECT_LABELS
                    flags = mapped_modifier_flags(state.held, labels) | extra_flags | (flags & keys.CAPS_LOCK_FLAG)
                    tap = keys.SESSION_EVENT_TAP
                else:
                    code = keys.KEY_CODES[name]
                keys.post_key_event(code, True, flags, event_tap=tap)
                self.key_down = code
                self.key_down_name = name
                self.key_flags, self.key_tap = flags, tap
                self.sync_buttons()
                if not tracking:
                    # Accessibility/programmatic clicks have no mouse-up callback.
                    self.timer = F.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                        .1, self, "releaseKey:", None, False)
                    F.NSRunLoop.mainRunLoop().addTimer_forMode_(self.timer, F.NSRunLoopCommonModes)
            except Exception as exc:
                self.release_safely()
                if self.remapping:
                    self.runtime_warning = "Karabiner input failed: ordinary Caps Lock"
                    self.refresh_status()
                report_error(exc)

        def releaseKey_(self, timer):
            self.release_safely(preserve_locked=True)

        def lockModifier_(self, timer):
            sender = timer.userInfo()
            name = str(sender.identifier())
            if getattr(sender, "pointer_down", False) and name in state.held:
                self.locked_modifiers.add(name)
                self.sync_buttons()

        @objc.python_method
        def show_extended_keys(self, sender):
            workspace = A.NSWorkspace.sharedWorkspace()
            target = workspace.frontmostApplication()
            if target is None:
                return
            pid = target.processIdentifier()
            labels = (RDP_LABELS if self.remote else NORMAL_LABELS) if self.remapping else DIRECT_LABELS
            flags = mapped_modifier_flags(state.held, labels)
            options = extended_keys(self.remote)
            self.release()
            self.extended_selection = None
            menu = A.NSMenu.alloc().initWithTitle_("Extended keys")
            for index, (title, _, _) in enumerate(options):
                item = A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "extendedSelected:", "")
                item.setTag_(index)
                item.setTarget_(self)
                menu.addItem_(item)
            menu.addItem_(A.NSMenuItem.separatorItem())
            utilities = [("Release all modifiers (Caps+`)", self.releaseAll_),
                         ("Refresh keyboard status", self.refresh_), ("Quit", self.quit_)]
            for index, (title, _) in enumerate(utilities, len(options)):
                item = A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "extendedSelected:", "")
                item.setTag_(index)
                item.setTarget_(self)
                menu.addItem_(item)
            menu.popUpMenuPositioningItem_atLocation_inView_(None, (0, -4), sender)
            # Post only after menu tracking ends, so the menu cannot consume the key.
            if self.extended_selection is None:
                return
            if self.extended_selection >= len(options):
                utilities[self.extended_selection - len(options)][1](sender)
                return
            current = workspace.frontmostApplication()
            if current is None or current.processIdentifier() != pid:
                notify("Target changed; key not sent", level="warning")
                return
            if not keys.can_post_events():
                raise RuntimeError("Accessibility permission required")
            _, name, extra_flags = options[self.extended_selection]
            keys.post_keystroke(keys.KEY_CODES[name], flags | extra_flags)

        def extendedSelected_(self, sender):
            self.extended_selection = sender.tag()

        def extended_(self, sender):
            try:
                self.refresh_status()
                self.show_extended_keys(sender)
            except Exception as exc:
                report_error(exc)

        @objc.python_method
        def release(self, *, preserve_locked=False):
            if self.timer:
                self.timer.invalidate()
                self.timer = None
            try:
                if self.key_down is not None:
                    keys.post_key_event(self.key_down, False, self.key_flags, event_tap=self.key_tap)
                    self.key_down = None
                    self.key_down_name = None
            finally:
                try:
                    keep = self.locked_modifiers.copy() if preserve_locked else set()
                    # Secondary triggers were suppressed; re-press them after Caps
                    # clears so retained locks regain their normal modifier mapping.
                    rearm = [name for name in state.held if name in keep and name in self.secondary_triggers]
                    state.release(keep=keep.difference(rearm))
                    for name in rearm:
                        state.toggle(name)
                finally:
                    if preserve_locked:
                        self.locked_modifiers.intersection_update(state.held)
                    else:
                        self.locked_modifiers.clear()
                    self.secondary_triggers.clear()
                    self.sync_buttons()

        @objc.python_method
        def release_safely(self, *, preserve_locked=False):
            try:
                self.release(preserve_locked=preserve_locked)
            except Exception as exc:
                report_error(exc)

        def reset_(self, sender):
            try:
                self.release()
                self.show_feedback("Screen keys released")
            except Exception as exc:
                report_error(exc)

        def releaseAll_(self, sender):
            try:
                self.release()
                subprocess.Popen([sys.executable, "-S", str(ROOT / "scripts/keyboard_events.py"),
                                  "--release-modifiers"])
            except Exception as exc:
                report_error(exc)

        def inputSource_(self, sender):
            try:
                self.refresh_status()
                self.release()
                if self.remote:
                    if not keys.can_post_events():
                        raise RuntimeError("Accessibility permission required")
                    # Match physical Caps -> F1 in the RDP rule, without re-entering HID.
                    keys.post_keystroke(keys.KEY_CODES["f1"])
                else:
                    self.previous_input_source = switch_input_source(self.previous_input_source)
            except Exception as exc:
                report_error(exc)

        def refresh_(self, sender):
            try:
                self.runtime_warning = ""
                self.refresh_status()
                self.show_feedback(self.warning or "Karabiner layers available",
                                   level="error" if not self.permitted else "warning" if self.warning else "info")
            except Exception as exc:
                report_error(exc)

        @objc.python_method
        def show_feedback(self, text, *, level="info"):
            notify(text, level=level)

        def mouseEntered_(self, event):
            self.refresh_status()

        def cursorUpdate_(self, event):
            A.NSCursor.arrowCursor().set()

        def mouseExited_(self, event):
            # Entered-and-exited tracking requires both Objective-C selectors.
            pass

        def minimize_(self, sender):
            self.panel.miniaturize_(None)
            if self.panel.isMiniaturized():
                self.show_feedback("Keyboard minimized")

        def resetSize_(self, sender):
            try:
                reset_window_size(self.panel, numpad=self.numpad_visible)
                self.show_feedback("Window size reset")
            except Exception as exc:
                report_error(exc)

        def quit_(self, sender):
            self.panel.performClose_(None)

        def numpad_(self, sender):
            self.release_safely()
            size = self.panel.contentView().bounds().size
            expanded = not self.numpad_visible
            width = resized_width(size.width, self.numpad_visible, expanded)
            self.numpad_visible = expanded
            self.panel.setContentMinSize_((resized_width(MINIMUM_SIZE[0], False, expanded), MINIMUM_SIZE[1]))
            self.panel.setContentSize_((round(width), size.height))
            self.panel.setFrame_display_(self.panel.constrainFrameRect_toScreen_(self.panel.frame(), self.panel.screen()), False)
            button = self.toolbar["numpad:"]
            button.setState_(int(expanded))
            button.setToolTip_("Hide numeric keypad" if expanded else "Show numeric keypad")
            button.update_appearance()
            self.layout()

        def contextChanged_(self, notification):
            # Never carry sticky modifiers into a different target application.
            self.release_safely()
            self.refresh_status()

        def command_(self, notification):
            command = (notification.userInfo() or {}).get("command")
            if command == "quit":
                self.panel.performClose_(None)
            elif command == "show":
                self.refresh_status()
                self.show_near_pointer()

        @objc.python_method
        def show_near_pointer(self):
            if self.panel.isMiniaturized():
                self.panel.deminiaturize_(None)
            mouse = A.NSEvent.mouseLocation()
            screen = next((screen for screen in A.NSScreen.screens()
                           if A.NSPointInRect(mouse, screen.frame())), A.NSScreen.mainScreen())
            size = self.panel.frame().size
            frame = panel_frame_near_pointer(mouse, screen.visibleFrame(), size.width, size.height)
            self.panel.setFrame_display_(frame, True)
            self.panel.orderFrontRegardless()

        def windowWillMiniaturize_(self, notification):
            self.release_safely()

        def windowDidResize_(self, notification):
            self.layout()

        def windowShouldZoom_toFrame_(self, window, frame):
            return False

        def windowDidMove_(self, notification):
            if remember_frame:
                self.panel.saveFrameUsingName_("CapsKeyboard.v1")

        def windowWillClose_(self, notification):
            if remember_frame:
                self.panel.saveFrameUsingName_("CapsKeyboard.v1")
            self.release_safely()
            self.closed = True
            app.postEvent_atStart_(A.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                A.NSEventTypeApplicationDefined, (0, 0), 0, 0, 0, None, 0, 0, 0), False)

        @objc.python_method
        def layout(self):
            size = self.panel.contentView().bounds().size
            compact = resized_width(size.width, self.numpad_visible, False) < 640 or size.height < 260
            margin, gap, header = 4, 3, 22
            footer = 14 if compact else 16
            self.update_labels()
            for label in self.legends.values():
                label.setFont_(A.NSFont.systemFontOfSize_(9 if compact else 11))
            self.status.setFont_(A.NSFont.systemFontOfSize_(10 if compact else 12))
            total_units = ROW_UNITS + (NUMPAD_UNITS if self.numpad_visible else 0)
            unit = (size.width - 2 * margin + gap) / total_units
            row_height = (size.height - footer - header - margin) / 6
            for row_index, row in enumerate(ROWS):
                x = margin
                y = size.height - header - (row_index + 1) * row_height
                for name, _, units in row:
                    width = units * unit - gap
                    if name:
                        self.buttons[name].setFrame_(((x, y), (width, row_height - gap)))
                        if name in self.legends:
                            self.legends[name].setFrame_(((x, margin - 2), (width, max(0, footer - 1))))
                    x += units * unit
            numpad_row_height = row_height * len(ROWS) / 5
            for name, _, _, _, _, column, row, width, height in NUMPAD:
                button = self.buttons[name]
                button.setHidden_(not self.numpad_visible)
                if self.numpad_visible:
                    x = margin + (ROW_UNITS + column) * unit
                    y = size.height - header - (row + height) * numpad_row_height
                    button.setFrame_(((x, y), (width * unit - gap, height * numpad_row_height - gap)))
            toolbar_width = len(self.toolbar) * 26
            self.status.setFrame_(((margin, size.height - header + 2),
                                   (size.width - 2 * margin - toolbar_width - 4, 18)))
            for index, button in enumerate(self.toolbar.values()):
                button.setFrame_(((size.width - margin - toolbar_width + index * 26,
                                   size.height - header + 2), (24, 18)))

    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyAccessory)
    screen = A.NSScreen.mainScreen().visibleFrame()
    width, height = min(DEFAULT_SIZE[0], screen.size.width - 24), min(DEFAULT_SIZE[1], screen.size.height - 60)
    panel = CapsKeyboardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        ((screen.origin.x + (screen.size.width - width) / 2, screen.origin.y + 35), (width, height)),
        A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable | A.NSWindowStyleMaskResizable
        | A.NSWindowStyleMaskMiniaturizable
        | A.NSWindowStyleMaskNonactivatingPanel, A.NSBackingStoreBuffered, False)
    panel.setTitle_("Caps Keyboard")
    panel.setContentMinSize_(MINIMUM_SIZE)
    panel.setRestorable_(False)
    panel.standardWindowButton_(A.NSWindowZoomButton).setEnabled_(False)
    panel.setReleasedWhenClosed_(False)
    panel.setHidesOnDeactivate_(False)
    panel.setBecomesKeyOnlyIfNeeded_(True)
    panel.setMovableByWindowBackground_(True)
    panel.setLevel_(A.NSFloatingWindowLevel)
    panel.setCollectionBehavior_(A.NSWindowCollectionBehaviorCanJoinAllSpaces
                                 | A.NSWindowCollectionBehaviorFullScreenAuxiliary
                                 | A.NSWindowCollectionBehaviorIgnoresCycle)
    if remember_frame:
        panel.setFrameUsingName_("CapsKeyboard.v1")
    reset_window_size(panel)
    controller = CapsKeyboardController.alloc().init()
    controller.setup(panel)
    panel.setDelegate_(controller)
    content = panel.contentView()
    content.setWantsLayer_(True)
    content.layer().setBackgroundColor_(A.NSColor.windowBackgroundColor().CGColor())
    for row in ROWS:
        for name, label, _ in row:
            if name:
                controller.buttons[name] = (label, name)
    for name, label, *_ in NUMPAD:
        controller.buttons[name] = (label, name)
    for name, (label, _) in list(controller.buttons.items()):
        button = CapsKeyboardButton.alloc().initWithFrame_(((0, 0), (40, 40)))
        button.setIdentifier_(name)
        button.setTitle_(label)
        if name == "input_source":
            button.setImage_(A.NSImage.imageWithSystemSymbolName_accessibilityDescription_("globe", "Switch input source"))
            button.setImagePosition_(A.NSImageOnly)
            button.setContentTintColor_(A.NSColor.whiteColor())
        button.setFont_(A.NSFont.systemFontOfSize_(11 if len(label) > 3 else 13))
        button.setAlignment_(A.NSTextAlignmentCenter)
        button.cell().setWraps_(False)
        button.cell().setUsesSingleLineMode_(True)
        button.cell().setLineBreakMode_(A.NSLineBreakByClipping)
        button.setBordered_(False)
        button.setWantsLayer_(True)
        button.layer().setCornerRadius_(5)
        button.layer().setBorderWidth_(.5)
        button.layer().setBorderColor_(A.NSColor.separatorColor().CGColor())
        button.setButtonType_(A.NSButtonTypeMomentaryPushIn)
        button.cell().setHighlightsBy_(A.NSNoCellMask)
        button.cell().setShowsStateBy_(A.NSNoCellMask)
        if name in EVENT_KEYS or name == "Caps":
            button.sendActionOn_(A.NSEventMaskLeftMouseDown)
        if (name in keys.KEY_CODES and name not in EVENT_KEYS) or (name.startswith("pad_") and name != "pad_mode"):
            button.sendActionOn_(A.NSEventMaskLeftMouseDown)
        button.setRefusesFirstResponder_(True)
        button.setToolTip_("Caps function layer" if name == "Caps" else name)
        button.setTarget_(controller)
        button.setAction_("clicked:")
        content.addSubview_(button)
        controller.buttons[name] = button
    for name in NORMAL_LABELS:
        label = A.NSTextField.labelWithString_(NORMAL_LABELS[name])
        label.setAlignment_(A.NSTextAlignmentCenter)
        label.setFont_(A.NSFont.systemFontOfSize_(11))
        label.setTextColor_(A.NSColor.secondaryLabelColor())
        content.addSubview_(label)
        controller.legends[name] = label
    controller.status = A.NSTextField.labelWithString_("")
    controller.status.setFont_(A.NSFont.systemFontOfSize_(12))
    controller.status.setTextColor_(A.NSColor.secondaryLabelColor())
    controller.status.setLineBreakMode_(A.NSLineBreakByTruncatingTail)
    content.addSubview_(controller.status)
    controller.toolbar = {}
    for action, symbol, title in [("minimize:", "minus", "Minimize"),
                                   ("extended:", "ellipsis", "Extended keys and actions"),
                                   ("numpad:", "number.square", "Show numeric keypad"),
                                   ("reset:", "xmark.circle", "Release screen keys"),
                                   ("resetSize:", "arrow.counterclockwise", "Reset window size")]:
        button = CapsKeyboardButton.alloc().initWithFrame_(((0, 0), (24, 18)))
        button.setImage_(A.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, title))
        button.setButtonType_(A.NSButtonTypeMomentaryPushIn)
        button.cell().setHighlightsBy_(A.NSNoCellMask)
        button.cell().setShowsStateBy_(A.NSNoCellMask)
        button.setBordered_(False)
        button.setRefusesFirstResponder_(True)
        button.setToolTip_(title)
        button.setTarget_(controller)
        button.setAction_(action)
        button.setWantsLayer_(True)
        button.layer().setCornerRadius_(4)
        button.layer().setBorderColor_(A.NSColor.separatorColor().CGColor())
        content.addSubview_(button)
        controller.toolbar[action] = button
    for button in (*controller.buttons.values(), *controller.toolbar.values()):
        # Missing Python attributes trigger expensive PyObjC selector lookups.
        button.pointer_down = False
        button.hovered = False
        button.locked = False
        button.appearance = None
        button.toggle_button = str(button.action()) == "numpad:"
        if button.toggle_button:
            button.setButtonType_(A.NSButtonTypePushOnPushOff)
        button.layer().setActions_({name: F.NSNull.null() for name in ("backgroundColor", "borderWidth")})
        tracking = A.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            button.bounds(), A.NSTrackingMouseEnteredAndExited | A.NSTrackingActiveAlways
            | A.NSTrackingInVisibleRect | A.NSTrackingCursorUpdate, button, None)
        button.addTrackingArea_(tracking)
    tracking = A.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
        content.bounds(), A.NSTrackingMouseEnteredAndExited | A.NSTrackingActiveAlways
        | A.NSTrackingInVisibleRect | A.NSTrackingCursorUpdate, controller, None)
    content.addTrackingArea_(tracking)
    A.NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
        controller, "contextChanged:", A.NSWorkspaceDidActivateApplicationNotification, None)
    F.NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
        controller, "command:", NOTIFICATION, str(os.getuid()))
    controller.layout()
    controller.refresh_status()
    return app, panel, controller


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--quit", action="store_true")
    args = parser.parse_args()
    try:
        if args.quit:
            send_command("quit")
            return 0
        if args.check:
            _, warning, permitted = keyboard_status()
            print(warning or "Karabiner layers available.")
            return 0 if permitted else 1
        (ROOT / "tmp").mkdir(exist_ok=True)
        # Shared with the old test panel: two panels must not own the same Caps state.
        with (ROOT / "tmp" / "test_keyboard.lock").open("a", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                send_command("show")
                return 0
            keys.request_post_events()
            state = KeyboardState(EVENT_KEYS)
            app, panel, controller = create_panel(state)
            try:
                controller.show_near_pointer()
                run_panel(app, controller)
            finally:
                controller.release_safely()
                panel.orderOut_(None)
        return 0
    except Exception as exc:
        if args.check:
            traceback.print_exception(exc, file=sys.stderr)
        else:
            message = str(exc)
            if os.environ.get("CAPS_KEYBOARD_APP") and "Accessibility permission" in message:
                message = "Allow Caps Keyboard in System Settings > Privacy & Security > Accessibility, then reopen."
            report_error(exc, message=message)
        return 1


if __name__ == "__main__":
    sys.exit(main())
