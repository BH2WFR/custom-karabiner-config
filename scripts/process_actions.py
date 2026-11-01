"""Process identity checks and argument-preserving restart operations.

Callers must obtain UI confirmation before kill/restart. No shell is involved.
"""

import os
import subprocess
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class RestartPlan:
    executable: str
    argv: tuple[str, ...]
    cwd: str
    environment: dict[str, str]


class ProcessTarget:
    def __init__(self, pid):
        self.process = psutil.Process(pid)
        self.pid = pid
        self.created = self.process.create_time()

    def checked(self):
        process = self.process
        if not process.is_running() or psutil.Process(self.pid).create_time() != self.created:
            raise RuntimeError("The original process has exited. Capture a new target.")
        if process.status() == psutil.STATUS_ZOMBIE:
            raise RuntimeError("The original process has exited.")
        return process

    def actionable(self):
        process = self.checked()
        if self.pid <= 1 or self.pid == os.getpid():
            raise RuntimeError("Cannot terminate this process from the inspector.")
        return process

    def prepare_restart(self):
        process = self.actionable()
        executable = process.exe()
        argv = tuple(process.cmdline())
        cwd = process.cwd()
        environment = process.environ()
        if not argv or not executable or not os.access(executable, os.X_OK):
            raise RuntimeError("Cannot read a complete command or execute the target binary.")
        if not cwd or not os.path.isdir(cwd):
            raise RuntimeError("The original working directory is unavailable.")
        self.checked()
        return RestartPlan(executable, argv, cwd, environment)

    def kill(self):
        process = self.actionable()
        process.kill()
        process.wait(timeout=5)

    def restart(self, plan, timeout=5):
        process = self.actionable()
        if (process.exe() != plan.executable or tuple(process.cmdline()) != plan.argv
                or process.cwd() != plan.cwd):
            raise RuntimeError("The process command changed. Review and confirm it again.")
        if not os.access(plan.executable, os.X_OK) or not os.path.isdir(plan.cwd):
            raise RuntimeError("The executable or working directory is no longer available.")
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except psutil.TimeoutExpired:
            raise RuntimeError(
                "The process did not exit. Restart cancelled; no second process was started."
            ) from None
        try:
            return subprocess.Popen(
                list(plan.argv), executable=plan.executable, cwd=plan.cwd,
                env=plan.environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise RuntimeError(f"The old process exited, but relaunch failed: {exc}") from exc
