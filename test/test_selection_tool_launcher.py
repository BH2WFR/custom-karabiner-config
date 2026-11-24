"""Test selection tool launches without sending input or touching a real clipboard."""

import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import launch_selection_tool as launcher


class LauncherTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.board = stack.enter_context(patch.object(launcher.clipboard, 'NSPasteboard')).generalPasteboard.return_value
        self.board.types.return_value = [launcher.clipboard.TEXT_TYPE]
        self.board.stringForType_.return_value = '--clip\n雪😀\x00'
        self.copy = stack.enter_context(patch.object(launcher.clipboard, 'send_selection_to_general', return_value=True))
        self.permission = stack.enter_context(patch.object(launcher.keys, 'can_post_events', return_value=True))
        self.pid = stack.enter_context(patch.object(launcher, '_frontmost_pid', return_value=123))
        self.run = stack.enter_context(patch.object(launcher.subprocess, 'run'))
        self.notify = stack.enter_context(patch.object(launcher, 'notify'))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def check_launch(self, *args, tool='--inspector'):
        script = str(Path(__file__).resolve())
        self.assertEqual(launcher.main([tool, script]), 0)
        self.run.assert_called_once_with([
            '/usr/bin/open', '-n', '-a', str(Path(sys.prefix) / 'python.app'),
            '--env', f'PYTHONEXECUTABLE={sys.executable}', '--args', script, *args,
        ], check=True)
        self.board.clearContents.assert_not_called()

    def test_copied_text_opens_with_clip(self):
        self.check_launch('--clip')
        self.copy.assert_called_once_with(self.board, launcher.keys.C_KEY_CODE)
        self.notify.assert_not_called()

    def test_failed_copy_ignores_old_clipboard(self):
        self.copy.return_value = False
        self.check_launch()
        self.board.stringForType_.assert_not_called()

    def test_processor_copies_files_then_loads_clipboard(self):
        self.board.types.return_value = ['public.file-url']
        self.run.side_effect = lambda *args, **kwargs: self.copy.assert_called_once_with(self.board, launcher.keys.C_KEY_CODE)
        self.check_launch('--clip', tool='--processor')
        self.board.stringForType_.assert_not_called()

    def test_processor_without_selection_loads_existing_clipboard(self):
        self.copy.return_value = False
        self.check_launch('--clip', tool='--processor')
        self.notify.assert_not_called()

    def test_empty_text_opens_blank(self):
        self.board.stringForType_.return_value = ''
        self.check_launch()

    def test_file_selection_opens_blank(self):
        self.board.types.return_value = ['public.file-url', launcher.clipboard.TEXT_TYPE]
        self.check_launch()

    def test_focus_change_opens_blank(self):
        self.pid.side_effect = [123, 456]
        self.check_launch()

    def test_permission_failure_opens_blank(self):
        self.permission.return_value = False
        self.check_launch()
        self.copy.assert_not_called()

    def test_busy_clipboard_operation_opens_blank(self):
        with patch.object(launcher.fcntl, 'flock', side_effect=BlockingIOError):
            self.check_launch()
        self.copy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
