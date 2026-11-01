#!/usr/bin/env python3
"""Run a quick-menu command in Terminal or a separate Tk output window."""

import codecs
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time

OUTPUT_LIMIT = 1024 * 1024  # Keep at most 1 MiB per stream; continue draining pipes.
TRUNCATION_NOTICE = "\n[Output truncated at 1 MiB.]\n"
TERMINAL_SCRIPT = '''on run argv
    set commandText to item 1 of argv
    set workDir to item 2 of argv
    tell application "Terminal"
        do script "cd -- " & quoted form of workDir & " && /bin/zsh -lc " & quoted form of commandText
        activate
    end tell
end run'''


def launch_command(spec):
    if spec["output"] == "terminal":
        subprocess.run(
            ["/usr/bin/osascript", "-e", TERMINAL_SCRIPT, spec["command"], spec["cwd"]],
            check=True, capture_output=True, timeout=15,
        )
    else:
        child = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve())],
            stdin=subprocess.PIPE, start_new_session=True,
        )
        assert child.stdin is not None
        try:
            child.stdin.write(json.dumps(dict(spec)).encode("utf-8"))
        finally:
            child.stdin.close()


class _AnsiFilter:
    """Discard terminal controls incrementally, without buffering control payloads."""

    def __init__(self):
        self.state = "text"
        self.osc = False

    def feed(self, text):
        output = []
        for char in text:
            if self.state in ("string", "string_escape"):
                if (char in "\x18\x1a\x9c" or (self.osc and char == "\x07")
                        or (self.state == "string_escape" and char == "\\")):
                    self.state = "text"
                else:
                    self.state = "string_escape" if char == "\x1b" else "string"
                continue
            if char == "\x1b":
                self.state = "escape"
            elif char in "\x18\x1a":
                self.state = "text"
            elif char == "\x9b":
                self.state = "csi"
            elif char in "\x90\x98\x9d\x9e\x9f":
                self.state, self.osc = "string", char == "\x9d"
            elif char in "\t\n\r":
                output.append(char)
            elif char < " " or "\x7f" <= char <= "\x9f":
                continue
            elif self.state == "escape" and char == "[":
                self.state = "csi"
            elif self.state == "escape" and char in "]PX^_":
                self.state, self.osc = "string", char == "]"
            elif self.state in ("escape", "intermediate") and " " <= char <= "/":
                self.state = "intermediate"
            elif self.state in ("escape", "intermediate") and "0" <= char <= "~":
                self.state = "text"
            elif self.state == "csi" and " " <= char <= "?":
                continue
            elif self.state == "csi" and "@" <= char <= "~":
                self.state = "text"
            else:
                self.state = "text"
                output.append(char)
        return "".join(output)


def capture_command(spec, cancel, on_output=None):
    if cancel.is_set():
        return -signal.SIGTERM, "", ""
    process = subprocess.Popen(
        ["/bin/zsh", "-lc", spec["command"]], cwd=spec["cwd"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    )
    outputs = [[], []]

    def read_stream(stream, index):
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        ansi = _AnsiFilter()
        retained_size = 0
        truncated = False

        def publish(text):
            if text:
                outputs[index].append(text)
                if on_output is not None:
                    on_output(index, text)

        with stream:
            while chunk := stream.read1(65536):
                remaining = OUTPUT_LIMIT - retained_size
                retained = chunk[:remaining]
                retained_size += len(retained)
                if not truncated:
                    publish(ansi.feed(decoder.decode(retained)))
                    if len(chunk) > remaining:
                        truncated = True
                        publish(ansi.feed(decoder.decode(b"", final=True)))
                        publish(TRUNCATION_NOTICE)
            if not truncated:
                publish(ansi.feed(decoder.decode(b"", final=True)))

    readers = [threading.Thread(target=read_stream, args=(stream, index), daemon=True)
               for index, stream in enumerate((process.stdout, process.stderr))]
    for reader in readers:
        reader.start()
    stopping_at = None
    while process.poll() is None or any(reader.is_alive() for reader in readers):
        if cancel.is_set():
            now = time.monotonic()
            sig = signal.SIGTERM if stopping_at is None else signal.SIGKILL
            if stopping_at is None or now - stopping_at >= 2:
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    pass
                if stopping_at is None:
                    stopping_at = now
                elif now - stopping_at >= 3:
                    break
        time.sleep(0.05)
    process.wait()
    return process.returncode, *("".join(parts) for parts in outputs)


class _LiveOutputFormatter:
    def __init__(self):
        self.stream = None
        self.line_start = True

    def feed(self, stream, text):
        if not text:
            return ""
        parts = []
        if stream != self.stream and not self.line_start:
            parts.append("\n")
            self.line_start = True
        self.stream = stream
        for line in text.splitlines(keepends=True):
            if self.line_start:
                parts.append(f"[{stream}] ")
            parts.append(line)
            self.line_start = line.endswith(("\n", "\r"))
        return "".join(parts)


def show_command_window(spec):
    import tkinter as tk
    from tkinter import messagebox, ttk
    from tkinter.scrolledtext import ScrolledText
    from gui_helpers import activate_window, copy_text

    root = tk.Tk()
    root.title(f"Command Output - {spec['title']}")
    root.geometry("900x600")
    root.minsize(480, 320)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    body = ttk.Frame(root, padding=12)
    body.grid(sticky="nsew")
    body.columnconfigure(0, weight=1)
    body.rowconfigure(2, weight=1)
    command = ttk.Entry(body)
    command.insert(0, spec["command"])
    command.configure(state="readonly")
    command.grid(row=0, column=0, sticky="ew")
    status = tk.StringVar(value="Running...")
    ttk.Label(body, textvariable=status).grid(row=1, column=0, sticky="w", pady=8)
    tabs = ttk.Notebook(body)
    tabs.grid(row=2, column=0, sticky="nsew")
    text_views = []
    for name in ("Live Output", "stdout", "stderr"):
        frame = ttk.Frame(tabs)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        text = ScrolledText(frame, wrap="word", font="TkFixedFont", state="disabled")
        text.grid(sticky="nsew")
        text_views.append(text)
        tabs.add(frame, text=name)
    live, *outputs = text_views
    formatter = _LiveOutputFormatter()
    footer = ttk.Frame(body)
    footer.grid(row=3, column=0, sticky="ew", pady=(8, 0))
    footer.columnconfigure(0, weight=1)
    results = queue.Queue(maxsize=128)
    cancel = threading.Event()
    finished = False
    closing = False

    def stop():
        cancel.set()
        status.set("Stopping...")
        stop_button.configure(state="disabled")

    def close():
        nonlocal closing
        if finished:
            root.destroy()
        elif messagebox.askyesno("Stop command", "Stop the running command and close this window?", parent=root):
            closing = True
            stop()

    def worker():
        try:
            result = capture_command(
                spec, cancel, lambda index, text: results.put(("output", index, text)))
            results.put(("done", *result))
        except (OSError, subprocess.SubprocessError) as exc:
            results.put(("output", 1, str(exc)))
            results.put(("done", None, "", str(exc)))

    def copy_outputs():
        stdout, stderr = (widget.get("1.0", "end-1c") for widget in outputs)
        combined = live.get("1.0", "end-1c")
        copy_text(root, f"{status.get()}\n\nLive Output:\n{combined}\n\nstdout:\n{stdout}\n\nstderr:\n{stderr}")

    def poll():
        nonlocal finished
        chunks = [[], []]
        live_chunks = []
        completion = None
        # Batch widget updates and yield to Tk even when a command floods output.
        for _ in range(100):
            try:
                event = results.get_nowait()
            except queue.Empty:
                break
            if event[0] == "output":
                chunks[event[1]].append(event[2])
                live_chunks.append(formatter.feed(("stdout", "stderr")[event[1]], event[2]))
            else:
                completion = event[1:]
                break
        for widget, parts in zip(text_views, (live_chunks, *chunks)):
            if parts:
                at_bottom = widget.yview()[1] >= 0.999
                widget.configure(state="normal")
                widget.insert("end", "".join(parts))
                if at_bottom:
                    widget.see("end")
                widget.configure(state="disabled")
                copy_button.configure(state="normal")
        if completion is None:
            root.after(50, poll)
            return
        code, stdout, stderr = completion
        finished = True
        if closing:
            root.destroy()
            return
        status.set("Stopped" if cancel.is_set() else ("Could not start command" if code is None else f"Exit code: {code}"))
        if stderr and code != 0:
            tabs.select(2)
        stop_button.configure(state="disabled")
        copy_button.configure(state="normal")

    copy_button = ttk.Button(footer, text="Copy All", state="disabled", command=copy_outputs)
    copy_button.grid(row=0, column=0, sticky="w")
    stop_button = ttk.Button(footer, text="Stop", command=stop)
    stop_button.grid(row=0, column=1, padx=8)
    ttk.Button(footer, text="Close", command=close).grid(row=0, column=2)
    root.protocol("WM_DELETE_WINDOW", close)
    root.bind("<Command-w>", lambda event: close())
    root.bind("<Escape>", lambda event: close())
    root.after(100, lambda: threading.Thread(target=worker, daemon=True).start())
    root.after(100, poll)
    activate_window(root)
    root.mainloop()


if __name__ == "__main__":
    show_command_window(json.load(sys.stdin))
