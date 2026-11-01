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
from tooltip import notify


def display(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
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
    cancel = ttk.Button(buttons, text="Cancel", command=finish)
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
    def __init__(self, root, app, window):
        self.root = root
        self.app = app
        self.target = ProcessTarget(int(app.processIdentifier()))
        self.app_ref = info.AS.AXUIElementCreateApplication(self.target.pid)
        info.AS.AXUIElementSetMessagingTimeout(self.app_ref, 1.0)
        self.window = window
        self.windows = []
        self.sections = {}
        self.paths = {}
        self.busy = False
        self.results = queue.Queue()
        self.restarted_processes = []
        self.buttons = []
        self.window_buttons = []
        self.status = tk.StringVar(value="")
        self.build()
        self.refresh()

    def build(self):
        root = self.root
        root.title(f"Window Inspector - {self.app.localizedName()} [{self.target.pid}]")
        root.geometry("1040x760")
        root.minsize(800, 580)
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        body = ttk.Frame(root, padding=6)
        body.grid(sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(4, weight=1)

        header = ttk.Frame(body)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 4))
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text=f"{self.app.localizedName()}  |  PID {self.target.pid}").grid(row=0, column=0, padx=(0, 12))
        self.selector = ttk.Combobox(header, state="readonly")
        self.selector.grid(row=0, column=1, sticky="ew")
        self.selector.bind("<<ComboboxSelected>>", self.select_window)
        self.add_button(header, "Refresh", self.refresh, 2)

        actions = ttk.Frame(body)
        actions.grid(row=1, column=0, sticky="ew", padx=12)
        actions.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(actions)
        toolbar.grid(row=0, column=0, sticky="ew")
        groups = []
        for name, commands in (
            ("Window", (("Bring Forward", self.bring_forward), ("Center", self.center),
                        ("1024 x 768", self.resize), ("Close Window", self.close_window))),
            ("Process", (("Restart Process", self.restart), ("Kill Process", self.kill))),
        ):
            group = ttk.Frame(toolbar)
            groups.append(group)
            ttk.Label(group, text=name).grid(row=0, column=0, sticky="w", padx=(0, 8))
            for column, (label, action) in enumerate(commands, start=1):
                button = self.add_button(group, label, action, column)
                if name == "Window":
                    self.window_buttons.append(button)
        groups[0].grid(row=0, column=0, sticky="w", pady=3)
        groups[1].grid(row=0, column=2, sticky="w", pady=3)
        divider = ttk.Separator(toolbar, orient="vertical")
        divider.grid(row=0, column=1, sticky="ns", padx=(4, 10), pady=4)

        def arrange_actions(event):
            required = sum(group.winfo_reqwidth() for group in groups) + 16
            if event.width < required:
                divider.grid_remove()
                groups[1].grid(row=1, column=0, columnspan=3)
            else:
                divider.grid()
                groups[1].grid(row=0, column=2, columnspan=1)

        toolbar.bind("<Configure>", arrange_actions)
        ttk.Separator(actions).grid(row=1, column=0, sticky="ew", pady=2)
        files = ttk.Frame(actions)
        files.grid(row=2, column=0, sticky="ew", pady=(2, 5))
        files.columnconfigure(1, weight=1)
        ttk.Label(files, text="File").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.file_selector = ttk.Combobox(files, state="readonly")
        self.file_selector.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.add_button(files, "Open Path", self.open_path, 2)
        self.add_button(files, "File Properties", self.file_properties, 3)

        ttk.Label(body, text="Command line").grid(row=2, column=0, sticky="w", padx=12)
        self.command = ScrolledText(body, height=3, wrap="word", font="TkFixedFont")
        self.command.grid(row=3, column=0, sticky="ew", padx=12, pady=(3, 5))
        style = ttk.Style(root)
        style.configure("Inspector.TNotebook", padding=(2, 2, 2, 2), tabmargins=(0, 0))
        self.notebook = ttk.Notebook(body, style="Inspector.TNotebook")
        self.notebook.grid(row=4, column=0, sticky="nsew")
        self.tables = {}
        for title, columns, widths in (
            ("Application / Bundle", ("Section", "Property", "Value"), (110, 130, 660)),
            ("Window", ("Property", "Value"), (160, 740)),
            ("AX Children", ("Index", "Role", "Subrole", "Title"), (60, 180, 200, 460)),
            ("Arguments", ("Index", "Argument"), (60, 840)),
        ):
            frame, table = make_table(self.notebook, columns, widths)
            self.notebook.add(frame, text=title)
            self.tables[title] = table
            table.bind("<Command-c>", lambda e, t=table: self.copy_rows(t))
            table.bind("<Double-1>", lambda e, t=table: self.copy_cell(t, e))
        footer = ttk.Frame(body)
        footer.grid(row=5, column=0, sticky="ew", pady=(4, 0))
        footer.columnconfigure(0, weight=1)
        status = ttk.Label(footer, textvariable=self.status, wraplength=580)
        status.grid(row=0, column=0, sticky="ew")
        status.bind("<Configure>", lambda e: status.configure(wraplength=max(100, e.width)))
        ttk.Button(footer, text="Copy Selected", command=self.copy_rows).grid(row=0, column=1, padx=8)
        ttk.Button(footer, text="Copy All", command=self.copy_all).grid(row=0, column=2)
        root.protocol("WM_DELETE_WINDOW", self.close_inspector)
        root.bind("<Escape>", self.close_inspector)
        root.bind("<Command-w>", self.close_inspector)

    def close_inspector(self, event=None):
        if self.busy:
            self.status.set("Wait for the process operation to finish before closing.")
        else:
            self.root.destroy()

    def add_button(self, parent, label, action, column):
        button = ttk.Button(parent, text=label, command=lambda: self.run(action))
        button.grid(row=0, column=column, padx=(0, 8))
        self.buttons.append(button)
        return button

    def run(self, action):
        if self.busy:
            return
        try:
            action()
        except Exception as exc:
            self.status.set(str(exc))
            messagebox.showerror("Window Inspector", str(exc), parent=self.root)

    def checked_window(self):
        self.target.checked()
        current = info._ax_attr(self.app_ref, "AXWindows", [])
        if self.window is None or self.window not in current:
            raise RuntimeError("The selected window is no longer available. Refresh the window list.")
        return self.window

    def refresh(self):
        process = self.target.checked()
        self.windows = list(info._ax_attr(self.app_ref, "AXWindows", []))
        self.selector.configure(values=[
            f"{index + 1}: {info._ax_attr(window, 'AXTitle') or '(Untitled)'}"
            for index, window in enumerate(self.windows)
        ])
        if self.window in self.windows:
            self.selector.current(self.windows.index(self.window))
        else:
            self.window = None
            self.selector.set("")
        for button in self.window_buttons:
            button.configure(state="normal" if self.window is not None else "disabled")
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
        for section, fields in self.sections.items():
            for label, value in fields.items():
                if section == "Window":
                    self.tables["Window"].insert("", "end", values=(label, display(value)))
                else:
                    self.tables["Application / Bundle"].insert("", "end", values=(section, label, display(value)))
        for row in info._child_summary(self.window) if self.window is not None else []:
            self.tables["AX Children"].insert("", "end", values=row)
        for index, argument in enumerate(self.argv):
            self.tables["Arguments"].insert("", "end", values=(index, argument))
        self.command.configure(state="normal")
        self.command.delete("1.0", "end")
        self.command.insert("1.0", self.sections["Application"]["Command"])
        self.command.configure(state="disabled")
        previous = self.file_selector.get()
        self.paths = {label: value for label, value in (
            ("Executable", self.sections["Application"]["Executable"]),
            ("App bundle", self.sections["Application"]["Bundle path"]),
        ) if value and (label != "App bundle" or Path(value).is_dir())}
        document = urlparse(str(self.sections["Window"].get("Document", "")))
        if document.scheme == "file" and document.netloc in ("", "localhost"):
            self.paths["Document"] = unquote(document.path)
        self.file_selector.configure(values=list(self.paths))
        self.file_selector.set(previous if previous in self.paths else next(iter(self.paths), ""))
        self.status.set("Updated." if self.window is not None else "No accessible window. Check Accessibility permission or select a window.")

    def select_window(self, event=None):
        index = self.selector.current()
        if not self.busy and 0 <= index < len(self.windows):
            self.window = self.windows[index]
            self.run(self.refresh)

    def bring_forward(self):
        window = self.checked_window()
        self.app.activateWithOptions_(info.AppKit.NSApplicationActivateIgnoringOtherApps)
        error = info.AS.AXUIElementPerformAction(window, "AXRaise")
        if error:
            raise RuntimeError(f"Cannot bring this window forward (AX error {error}).")

    def center(self):
        geometry.center_window(SimpleNamespace(display="current", fit=False), self.checked_window())
        self.refresh()

    def resize(self):
        window = self.checked_window()
        geometry._set_window_size(window, 1024, 768)

        def report_size():
            size = geometry._window_size(window)
            self.refresh()
            if abs(size.width - 1024) > 1 or abs(size.height - 768) > 1:
                self.status.set(f"Application limited the size to {size.width:.0f} x {size.height:.0f}.")

        self.root.after(250, lambda: self.run(report_size))

    def close_window(self):
        window = self.checked_window()
        button = info._ax_attr(window, "AXCloseButton", None)
        if button is None:
            raise RuntimeError("This window does not expose a close button.")
        if not messagebox.askyesno("Close Window", "Close the selected window?", detail=str(
                info._ax_attr(window, "AXTitle")), icon="warning", default="no", parent=self.root):
            return
        self.checked_window()
        error = info.AS.AXUIElementPerformAction(button, "AXPress")
        if error:
            raise RuntimeError(f"Cannot close this window (AX error {error}).")
        self.root.after(250, lambda: self.run(self.refresh))

    def file_path(self):
        value = self.paths.get(self.file_selector.get())
        if not value or not Path(value).exists():
            raise RuntimeError("The selected file path is unavailable.")
        return value

    def open_path(self):
        subprocess.run(["/usr/bin/open", "-R", self.file_path()], check=True, timeout=5)

    def file_properties(self):
        script = '''on run argv
tell application "Finder"
    open information window of (POSIX file (item 1 of argv) as alias)
    activate
end tell
end run'''
        result = subprocess.run(["/usr/bin/osascript", "-e", script, self.file_path()],
                                capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())

    def process_details(self):
        return f"Application: {self.app.localizedName()}\nPID: {self.target.pid}\nExecutable: {self.target.checked().exe()}"

    def kill(self):
        details = self.process_details()
        if confirm_process(self.root, "Kill Process", "Warning: force termination can lose unsaved work in every window of this process.", details):
            self.start_job(self.target.kill, "Terminating process...")

    def restart(self):
        plan = self.target.prepare_restart()
        details = (f"{self.process_details()}\nWorking directory: {plan.cwd}\n\n"
                   f"Command:\n{shlex.join(plan.argv)}\n\nArguments:\n" +
                   "\n".join(f"[{index}] {argument!r}" for index, argument in enumerate(plan.argv)))
        if confirm_process(self.root, "Restart Process", "Warning: restart terminates this process and all its windows. Unsaved work may be lost.", details):
            self.start_job(lambda: self.target.restart(plan), "Waiting for the process to exit...")

    def start_job(self, work, message):
        self.busy = True
        self.status.set(message)
        for button in self.buttons:
            button.configure(state="disabled")
        self.selector.configure(state="disabled")

        def worker():
            try:
                self.results.put((work(), None))
            except Exception as exc:
                self.results.put((None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(50, self.finish_job)

    def finish_job(self):
        try:
            child, error = self.results.get_nowait()
        except queue.Empty:
            self.root.after(50, self.finish_job)
            return
        self.busy = False
        for button in self.buttons:
            button.configure(state="normal")
        self.selector.configure(state="readonly")
        if error:
            self.status.set(error)
            messagebox.showerror("Process operation failed", error, parent=self.root)
        elif child is not None:
            self.restarted_processes.append(child)
            self.status.set(f"Restart launched as PID {child.pid}. Displayed information belongs to the original process.")
        else:
            self.status.set("Process terminated. Displayed information is the last snapshot.")

    def copy_cell(self, table, event):
        if table.identify_region(event.x, event.y) == "cell":
            item = table.identify_row(event.y)
            column = table.identify_column(event.x)
            if item and column:
                copy_text(self.root, table.set(item, column))
        return "break"

    def copy_rows(self, table=None):
        if table is None:
            title = self.notebook.tab(self.notebook.select(), "text")
            table = self.tables[title]
        rows = [table.item(item, "values") for item in table.selection()]
        if rows:
            copy_text(self.root, "\n".join("\t".join(map(str, row)) for row in rows))
        return "break"

    def copy_all(self):
        text = "\n\n".join(
            section + "\n" + "\n".join(f"{label}: {display(value)}" for label, value in fields.items())
            for section, fields in self.sections.items()
        )
        for title in ("AX Children", "Arguments"):
            table = self.tables[title]
            text += "\n\n" + title + "\n" + "\n".join(
                "\t".join(map(str, table.item(item, "values"))) for item in table.get_children()
            )
        copy_text(self.root, text)


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
        WindowInspector(root, app, window)
        root.deiconify()
        activate_window(root)
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
