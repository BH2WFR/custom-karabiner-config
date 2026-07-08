#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportMissingModuleSource=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Print frontmost application and focused window information."""

import importlib
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any

AS: Any = importlib.import_module("ApplicationServices")
AppKit: Any = importlib.import_module("AppKit")

FGray = "\033[90m"
FLRed = "\033[91m"
FLGreen = "\033[92m"
FLYellow = "\033[93m"
FLBlue = "\033[94m"
FLMagenta = "\033[95m"
FLCyan = "\033[96m"
CRst = "\033[0m"


def _ax_copy(element: Any, attribute: str) -> tuple[int, Any]:
    error, value = AS.AXUIElementCopyAttributeValue(element, attribute, None)
    return error, value


def _ax_value(value: Any, value_type: int) -> Any:
    ok, result = AS.AXValueGetValue(value, value_type, None)
    return result if ok else None


def _ax_attr(element: Any, attribute: str, default: Any = "") -> Any:
    error, value = _ax_copy(element, attribute)
    return value if error == AS.kAXErrorSuccess else default


def _ax_point(element: Any, attribute: str) -> str:
    value = _ax_attr(element, attribute, None)
    point = _ax_value(value, AS.kAXValueCGPointType) if value is not None else None
    if point is None:
        return ""
    return f"({point.x:.0f}, {point.y:.0f})"


def _ax_size(element: Any, attribute: str) -> str:
    value = _ax_attr(element, attribute, None)
    size = _ax_value(value, AS.kAXValueCGSizeType) if value is not None else None
    if size is None:
        return ""
    return f"{size.width:.0f} x {size.height:.0f}"


def _url_path(url: Any) -> str:
    if url is None:
        return ""
    path = url.path()
    return str(path) if path is not None else ""


def _run_text(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _ps_field(pid: int, field: str) -> str:
    return _run_text(["/bin/ps", "-p", str(pid), "-o", f"{field}="])


def _file_type(path: str) -> str:
    if not path:
        return ""
    return _run_text(["/usr/bin/file", "-b", path])


def _bundle_info(bundle_path: str) -> dict[str, Any]:
    info_path = Path(bundle_path) / "Contents" / "Info.plist"
    if not info_path.exists():
        return {}
    try:
        with info_path.open("rb") as f:
            return plistlib.load(f)
    except (OSError, plistlib.InvalidFileException):
        return {}


def _print_section(title: str) -> None:
    print(f"\n{FLYellow}== {title} =={CRst}")


def _print_kv(label: str, value: Any) -> None:
    if value is None:
        value = ""
    if isinstance(value, bool):
        value = "Yes" if value else "No"
    print(f"{FLCyan}{label:<22}{CRst} {value}")


def _focused_window(app_ref: Any) -> Any:
    error, window = _ax_copy(app_ref, AS.kAXFocusedWindowAttribute)
    if error == AS.kAXErrorSuccess:
        return window

    windows = _ax_attr(app_ref, AS.kAXWindowsAttribute, [])
    if windows:
        return windows[0]
    return None


def _running_app_for_pid(pid: int) -> Any:
    apps = AppKit.NSWorkspace.sharedWorkspace().runningApplications()
    for app in apps:
        if int(app.processIdentifier()) == pid:
            return app
    return None


def _frontmost_app() -> Any:
    return AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()


def _target_app() -> Any:
    if "--pid" not in sys.argv:
        return _frontmost_app()

    idx = sys.argv.index("--pid")
    try:
        pid = int(sys.argv[idx + 1])
    except (IndexError, ValueError):
        print(f"{FLRed}Invalid --pid argument.{CRst}", file=sys.stderr)
        return None

    app = _running_app_for_pid(pid)
    if app is None:
        print(f"{FLRed}No running application found for PID {pid}.{CRst}", file=sys.stderr)
    return app


def _child_summary(window: Any, limit: int = 30) -> list[tuple[int, str, str, str]]:
    children = _ax_attr(window, AS.kAXChildrenAttribute, [])
    rows = []
    for idx, child in enumerate(children[:limit], start=1):
        rows.append((
            idx,
            str(_ax_attr(child, AS.kAXRoleAttribute, "")),
            str(_ax_attr(child, AS.kAXSubroleAttribute, "")),
            str(_ax_attr(child, AS.kAXTitleAttribute, "")),
        ))
    return rows


def _print_child_summary(window: Any) -> None:
    rows = _child_summary(window)
    if not rows:
        _print_kv("AX children", "")
        return

    print(f"{FLCyan}{'#':>3}  {'Role':<18} {'Subrole':<24} Title{CRst}")
    for idx, role, subrole, title in rows:
        if len(title) > 70:
            title = title[:69] + "..."
        print(f"{FLGreen}{idx:>3}{CRst}  {role:<18} {subrole:<24} {title}")


def main() -> int:
    app = _target_app()
    if app is None:
        print(f"{FLRed}No target application.{CRst}", file=sys.stderr)
        return 1

    pid = int(app.processIdentifier())
    app_ref = AS.AXUIElementCreateApplication(pid)
    window = _focused_window(app_ref)

    bundle_path = _url_path(app.bundleURL())
    executable_path = _url_path(app.executableURL())
    info = _bundle_info(bundle_path)

    print(f"{FLYellow}=========== FRONT WINDOW INFO ==========={CRst}")

    _print_section("Application")
    _print_kv("Name", app.localizedName())
    _print_kv("Bundle ID", app.bundleIdentifier())
    _print_kv("PID", pid)
    _print_kv("Parent PID", _ps_field(pid, "ppid"))
    _print_kv("User", _ps_field(pid, "user"))
    _print_kv("Executable", executable_path)
    _print_kv("Bundle path", bundle_path)
    _print_kv("Command", _ps_field(pid, "command"))
    _print_kv("Started", _ps_field(pid, "lstart"))
    _print_kv("CPU time", _ps_field(pid, "time"))
    _print_kv("RSS / VSZ", f"{_ps_field(pid, 'rss')} KB / {_ps_field(pid, 'vsz')} KB")
    _print_kv("Binary type", _file_type(executable_path))

    _print_section("Bundle")
    _print_kv("Display name", info.get("CFBundleDisplayName", ""))
    _print_kv("Name", info.get("CFBundleName", ""))
    _print_kv("Identifier", info.get("CFBundleIdentifier", ""))
    _print_kv("Short version", info.get("CFBundleShortVersionString", ""))
    _print_kv("Bundle version", info.get("CFBundleVersion", ""))
    _print_kv("Package type", info.get("CFBundlePackageType", ""))
    _print_kv("Minimum system", info.get("LSMinimumSystemVersion", ""))

    _print_section("Focused Window")
    if window is None:
        print(f"{FLRed}No focused window exposed through Accessibility.{CRst}")
    else:
        windows = _ax_attr(app_ref, AS.kAXWindowsAttribute, [])
        _print_kv("Window count", len(windows) if windows else 0)
        _print_kv("Title", _ax_attr(window, AS.kAXTitleAttribute, ""))
        _print_kv("Role", _ax_attr(window, AS.kAXRoleAttribute, ""))
        _print_kv("Subrole", _ax_attr(window, AS.kAXSubroleAttribute, ""))
        _print_kv("Position", _ax_point(window, AS.kAXPositionAttribute))
        _print_kv("Size", _ax_size(window, AS.kAXSizeAttribute))
        _print_kv("Minimized", _ax_attr(window, AS.kAXMinimizedAttribute, ""))
        _print_kv("Fullscreen", _ax_attr(window, "AXFullScreen", ""))
        _print_kv("Modal", _ax_attr(window, "AXModal", ""))

        _print_section("Focused Window Children")
        _print_child_summary(window)

    if "--pause" in sys.argv:
        try:
            input(f"{FGray}Press Enter to exit...{CRst}")
        except (EOFError, KeyboardInterrupt):
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
