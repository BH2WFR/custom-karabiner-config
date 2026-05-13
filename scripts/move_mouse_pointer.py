#!/usr/bin/env python3
import argparse
import importlib
import sys
from typing import Any

CoreGraphics: Any = importlib.import_module("Quartz.CoreGraphics")

CGAssociateMouseAndMouseCursorPosition = CoreGraphics.CGAssociateMouseAndMouseCursorPosition
CGEventCreate = CoreGraphics.CGEventCreate
CGEventCreateMouseEvent = CoreGraphics.CGEventCreateMouseEvent
CGEventGetLocation = CoreGraphics.CGEventGetLocation
CGEventPost = CoreGraphics.CGEventPost
CGEventSetIntegerValueField = CoreGraphics.CGEventSetIntegerValueField
CGDisplayBounds = CoreGraphics.CGDisplayBounds
CGDisplayPixelsHigh = CoreGraphics.CGDisplayPixelsHigh
CGDisplayPixelsWide = CoreGraphics.CGDisplayPixelsWide
CGGetActiveDisplayList = CoreGraphics.CGGetActiveDisplayList
CGWarpMouseCursorPosition = CoreGraphics.CGWarpMouseCursorPosition
kCGEventLeftMouseDown = CoreGraphics.kCGEventLeftMouseDown
kCGEventLeftMouseUp = CoreGraphics.kCGEventLeftMouseUp
kCGEventOtherMouseDown = CoreGraphics.kCGEventOtherMouseDown
kCGEventOtherMouseUp = CoreGraphics.kCGEventOtherMouseUp
kCGEventRightMouseDown = CoreGraphics.kCGEventRightMouseDown
kCGEventRightMouseUp = CoreGraphics.kCGEventRightMouseUp
kCGHIDEventTap = CoreGraphics.kCGHIDEventTap
kCGMouseButtonCenter = CoreGraphics.kCGMouseButtonCenter
kCGMouseButtonLeft = CoreGraphics.kCGMouseButtonLeft
kCGMouseButtonRight = CoreGraphics.kCGMouseButtonRight
kCGMouseEventButtonNumber = CoreGraphics.kCGMouseEventButtonNumber

"""
move_mouse_pointer.py --left 1
move_mouse_pointer.py --right 1
move_mouse_pointer.py --up 1
move_mouse_pointer.py --down 1

move_mouse_pointer.py --left 10
move_mouse_pointer.py --right 10
move_mouse_pointer.py --up 10
move_mouse_pointer.py --down 10

默认按逻辑像素移动；加 --actual-pixels 后按实际像素移动
move_mouse_pointer.py --actual-pixels --down 10

鼠标点击
move_mouse_pointer.py --key_click button1
move_mouse_pointer.py --key_click button2
(button1: 左键, button2: 右键, button3: 中键, button4: 前进键, button5: 后退键)


move_mouse_pointer.py --key_down button1
move_mouse_pointer.py --key_up button1
"""


BUTTONS = {
    "button1": {
        "number": kCGMouseButtonLeft,
        "down": kCGEventLeftMouseDown,
        "up": kCGEventLeftMouseUp,
    },
    "button2": {
        "number": kCGMouseButtonRight,
        "down": kCGEventRightMouseDown,
        "up": kCGEventRightMouseUp,
    },
    "button3": {
        "number": kCGMouseButtonCenter,
        "down": kCGEventOtherMouseDown,
        "up": kCGEventOtherMouseUp,
    },
    "button4": {
        "number": 3,
        "down": kCGEventOtherMouseDown,
        "up": kCGEventOtherMouseUp,
    },
    "button5": {
        "number": 4,
        "down": kCGEventOtherMouseDown,
        "up": kCGEventOtherMouseUp,
    },
}


def current_position():
    event = CGEventCreate(None)
    location = CGEventGetLocation(event)
    return location.x, location.y


def point_in_rect(x, y, rect):
    return (
        rect.origin.x <= x < rect.origin.x + rect.size.width
        and rect.origin.y <= y < rect.origin.y + rect.size.height
    )


def current_display_scale(x, y):
    _error, displays, _count = CGGetActiveDisplayList(32, None, None)
    for display in displays:
        bounds = CGDisplayBounds(display)
        if not point_in_rect(x, y, bounds):
            continue

        scale_x = CGDisplayPixelsWide(display) / bounds.size.width
        scale_y = CGDisplayPixelsHigh(display) / bounds.size.height
        return scale_x or 1, scale_y or 1

    return 1, 1


def current_display_geometry(x, y):
    _error, displays, _count = CGGetActiveDisplayList(32, None, None)
    for display in displays:
        bounds = CGDisplayBounds(display)
        if not point_in_rect(x, y, bounds):
            continue

        scale_x = CGDisplayPixelsWide(display) / bounds.size.width
        scale_y = CGDisplayPixelsHigh(display) / bounds.size.height
        return bounds, scale_x or 1, scale_y or 1

    return None, 1, 1


def post_mouse_event(event_type, x, y, button):
    event = CGEventCreateMouseEvent(
        None,
        event_type,
        (x, y),
        button["number"],
    )

    if event_type in (kCGEventOtherMouseDown, kCGEventOtherMouseUp):
        CGEventSetIntegerValueField(
            event,
            kCGMouseEventButtonNumber,
            button["number"],
        )

    CGEventPost(kCGHIDEventTap, event)


def move_pointer(dx, dy, *, actual_pixels=False):
    x, y = current_position()
    if actual_pixels:
        bounds, scale_x, scale_y = current_display_geometry(x, y)
        if bounds is not None:
            pixel_x = round((x - bounds.origin.x) * scale_x)
            pixel_y = round((y - bounds.origin.y) * scale_y)
            x = bounds.origin.x + (pixel_x + dx) / scale_x
            y = bounds.origin.y + (pixel_y + dy) / scale_y
            CGWarpMouseCursorPosition((x, y))
            CGAssociateMouseAndMouseCursorPosition(True)
            return

        dx /= scale_x
        dy /= scale_y

    CGWarpMouseCursorPosition((x + dx, y + dy))
    CGAssociateMouseAndMouseCursorPosition(True)


def click_button(button_name):
    button = BUTTONS[button_name]
    x, y = current_position()
    post_mouse_event(button["down"], x, y, button)
    post_mouse_event(button["up"], x, y, button)


def button_down(button_name):
    button = BUTTONS[button_name]
    x, y = current_position()
    post_mouse_event(button["down"], x, y, button)


def button_up(button_name):
    button = BUTTONS[button_name]
    x, y = current_position()
    post_mouse_event(button["up"], x, y, button)


def parse_args():
    parser = argparse.ArgumentParser()
    direction_group = parser.add_mutually_exclusive_group()
    direction_group.add_argument("--left", type=int)
    direction_group.add_argument("--right", type=int)
    direction_group.add_argument("--up", type=int)
    direction_group.add_argument("--down", type=int)
    parser.add_argument("--actual-pixels", action="store_true")

    button_group = parser.add_mutually_exclusive_group()
    button_group.add_argument("--key_click", choices=BUTTONS.keys())
    button_group.add_argument("--key_down", choices=BUTTONS.keys())
    button_group.add_argument("--key_up", choices=BUTTONS.keys())
    return parser.parse_args()


def main():
    args = parse_args()
    actions = [
        args.left is not None,
        args.right is not None,
        args.up is not None,
        args.down is not None,
        args.key_click is not None,
        args.key_down is not None,
        args.key_up is not None,
    ]
    if sum(actions) != 1:
        print("Specify exactly one action.", file=sys.stderr)
        return 2

    if args.left is not None:
        move_pointer(-args.left, 0, actual_pixels=args.actual_pixels)
    elif args.right is not None:
        move_pointer(args.right, 0, actual_pixels=args.actual_pixels)
    elif args.up is not None:
        move_pointer(0, -args.up, actual_pixels=args.actual_pixels)
    elif args.down is not None:
        move_pointer(0, args.down, actual_pixels=args.actual_pixels)
    elif args.key_click is not None:
        click_button(args.key_click)
    elif args.key_down is not None:
        button_down(args.key_down)
    elif args.key_up is not None:
        button_up(args.key_up)

    return 0


if __name__ == "__main__":
    sys.exit(main())
