"""External inspector handoff without real input, clipboard access or windows."""

import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import launch_unicode_inspector as launcher


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.board = Mock()
        self.board.changeCount.side_effect = [0, 0, 1, 1, 1]
        self.board.types.return_value = ['public.utf8-plain-text']
        self.original = [[('public.html', b'<b>original</b>'), ('public.png', b'image')]]
        self.stack.enter_context(patch.object(launcher.keys, 'can_post_events', return_value=True))
        self.pid = self.stack.enter_context(patch.object(launcher, '_frontmost_pid', return_value=123))
        self.stack.enter_context(patch.object(launcher.clipboard, 'snapshot_pasteboard', return_value=self.original))
        self.copy = self.stack.enter_context(patch.object(launcher.clipboard, 'send_selection_to_general', return_value=True))
        self.read = self.stack.enter_context(patch.object(launcher, 'read_clipboard_text', return_value=' A\n\U0001f600\x00'))
        self.restore = self.stack.enter_context(patch.object(launcher.clipboard, 'restore_pasteboard'))

    def test_selection_is_verbatim_and_all_formats_restored(self):
        self.assertEqual(launcher.capture_selection(self.board), ' A\n\U0001f600\x00')
        self.copy.assert_called_once_with(self.board, launcher.keys.C_KEY_CODE)
        self.restore.assert_called_once_with(self.board, self.original)

    def test_failed_copy_does_not_read_old_clipboard(self):
        self.copy.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'Cannot copy'):
            launcher.capture_selection(self.board)
        self.read.assert_not_called()
        self.restore.assert_not_called()

    def test_empty_selection_restores_clipboard(self):
        self.read.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'contains no text'):
            launcher.capture_selection(self.board)
        self.restore.assert_called_once_with(self.board, self.original)

    def test_newer_clipboard_is_not_overwritten(self):
        self.board.changeCount.side_effect = [0, 0, 1, 2, 2]
        with self.assertRaisesRegex(RuntimeError, 'Clipboard changed'):
            launcher.capture_selection(self.board)
        self.restore.assert_not_called()

    def test_focus_change_cancels_and_restores(self):
        self.pid.side_effect = [123, 456]
        with self.assertRaisesRegex(RuntimeError, 'application changed'):
            launcher.capture_selection(self.board)
        self.restore.assert_called_once_with(self.board, self.original)

    def test_file_selection_is_not_inspected_as_text(self):
        self.board.types.return_value = ['public.file-url']
        with self.assertRaisesRegex(RuntimeError, 'files, not text'):
            launcher.capture_selection(self.board)
        self.read.assert_not_called()
        self.restore.assert_called_once_with(self.board, self.original)


class LauncherTests(unittest.TestCase):
    def test_handoff_keeps_text_off_command_line(self):
        selected = 'A\x00\U0001f600\n' * 100000
        with patch.object(launcher.clipboard, 'NSPasteboard') as factory, \
             patch.object(launcher, 'capture_selection', return_value=selected), \
             patch.object(launcher.clipboard, 'restore_pasteboard') as restore, \
             patch.object(launcher.subprocess, 'run') as run:
            board = factory.pasteboardWithUniqueName.return_value
            board.name.return_value = 'transfer-board'
            launcher.launch_inspector(Path('/repo with spaces/unicode-inspector.py'), launcher.prepare_transfer())
        restore.assert_called_once_with(board, launcher.clipboard.text_snapshot(selected))
        run.assert_called_once_with([
            '/usr/bin/open', '-g', '-n', '-a', str(Path(sys.prefix) / 'python.app'),
            '--env', f'PYTHONEXECUTABLE={sys.executable}', '--args',
            '/repo with spaces/unicode-inspector.py', '--consume-pasteboard', 'transfer-board',
        ], check=True)
        board.releaseGlobally.assert_not_called()

    def test_blank_launch_opens_script_without_transfer_board(self):
        with patch.object(launcher.clipboard, 'NSPasteboard') as factory, \
             patch.object(launcher.subprocess, 'run') as run:
            launcher.launch_inspector(Path('/inspector.py'), None)
        self.assertEqual(run.call_args.args[0][-2:], ['--args', '/inspector.py'])
        factory.pasteboardWithUniqueName.assert_not_called()

    def test_failed_launch_releases_transfer_board(self):
        board = Mock()
        with patch.object(launcher.subprocess, 'run', side_effect=OSError('launch failed')):
            with self.assertRaises(OSError):
                launcher.launch_inspector(Path('/inspector.py'), board)
        board.releaseGlobally.assert_called_once()

    def test_preparation_failure_still_opens_blank_inspector(self):
        for stage in ('lock', 'copy', 'transfer'):
            with self.subTest(stage=stage), \
                 patch.object(launcher.clipboard, 'NSPasteboard') as factory, \
                 patch.object(launcher.fcntl, 'flock') as lock, \
                 patch.object(launcher, 'capture_selection', return_value='selected') as copy, \
                 patch.object(launcher.clipboard, 'restore_pasteboard') as transfer, \
                 patch.object(launcher.subprocess, 'run') as run, \
                 patch.object(launcher, 'notify') as notify, \
                 contextlib.redirect_stderr(io.StringIO()):
                operation = {'lock': lock, 'copy': copy, 'transfer': transfer}[stage]
                operation.side_effect = RuntimeError(f'{stage} failed.')
                result = launcher.main(['--inspector', __file__])
                self.assertEqual(result, 0)
                self.assertEqual(run.call_args.args[0][-2:], ['--args', str(Path(__file__).resolve())])
                notify.assert_called_once_with(f'{stage} failed. Paste or enter text manually.', level='error')
                if stage == 'transfer':
                    factory.pasteboardWithUniqueName.return_value.releaseGlobally.assert_called_once()


if __name__ == '__main__':
    unittest.main()
