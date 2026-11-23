"""macOS window discovery, non-activating outlines and a Tk drag-to-pick control."""

from dataclasses import dataclass
import os
import psutil

import front_window_info as info
import center_front_window as geometry
from process_actions import ProcessTarget
from tooltip import _panel_class


@dataclass
class WindowTarget:
    app: object
    window: object
    process: ProcessTarget
    title: str

    @classmethod
    def capture(cls, app, window):
        return cls(app, window, ProcessTarget(int(app.processIdentifier())),
                   str(info._ax_attr(window, "AXTitle") or "（无标题）"))

    @property
    def label(self):
        return f"PID:{self.process.pid}, {self.app.localizedName()} — {self.title}"

    def matches(self, other):
        return (other is not None and self.process.pid == other.process.pid
                and self.process.created == other.process.created
                and self.window == other.window)

    def checked(self):
        self.process.checked()
        error, pid = info.AS.AXUIElementGetPid(self.window, None)
        role_error, role = info._ax_copy(self.window, "AXRole")
        if error or role_error or pid != self.process.pid or role != "AXWindow":
            raise RuntimeError("原窗口已关闭，请重新选择。")
        return self.window


def list_windows(include_hidden=False):
    """Enumerate AX windows on demand; skip this inspector and inaccessible apps."""
    targets = []
    for app in info.AppKit.NSWorkspace.sharedWorkspace().runningApplications():
        pid = int(app.processIdentifier())
        if pid == os.getpid() or app.isTerminated() or (app.isHidden() and not include_hidden):
            continue
        app_ref = info.AS.AXUIElementCreateApplication(pid)
        info.AS.AXUIElementSetMessagingTimeout(app_ref, .2)
        for window in info.accessible_windows(app_ref):
            if not include_hidden and info._ax_attr(window, "AXMinimized", False):
                continue
            try:
                targets.append(WindowTarget.capture(app, window))
            except (psutil.Error, RuntimeError):
                continue
    return targets


def window_at_pointer():
    """Hit-test the actual AX element, then use its owning window (not a guessed title)."""
    mouse = info.AppKit.NSEvent.mouseLocation()
    primary_top = info.AppKit.NSScreen.screens()[0].frame().size.height
    system = info.AS.AXUIElementCreateSystemWide()
    info.AS.AXUIElementSetMessagingTimeout(system, .2)
    error, element = info.AS.AXUIElementCopyElementAtPosition(system, mouse.x, primary_top - mouse.y, None)
    if error or element is None:
        return None
    error, pid = info.AS.AXUIElementGetPid(element, None)
    if error or pid == os.getpid():
        return None
    window = element if info._ax_attr(element, "AXRole") == "AXWindow" else info._ax_attr(element, "AXWindow", None)
    app = info._running_app_for_pid(pid)
    if window is None or app is None:
        return None
    return WindowTarget.capture(app, window)


def outline_rectangles(x, y, width, height, thickness=4):
    """Four inset edges in logical points; keeps small windows inside their bounds."""
    dx, dy = min(thickness, width), min(thickness, height)
    return [((x, y), (width, dy)), ((x, y + height - dy), (width, dy)),
            ((x, y), (dx, height)), ((x + width - dx, y), (dx, height))]


class WindowHighlight:
    def __init__(self, root):
        self.root = root
        self.edges = []
        self.timer = None

    def show(self, target, duration_ms=None):
        self.hide()
        window = target.checked()
        if target.app.isHidden() or info._ax_attr(window, "AXMinimized", False):
            raise RuntimeError("窗口已隐藏或最小化，请先激活窗口。")
        position, size = geometry._window_position(window), geometry._window_size(window)
        if size.width <= 0 or size.height <= 0:
            raise RuntimeError("无法读取窗口边界。")
        A = info.AppKit
        primary_top = A.NSScreen.screens()[0].frame().size.height
        frames = outline_rectangles(position.x, primary_top - position.y - size.height, size.width, size.height)
        try:
            for frame in frames:
                edge = _panel_class().alloc().initWithContentRect_styleMask_backing_defer_(
                    frame, A.NSWindowStyleMaskBorderless | A.NSWindowStyleMaskNonactivatingPanel,
                    A.NSBackingStoreBuffered, False)
                edge.setReleasedWhenClosed_(False)
                self.edges.append(edge)
                edge.setHidesOnDeactivate_(False)
                edge.setIgnoresMouseEvents_(True)
                edge.setHasShadow_(False)
                edge.setLevel_(A.NSStatusWindowLevel)
                # Keep the outline in the current Space; it must not follow unrelated desktops.
                edge.setCollectionBehavior_(A.NSWindowCollectionBehaviorFullScreenAuxiliary
                                            | A.NSWindowCollectionBehaviorIgnoresCycle)
                edge.setBackgroundColor_(A.NSColor.colorWithSRGBRed_green_blue_alpha_(1, .267, .133, 1))
                edge.orderFrontRegardless()
            if duration_ms is not None:
                self.timer = self.root.after(duration_ms, self.hide)
        except Exception:
            self.hide()
            raise

    def hide(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        for edge in self.edges:
            edge.orderOut_(None)
            edge.close()
        self.edges.clear()


class WindowPicker:
    HINT = "将此小圆饼拖动到目标窗口，即可查看窗口信息"

    def __init__(self, root, control, border, selected, status, enabled):
        self.root, self.control, self.border = root, control, border
        self.selected, self.status, self.enabled = selected, status, enabled
        self.dragging = False
        self.target = None
        control.bind("<ButtonPress-1>", self.start)
        root.bind("<B1-Motion>", self.motion, add="+")
        root.bind("<ButtonRelease-1>", self.release, add="+")
        root.bind("<Unmap>", self.unmap, add="+")

    def start(self, event=None):
        if not self.enabled():
            return "break"
        self.cancel()
        self.root.configure(cursor="crosshair")
        try:
            self.control.grab_set_global()
        except Exception as exc:
            self.root.configure(cursor="")
            self.status(f"无法开始选窗：{exc}")
            return "break"
        self.dragging = True
        self.status("拖动到目标窗口后松开；Esc 取消")
        return "break"

    def update(self):
        target = window_at_pointer()
        if target is not None and target.matches(self.target):
            return
        self.target = target
        if target is None:
            self.border.hide()
        else:
            self.border.show(target)
            self.status(f"目标：{target.label}；松开读取窗口信息")

    def motion(self, event=None):
        if self.dragging:
            if self.control.grab_current() != self.control:
                self.cancel()
                return "break"
            try:
                self.update()
            except Exception as exc:
                self.cancel()
                self.status(str(exc))
            return "break"

    def release(self, event=None):
        if not self.dragging:
            return
        target = None
        try:
            self.update()
            target = self.target
        except Exception as exc:
            self.status(str(exc))
        finally:
            self.cancel()
        if target is not None:
            self.selected(target)
        return "break"

    def unmap(self, event):
        if event.widget == self.root and self.dragging:
            self.cancel()

    def cancel(self):
        if self.dragging:
            if self.control.grab_current() == self.control:
                self.control.grab_release()
            self.root.configure(cursor="")
        self.dragging = False
        self.target = None
        self.border.hide()
