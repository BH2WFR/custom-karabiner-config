"""External inspector handoff without real input, clipboard access or windows."""

import contextlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
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
             patch.object(launcher.clipboard, 'restore_pasteboard') as restore, \
             patch.object(launcher.subprocess, 'run') as run:
            run.return_value.returncode = 0
            launcher.launch_inspector(Path('/repo with spaces/unicode-inspector.py'), selected)
        payload = json.loads(restore.call_args.args[1][0][0][1].decode('utf-8'))
        self.assertEqual(payload, {'text': selected, 'error': None})
        command = run.call_args.args[0]
        self.assertNotIn(selected, command)
        self.assertIn('/repo with spaces/unicode-inspector.py', command)
        self.assertEqual(command[-2], '--pasteboard')
        factory.pasteboardWithName_.return_value.releaseGlobally.assert_not_called()

    def test_failed_launch_releases_transfer_board(self):
        with patch.object(launcher.clipboard, 'NSPasteboard') as factory, \
             patch.object(launcher.clipboard, 'restore_pasteboard'), \
             patch.object(launcher.subprocess, 'run', side_effect=OSError('launch failed')):
            with self.assertRaises(OSError):
                launcher.launch_inspector(Path('/inspector.py'), 'selected')
        factory.pasteboardWithName_.return_value.releaseGlobally.assert_called_once()

    def test_main_restores_selection_before_launch_and_defers_error(self):
        for failure in (None, RuntimeError('Cannot copy selected text.')):
            with self.subTest(failure=failure), \
                 patch.object(launcher.clipboard, 'NSPasteboard'), \
                 patch.object(launcher, 'capture_selection', return_value='selected', side_effect=failure), \
                 patch.object(launcher, 'launch_inspector') as launch, \
                 patch.object(launcher, 'notify') as notify, \
                 contextlib.redirect_stderr(io.StringIO()):
                result = launcher.main(['--inspector', __file__])
                self.assertEqual(result, 0)
                launch.assert_called_once_with(
                    Path(__file__).resolve(), '' if failure else 'selected',
                    f'{failure} Paste or enter text manually.' if failure else None)
                notify.assert_not_called()

    def test_external_ui_receives_selection_then_shows_tooltip(self):
        with patch.object(launcher.clipboard, 'NSPasteboard') as factory, \
             patch.object(launcher.runpy, 'run_path') as load, \
             patch('tkinter.Tk') as tk, \
             patch.object(launcher, 'activate_window'), \
             patch.object(launcher.subprocess, 'Popen') as popen:
            factory.pasteboardWithName_.return_value.stringForType_.return_value = json.dumps(
                {'text': '', 'error': 'Copy failed'})
            inspector = Mock()
            load.return_value = {'UnicodeInspector': inspector}
            root = tk.return_value

            def mainloop():
                inspector.assert_called_once_with(root, '')
                factory.pasteboardWithName_.return_value.releaseGlobally.assert_called_once()
                popen.assert_not_called()
                root.bind.call_args.args[1](SimpleNamespace(widget=root))
                popen.assert_not_called()
                root.after_idle.call_args.args[0]()

            root.mainloop.side_effect = mainloop
            launcher.run_inspector(Path('/external.py'), 'private.test')
            load.assert_called_once_with('/external.py')
            popen.assert_called_once()
            self.assertEqual(popen.call_args.args[0][-3:], ['Copy failed', '--level', 'error'])
            root.destroy.assert_called_once()


if __name__ == '__main__':
    unittest.main()
