#!/usr/bin/env python3
"""Inspect and operate on a captured macOS window and its owning process."""

import argparse
import queue
import shlex
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

import front_window_info as info
import center_front_window as geometry
from gui_helpers import activate_window, copy_text
from process_actions import ProcessTarget
from tooltip import TkTooltip, notify
from window_picker import WindowHighlight, WindowPicker, WindowTarget, list_windows


def display(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def make_table(parent, columns, widths):
    frame = ttk.Frame(parent)
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    table = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
    for column, width in zip(columns, widths):
        table.heading(column, text=column)
        table.column(column, width=width, minwidth=60, stretch=column == columns[-1])
    vertical = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
    horizontal = ttk.Scrollbar(frame, orient="horizontal", command=table.xview)
    table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    table.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    return frame, table


def confirm_process(root, title, warning, details):
    """A bounded, scrollable warning dialog; Cancel is the default action."""
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.transient(root)
    dialog.geometry("700x380")
    dialog.minsize(480, 300)
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(1, weight=1)
    label = ttk.Label(dialog, text=warning, foreground="#b42318", wraplength=660)
    label.grid(row=0, column=0, sticky="ew", padx=16, pady=12)
    label.bind("<Configure>", lambda e: label.configure(wraplength=max(200, e.width)))
    content = ScrolledText(dialog, height=10, wrap="word", font="TkFixedFont")
    content.insert("1.0", details)
    content.configure(state="disabled")
    content.grid(row=1, column=0, sticky="nsew", padx=16)
    result = False

    def finish(accepted=False):
        nonlocal result
        result = accepted
        dialog.destroy()

    buttons = ttk.Frame(dialog)
    buttons.grid(row=2, column=0, sticky="e", padx=16, pady=12)
    cancel = ttk.Button(buttons, text="取消", command=finish)
    cancel.grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text=title, command=lambda: finish(True)).grid(row=0, column=1)
    dialog.protocol("WM_DELETE_WINDOW", finish)
    dialog.bind("<Escape>", lambda e: finish())
    dialog.bind("<Command-w>", lambda e: finish())
    dialog.wait_visibility()
    dialog.grab_set()
    cancel.focus_set()
    root.wait_window(dialog)
    return result


class WindowInspector:
    PREVIEW_MS = 3000
    TIP_MS = 800
    ERROR_MS = 1800
    WINDOWS_PROMPT = "请先按「刷新列表」加载所有窗口，或拖动左侧小圆饼到目标窗口"
    LOADED_PROMPT = "轻按「刷新列表」刷新所有窗口列表，或将小圆饼拖动到目标窗口，以查看窗口信息"
    CONTROLS_PROMPT = "请先点击『读取控件』按钮"
    READY_PROMPT = "拖动左上角 ◎ 选窗；双击列表单元格复制"
    FIELD_NAMES = dict(zip(
        ("Name", "Bundle ID", "PID", "Parent PID", "User", "Executable", "Bundle path",
         "Command", "Started", "CPU time", "RSS / VSZ", "Binary type", "Display name",
         "Identifier", "Short version", "Bundle version", "Package type", "Minimum system",
         "Window count", "Title", "Role", "Subrole", "Position", "Size", "Minimized",
         "Fullscreen", "Modal", "Document", "Working directory", "Argument access", "Status"),
        ("应用名称", "Bundle ID", "进程 PID", "父进程 PID", "用户", "可执行文件", "应用包路径",
         "命令行", "启动时间", "CPU 时间", "驻留／虚拟内存", "架构", "显示名称",
         "标识符", "版本", "构建版本", "包类型", "最低系统版本",
         "所属进程窗口数", "标题", "角色", "子角色", "位置（逻辑点）", "大小（逻辑点）", "最小化",
         "全屏", "模态窗口", "文档", "工作目录", "参数读取", "状态")))

    def __init__(self, root, app, window):
        self.root = root
        self.app = self.window = self.target = self.selection = None
        self.app_ref = None
        self.entries = []
        self.list_loaded = False
        self.sections, self.paths = {}, {}
        self.busy = False
        self.results = queue.Queue()
        self.restarted_processes = []
        self.buttons, self.target_buttons, self.window_buttons = [], [], []
        self.return_timer = self.preview_timer = None
        self.activation_timer = None
        self.status = tk.StringVar(value=self.READY_PROMPT)
        self.topmost = tk.BooleanVar(value=True)
        self.hidden = tk.BooleanVar(value=False)
        self.tip = TkTooltip(root)
        self.hover = TkTooltip(root)
        self.border = WindowHighlight(root)
        self.build()
        if app is not None:
            self.app = app
            self.target = ProcessTarget(int(app.processIdentifier()))
            self.app_ref = info.AS.AXUIElementCreateApplication(self.target.pid)
            info.AS.AXUIElementSetMessagingTimeout(self.app_ref, 1.0)
            self.window = window
            if window is not None:
                self.selection = WindowTarget.capture(app, window)
                self.entries.append(self.selection)
            self.run(self.refresh)
        self.sync_selector()
        self.update_actions()
        self.apply_topmost()

    def build(self):
        root = self.root
        root.title("窗口信息查看器")
        root.geometry("1100x700")
        root.minsize(1000, 520)
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        body = ttk.Frame(root, padding=8)
        body.grid(sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(4, weight=1)

        header = ttk.Frame(body)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        finder = ttk.Label(header, text="◎", font=("Helvetica", 26), anchor="center", width=2)
        finder.grid(row=0, column=0, padx=(0, 6))
        self.selector = ttk.Combobox(header)
        self.selector.grid(row=0, column=1, sticky="ew")
        self.selector.bind("<<ComboboxSelected>>", self.select_window)
        self.selector.bind("<Return>", lambda e: self.run(self.search))
        self.selector.bind("<FocusIn>", self.clear_prompt)
        self.selector.bind("<FocusOut>", lambda e: self.selector.set(self.list_prompt()) if not self.selector.get() else None)
        self.add_button(header, "刷新列表", self.refresh_list, 2)
        self.add_button(header, "查找", self.search, 3)
        self.bind_hint(self.selector, "可输入窗口标题、应用名称或 PID:进程号查找；也可从列表选择窗口")
        self.picker = WindowPicker(root, finder, self.border, self.picked, self.status.set, self.begin_pick)
        self.bind_hint(finder, WindowPicker.HINT)

        options = ttk.Frame(body)
        options.grid(row=1, column=0, sticky="ew", pady=(3, 5))
        self.hidden_button = ttk.Checkbutton(options, text="包含隐藏窗口", variable=self.hidden,
                                            command=lambda: self.run(self.refresh_list) if self.list_loaded else None)
        self.hidden_button.grid(row=0, column=0)
        self.bind_hint(self.hidden_button, "包含隐藏应用及最小化窗口；仅列出应用通过辅助功能公开的窗口")
        ttk.Checkbutton(options, text="查看器置顶", variable=self.topmost,
                        command=self.apply_topmost).grid(row=0, column=1, padx=6)
        self.add_button(options, "刷新信息", self.refresh_info, 2, target=True)
        self.add_button(options, "读取控件", self.read_controls, 3, window=True)
        ttk.Separator(options, orient="vertical").grid(row=0, column=4, sticky="ns", padx=8)
        self.add_button(options, "重启进程", self.restart, 5, target=True)
        self.add_button(options, "终止进程", self.kill, 6, target=True)

        actions = ttk.Frame(body)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        for col, (label, action, window) in enumerate((
            ("文件属性", self.file_properties, False), ("打开路径", self.open_path, False),
            ("激活窗口", self.bring_forward, True), ("窗口居中", self.center, True),
            ("重置大小", self.resize, True), ("显示边界", self.show_border, True),
            ("最小化窗口", self.minimize, True), ("关闭窗口", self.close_window, True),
        )):
            button = self.add_button(actions, label, action, col, target=not window, window=window)
            if label in ("激活窗口", "重置大小", "显示边界"):
                self.bind_hint(button, {
                    "激活窗口": "恢复并置前目标窗口，显示红框，3 秒后切回窗口信息查看器",
                    "重置大小": "调整为 1024 × 768 逻辑点，并在原显示器居中",
                    "显示边界": "仅显示目标窗口红框 3 秒，不改变焦点",
                }[label])

        fields = ttk.Frame(body)
        fields.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        fields.columnconfigure(1, weight=1)
        self.fields = {}
        for row, name in enumerate(("标题", "进程", "路径", "命令行")):
            ttk.Label(fields, text=name).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
            value = tk.StringVar()
            self.fields[name] = value
            ttk.Entry(fields, textvariable=value, state="readonly").grid(row=row, column=1, sticky="ew", pady=2)
        self.file_selector = ttk.Combobox(fields, state="readonly", width=10)
        self.file_selector.grid(row=2, column=2, padx=(6, 0))
        self.file_selector.bind("<<ComboboxSelected>>", lambda e: self.fields["路径"].set(self.paths.get(self.file_selector.get(), "")))

        split = ttk.Panedwindow(body, orient="horizontal")
        split.grid(row=4, column=0, sticky="nsew")
        frame, table = make_table(split, ("项目", "值"), (145, 285))
        split.add(frame, weight=2)
        self.tables = {"信息": table}
        self.notebook = ttk.Notebook(split)
        split.add(self.notebook, weight=3)
        for title, columns, widths in (
            ("控件", ("序号", "角色", "子角色", "标题"), (45, 140, 150, 200)),
            ("参数", ("序号", "参数"), (45, 480)),
        ):
            frame, table = make_table(self.notebook, columns, widths)
            self.notebook.add(frame, text=title)
            self.tables[title] = table
        for table in self.tables.values():
            table.bind("<Command-c>", lambda e, t=table: self.copy_rows(t))
            table.bind("<Double-1>", lambda e, t=table: self.copy_cell(t, e))
        self.reset_controls()
        footer = ttk.Frame(body)
        footer.grid(row=5, column=0, sticky="ew", pady=(5, 0))
        footer.columnconfigure(0, weight=1)
        status = ttk.Label(footer, textvariable=self.status, wraplength=760)
        status.grid(row=0, column=0, sticky="ew")
        status.bind("<Configure>", lambda e: status.configure(wraplength=max(100, e.width)))
        ttk.Button(footer, text="复制全部", command=self.copy_all).grid(row=0, column=1)
        root.protocol("WM_DELETE_WINDOW", self.close_inspector)
        root.bind("<Escape>", self.escape)
        root.bind("<Command-w>", self.close_inspector)

    def bind_hint(self, widget, text):
        widget.bind("<Enter>", lambda e: self.hover.show(text, 0) if not self.picker.dragging else None)
        widget.bind("<Leave>", lambda e: self.hover.hide())
        widget.bind("<ButtonPress>", lambda e: self.hover.hide(), add="+")

    def feedback(self, text, level="info", duration_ms=None):
        self.status.set(text)
        try:
            if duration_ms is None:
                duration_ms = self.TIP_MS if level == "info" else self.ERROR_MS
            self.tip.show(text, duration_ms, level=level)
        except Exception as exc:
            print(f"{text} (tooltip unavailable: {exc})", file=sys.stderr)

    def apply_topmost(self):
        self.root.attributes("-topmost", self.topmost.get() and self.return_timer is None and self.preview_timer is None)

    def cancel_preview(self):
        for name in ("return_timer", "preview_timer", "activation_timer"):
            token = getattr(self, name)
            if token is not None:
                self.root.after_cancel(token)
                setattr(self, name, None)
        self.border.hide()
        self.apply_topmost()

    def escape(self, event=None):
        if self.picker.dragging:
            self.picker.cancel()
            self.status.set("已取消选窗")
        else:
            self.close_inspector()
        return "break"

    def close_inspector(self, event=None):
        if self.busy:
            self.feedback("请等待当前操作完成。", "warning")
        else:
            self.cancel_preview()
            self.picker.cancel()
            self.hover.hide()
            self.tip.hide()
            self.root.destroy()
        return "break"

    def add_button(self, parent, label, action, column, *, target=False, window=False):
        button = ttk.Button(parent, text=label, width=8, command=lambda: self.run(action))
        button.grid(row=0, column=column, padx=(0, 5))
        self.buttons.append(button)
        if target or window:
            self.target_buttons.append(button)
        if window:
            self.window_buttons.append(button)
        return button

    def update_actions(self):
        for button in self.buttons:
            disabled = (self.busy or (button in self.target_buttons and self.target is None)
                        or (button in self.window_buttons and self.window is None))
            button.configure(state="disabled" if disabled else "normal")
        self.selector.configure(state="disabled" if self.busy else "normal")
        self.hidden_button.configure(state="disabled" if self.busy else "normal")

    def run(self, action):
        if self.busy:
            return
        self.hover.hide()
        try:
            action()
        except Exception as exc:
            self.feedback(f"窗口操作失败：{exc}", "error")

    def checked_window(self):
        if self.selection is None:
            raise RuntimeError("请先选择窗口。")
        try:
            return self.selection.checked()
        except Exception:
            self.clear_target()
            self.sync_selector()
            raise

    def list_prompt(self):
        return self.LOADED_PROMPT if self.list_loaded else self.WINDOWS_PROMPT

    def sync_selector(self):
        self.selector.configure(values=[self.list_prompt()] + [entry.label for entry in self.entries])
        index = next((i for i, entry in enumerate(self.entries) if entry.matches(self.selection)), None)
        self.selector.current(0 if index is None else index + 1)

    def clear_prompt(self, event=None):
        if self.selector.get() in (self.WINDOWS_PROMPT, self.LOADED_PROMPT):
            self.selector.set("")

    def clear_target(self):
        self.cancel_preview()
        self.app = self.window = self.target = self.selection = self.app_ref = None
        self.sections, self.paths = {}, {}
        for value in self.fields.values():
            value.set("")
        for table in self.tables.values():
            table.delete(*table.get_children())
        self.file_selector.configure(values=[])
        self.file_selector.set("")
        self.reset_controls()
        self.update_actions()

    def refresh_list(self, query=None):
        hidden = self.hidden.get()
        def loaded(entries):
            self.entries = entries
            self.list_loaded = True
            if query is None:
                selected = next((entry for entry in entries if entry.matches(self.selection)), None)
                if selected is None:
                    self.clear_target()
                else:
                    self.load(selected)
                self.sync_selector()
                self.feedback(f"列表已刷新，共 {len(entries)} 个窗口")
            else:
                self.sync_selector()
                self.find_in_list(query)
        self.start_job(lambda: list_windows(hidden), "正在读取窗口列表…", loaded)

    def search(self):
        query = self.selector.get().strip()
        if not query or query in (self.WINDOWS_PROMPT, self.LOADED_PROMPT):
            self.feedback("请输入窗口标题、应用名称或 PID:进程号。", "warning")
            return
        if not self.list_loaded:
            self.refresh_list(query)
        else:
            self.find_in_list(query)

    def find_in_list(self, query):
        query = query.casefold()
        pid_query = query.removeprefix("pid:").strip()
        by_pid = pid_query.isdecimal()
        for entry in self.entries:
            if (str(entry.process.pid) == pid_query if by_pid else query in entry.label.casefold()):
                self.load(entry)
                return
        self.clear_target()
        self.selector.set(query)
        self.feedback("未找到匹配窗口。可刷新列表或勾选「包含隐藏窗口」。", "warning")

    def load(self, entry):
        try:
            entry.checked()
        except Exception:
            self.clear_target()
            self.sync_selector()
            raise
        self.cancel_preview()
        self.selection = entry
        self.app, self.window, self.target = entry.app, entry.window, entry.process
        self.app_ref = info.AS.AXUIElementCreateApplication(self.target.pid)
        info.AS.AXUIElementSetMessagingTimeout(self.app_ref, 1.0)
        if not any(item.matches(entry) for item in self.entries):
            self.entries.append(entry)
        self.refresh()
        self.sync_selector()

    def select_window(self, event=None):
        index = self.selector.current() - 1
        if not self.busy and 0 <= index < len(self.entries):
            self.run(lambda: self.load(self.entries[index]))
        else:
            self.sync_selector()

    def begin_pick(self):
        if self.busy:
            return False
        self.cancel_preview()
        self.hover.hide()
        self.tip.hide()
        return True

    def picked(self, target):
        self.run(lambda: self.load(target))
        self.activation_timer = activate_window(self.root)

    def refresh_info(self):
        self.refresh()
        self.feedback("窗口信息已刷新")

    def refresh(self):
        if self.window is not None:
            self.checked_window()
        try:
            process = self.target.checked()
        except Exception:
            self.clear_target()
            self.sync_selector()
            raise
        self.sections = info.collect_info(self.app, self.window)
        try:
            self.argv = process.cmdline()
            self.sections["Application"]["Command"] = shlex.join(self.argv)
            self.sections["Application"]["Working directory"] = process.cwd()
        except Exception as exc:
            self.argv = []
            self.sections["Application"]["Argument access"] = str(exc)
        for table in self.tables.values():
            table.delete(*table.get_children())
        for section in ("Window", "Application", "Bundle"):
            for label, value in self.sections[section].items():
                name = self.FIELD_NAMES.get(label, label)
                if label == "Status" and self.window is None:
                    value = "应用未通过辅助功能公开窗口。"
                if section == "Bundle":
                    name = "应用包 · " + name
                self.tables["信息"].insert("", "end", values=(name, display(value)))
        self.reset_controls()
        for index, argument in enumerate(self.argv):
            self.tables["参数"].insert("", "end", values=(index, argument))
        self.fields["标题"].set(self.sections["Window"].get("Title", ""))
        self.fields["进程"].set(f"{self.app.localizedName()} (PID: {self.target.pid})")
        self.fields["命令行"].set(self.sections["Application"]["Command"])
        previous = self.file_selector.get()
        self.paths = {label: value for label, value in (
            ("可执行文件", self.sections["Application"]["Executable"]),
            ("应用包", self.sections["Application"]["Bundle path"]),
        ) if value and (label != "应用包" or Path(value).is_dir())}
        document = urlparse(str(self.sections["Window"].get("Document", "")))
        if document.scheme == "file" and document.netloc in ("", "localhost"):
            self.paths["文档"] = unquote(document.path)
        self.file_selector.configure(values=list(self.paths))
        self.file_selector.set(previous if previous in self.paths else next(iter(self.paths), ""))
        self.fields["路径"].set(self.paths.get(self.file_selector.get(), ""))
        if self.selection is not None:
            self.selection.title = self.sections["Window"].get("Title") or "（无标题）"
        self.sync_selector()
        self.update_actions()
        self.status.set(self.READY_PROMPT if self.window is not None else "没有可访问的窗口。可刷新列表或拖动圆饼选窗。")

    def reset_controls(self):
        table = self.tables["控件"]
        table.delete(*table.get_children())
        table.configure(displaycolumns=("标题",))
        table.insert("", "end", iid="hint", values=("", "", "", self.CONTROLS_PROMPT))

    def read_controls(self):
        children = info._ax_attr(self.checked_window(), "AXChildren", [])
        rows = info._child_summary(self.window, limit=500)
        table = self.tables["控件"]
        table.delete(*table.get_children())
        table.configure(displaycolumns="#all")
        for row in rows:
            table.insert("", "end", values=row)
        self.notebook.select(0)
        suffix = f"（共 {len(children)} 个，仅显示前 500 个）" if len(children) > 500 else ""
        self.feedback(f"已读取 {len(rows)} 个直接子控件{suffix}")

    def show_border(self):
        self.checked_window()
        self.border.show(self.selection, self.PREVIEW_MS)

    def bring_forward(self):
        window = self.checked_window()
        self.cancel_preview()
        self.root.attributes("-topmost", False)
        try:
            if self.app.isHidden():
                self.app.unhide()
            if info._ax_attr(window, "AXMinimized", False):
                self.set_window_attribute(window, "AXMinimized", False)
            self.app.activateWithOptions_(info.AppKit.NSApplicationActivateIgnoringOtherApps)
            error = info.AS.AXUIElementPerformAction(window, "AXRaise")
            if error:
                raise RuntimeError(f"无法激活窗口（AX 错误 {error}）。")
        except Exception:
            self.apply_topmost()
            raise
        # Allow the application's restore animation to settle before reading its frame.
        target = self.selection
        self.preview_timer = self.root.after(300, lambda: self.finish_preview(target))

    def finish_preview(self, target):
        self.preview_timer = None
        try:
            if not target.matches(self.selection):
                self.apply_topmost()
                return
            front = info._frontmost_app()
            if front is None or int(front.processIdentifier()) != target.process.pid:
                raise RuntimeError("无法将目标窗口移到前台。")
            focused = info._ax_attr(self.app_ref, "AXFocusedWindow", None)
            if focused is not None and focused != target.window:
                raise RuntimeError("应用未将所选窗口移到前台。")
            self.border.show(target, self.PREVIEW_MS)
            self.feedback("窗口已激活\n3 秒后切回窗口信息查看器", duration_ms=self.PREVIEW_MS)
            self.return_timer = self.root.after(self.PREVIEW_MS, self.return_focus)
        except Exception as exc:
            self.return_focus()
            self.feedback(str(exc), "warning")

    def return_focus(self):
        self.return_timer = None
        self.border.hide()
        self.apply_topmost()
        self.activation_timer = activate_window(self.root)
        self.status.set("已返回窗口信息查看器")

    @staticmethod
    def set_window_attribute(window, name, value):
        error = info.AS.AXUIElementSetAttributeValue(window, name, value)
        if error:
            raise RuntimeError(f"无法设置 {name}（AX 错误 {error}）。")

    def minimize(self):
        self.cancel_preview()
        self.set_window_attribute(self.checked_window(), "AXMinimized", True)
        self.refresh_after_action(self.selection)
        self.feedback("已发送最小化窗口请求")

    def refresh_after_action(self, target):
        def refresh():
            if not self.busy and target.matches(self.selection):
                try:
                    target.checked()
                except Exception:
                    self.clear_target()
                    self.sync_selector()
                else:
                    self.run(self.refresh)
        self.root.after(300, refresh)

    def center(self):
        geometry.center_window(SimpleNamespace(display="current", fit=False), self.checked_window())
        self.refresh()
        self.feedback("窗口已居中")

    def resize(self):
        window = self.checked_window()
        bounds = geometry._target_display_bounds("current", geometry._window_position(window),
                                                  geometry._window_size(window))
        geometry._set_window_size(window, 1024, 768)
        target = self.selection
        def report_size():
            if not target.matches(self.selection):
                return
            target.checked()
            size = geometry._window_size(window)
            geometry._center_on_display(window, bounds, size)
            self.refresh()
            if abs(size.width - 1024) > 1 or abs(size.height - 768) > 1:
                self.feedback(f"应用将窗口大小限制为 {size.width:.0f} × {size.height:.0f}，已居中。", "warning")
            else:
                self.feedback("窗口已重置为 1024 × 768 并居中")
        self.root.after(250, lambda: self.run(report_size))

    def close_window(self):
        window = self.checked_window()
        button = info._ax_attr(window, "AXCloseButton", None)
        if button is None:
            raise RuntimeError("此窗口未提供关闭按钮。")
        if not messagebox.askyesno("关闭窗口", "关闭窗口？", detail=str(
                info._ax_attr(window, "AXTitle")), icon="warning", default="no", parent=self.root):
            return
        self.checked_window()
        self.cancel_preview()
        error = info.AS.AXUIElementPerformAction(button, "AXPress")
        if error:
            raise RuntimeError(f"无法关闭窗口（AX 错误 {error}）。")
        self.refresh_after_action(self.selection)
        self.feedback("已发送关闭窗口请求")

    def file_path(self):
        value = self.paths.get(self.file_selector.get())
        if not value or not Path(value).exists():
            raise RuntimeError("所选文件路径不可用。")
        return value

    def open_path(self):
        subprocess.run(["/usr/bin/open", "-R", self.file_path()], check=True, timeout=5)
        self.topmost.set(False)
        self.apply_topmost()

    def file_properties(self):
        script = """on run argv
tell application "Finder"
    open information window of (POSIX file (item 1 of argv) as alias)
    activate
end tell
end run"""
        result = subprocess.run(["/usr/bin/osascript", "-e", script, self.file_path()],
                                capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        self.topmost.set(False)
        self.apply_topmost()

    def process_details(self):
        return f"应用：{self.app.localizedName()}\nPID: {self.target.pid}\n可执行文件：{self.target.checked().exe()}"

    def kill(self):
        details = self.process_details()
        if confirm_process(self.root, "终止进程", "终止进程？此进程所有窗口中未保存的内容可能丢失。", details):
            self.start_job(self.target.kill, "正在终止进程…", self.process_finished)

    def restart(self):
        plan = self.target.prepare_restart()
        details = (f"{self.process_details()}\n工作目录：{plan.cwd}\n\n"
                   f"命令行：\n{shlex.join(plan.argv)}\n\n参数：\n" +
                   "\n".join(f"[{index}] {argument!r}" for index, argument in enumerate(plan.argv)))
        if confirm_process(self.root, "重启进程", "重启进程？此进程所有窗口中未保存的内容可能丢失。", details):
            self.start_job(lambda: self.target.restart(plan), "正在等待原进程退出…", self.process_finished)

    def start_job(self, work, message, completed):
        self.cancel_preview()
        self.busy = True
        self.status.set(message)
        self.update_actions()
        self.completed = completed
        def worker():
            try:
                self.results.put((work(), None))
            except Exception as exc:
                self.results.put((None, str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(50, self.finish_job)

    def finish_job(self):
        try:
            result, error = self.results.get_nowait()
        except queue.Empty:
            self.root.after(50, self.finish_job)
            return
        self.busy = False
        self.update_actions()
        if error:
            self.feedback(error, "error")
        else:
            self.run(lambda: self.completed(result))

    def process_finished(self, child):
        self.clear_target()
        self.sync_selector()
        if child is not None:
            self.restarted_processes.append(child)
            self.feedback(f"已启动新进程（PID: {child.pid}）；可刷新列表选择新窗口。")
        else:
            self.feedback("进程已终止；可选择其他窗口。")

    def copy_cell(self, table, event):
        if table.identify_region(event.x, event.y) == "cell":
            item, column = table.identify_row(event.y), table.identify_column(event.x)
            if item and column and item != "hint":
                copy_text(self.root, table.set(item, column))
                self.feedback("已复制")
        return "break"

    def copy_rows(self, table):
        rows = [table.item(item, "values") for item in table.selection() if item != "hint"]
        if rows:
            copy_text(self.root, "\n".join("\t".join(map(str, row)) for row in rows))
            self.feedback("已复制")
        return "break"

    def copy_all(self):
        text = "\n\n".join(title + "\n" + "\n".join(
            "\t".join(map(str, table.item(item, "values"))) for item in table.get_children() if item != "hint")
            for title, table in self.tables.items())
        copy_text(self.root, text)
        self.feedback("已复制")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, help="Inspect a specific running application")
    args = parser.parse_args()
    root = None
    try:
        app = info._running_app_for_pid(args.pid) if args.pid else info._frontmost_app()
        if app is None:
            raise RuntimeError("No target application.")
        # Capture the exact window before Tk can activate this process.
        app_ref = info.AS.AXUIElementCreateApplication(app.processIdentifier())
        info.AS.AXUIElementSetMessagingTimeout(app_ref, 1.0)
        window = info._focused_window(app_ref)
        root = tk.Tk()
        root.withdraw()
        inspector = WindowInspector(root, app, window)
        root.deiconify()
        inspector.activation_timer = activate_window(root)
        root.mainloop()
    except Exception as exc:
        if root is not None:
            root.destroy()
        print(str(exc), file=sys.stderr)
        notify(str(exc), level="error")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
