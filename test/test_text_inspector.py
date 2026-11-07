"""Inspector recovery without real keyboard input, clipboard access or GUI windows."""

import contextlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import text_actions as text


class InspectorRecoveryTests(unittest.TestCase):
    def run_action(self, action, *, error=None, permission=True):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'argv', ['text_actions.py', action]))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            stack.enter_context(patch.object(text.fcntl, 'flock'))
            stack.enter_context(patch.object(text.keys, 'can_post_events', return_value=permission))
            stack.enter_context(patch.object(text.clipboard, 'NSPasteboard'))
            perform = stack.enter_context(patch.object(
                text, 'perform_action', side_effect=error,
                return_value=text.inspect_text('A\U0001f600')))
            notify = stack.enter_context(patch.object(text, 'notify'))
            launch = stack.enter_context(patch.object(text, 'launch_inspector'))
            result = text.main()
        return result, perform, notify, launch

    def test_copy_failures_open_blank_inspector_with_error(self):
        for error in (RuntimeError('No text copied. Select text to inspect.'),
                      RuntimeError('Clipboard is empty or contains no text.'),
                      ValueError('The selection contains files, not text.')):
            with self.subTest(error=str(error)):
                result, _, notify, launch = self.run_action('stats', error=error)
                self.assertEqual(result, 0)
                notify.assert_not_called()
                launch.assert_called_once_with(
                    '', error_message=f'{error} Paste or enter text manually.')

    def test_missing_permission_still_allows_manual_input(self):
        result, perform, notify, launch = self.run_action('stats', permission=False)
        self.assertEqual(result, 0)
        perform.assert_not_called()
        notify.assert_not_called()
        launch.assert_called_once_with('', error_message=(
            'Python needs Accessibility permission for text actions. Paste or enter text manually.'))

    def test_success_uses_selected_text(self):
        result, _, notify, launch = self.run_action('stats')
        self.assertEqual(result, 0)
        notify.assert_not_called()
        launch.assert_called_once_with('A\U0001f600', error_message=None)

    def test_transform_failure_does_not_open_inspector(self):
        result, _, notify, launch = self.run_action('lower', error=ValueError('No text.'))
        self.assertEqual(result, 1)
        notify.assert_called_once_with('No text.', level='warning')
        launch.assert_not_called()

    def test_non_text_selection_restores_original_clipboard(self):
        board = Mock()
        board.changeCount.side_effect = [0, 0, 1, 1, 1]
        board.types.return_value = ['public.png']
        original = [[('public.html', b'<b>original</b>')]]
        with patch.object(text, '_frontmost_pid', return_value=123), \
             patch.object(text.clipboard, 'snapshot_pasteboard', return_value=original), \
             patch.object(text.clipboard, 'send_selection_to_general', return_value=True), \
             patch.object(text, 'read_clipboard_text', return_value=None), \
             patch.object(text.clipboard, 'restore_pasteboard') as restore, \
             patch.object(text.clipboard, 'post_shortcut') as post:
            with self.assertRaisesRegex(RuntimeError, 'Clipboard is empty'):
                text.perform_action('stats', board)
            restore.assert_called_once_with(board, original)
            post.assert_not_called()

    def test_failed_copy_does_not_read_or_replace_old_clipboard(self):
        board = Mock()
        board.changeCount.return_value = 0
        with patch.object(text, '_frontmost_pid', return_value=123), \
             patch.object(text.clipboard, 'snapshot_pasteboard'), \
             patch.object(text.clipboard, 'send_selection_to_general', return_value=False), \
             patch.object(text, 'read_clipboard_text') as read, \
             patch.object(text.clipboard, 'restore_pasteboard') as restore:
            with self.assertRaisesRegex(RuntimeError, 'No text copied'):
                text.perform_action('stats', board)
            read.assert_not_called()
            restore.assert_not_called()

    def test_empty_launch_uses_private_pasteboard(self):
        with patch.object(text, '_inspector_pasteboard') as factory, \
             patch.object(text.clipboard, 'restore_pasteboard') as restore, \
             patch.object(text.subprocess, 'run') as run:
            run.return_value.returncode = 0
            text.launch_inspector('', error_message='Copy failed')
        restore.assert_called_once_with(factory.return_value, text.clipboard.text_snapshot(''))
        self.assertTrue(factory.call_args.args[0].startswith(text.INSPECTOR_PASTEBOARD_PREFIX))
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][-2:], ['--inspector-error', 'Copy failed'])

    def test_empty_window_and_missing_transfer_data(self):
        for value in ('', None, 'A\U0001f600'):
            with self.subTest(value=value), \
                 patch.object(text, '_inspector_pasteboard') as factory, \
                 patch.object(text, 'show_inspector') as show, \
                 patch.object(text, 'notify') as notify:
                board = factory.return_value
                board.stringForType_.return_value = value
                text.run_inspector('private.test')
                message = 'Cannot read inspector text. Paste or enter text manually.' if value is None else None
                show.assert_called_once_with(text.inspect_text(value or ''), error_message=message)
                board.releaseGlobally.assert_called_once()
                notify.assert_not_called()

    def test_tooltip_starts_only_after_window_is_visible(self):
        with patch('tkinter.Tk') as factory, \
             patch.object(text, 'build_inspector_window'), \
             patch.object(text, 'activate_window'), \
             patch.object(text.subprocess, 'Popen') as popen:
            root = factory.return_value
            text.show_inspector(text.inspect_text(''), error_message='Copy failed')
            popen.assert_not_called()
            root.mainloop.assert_called_once()
            on_visible = root.bind.call_args.args[1]
            on_visible(SimpleNamespace(widget=object()))
            root.after_idle.assert_not_called()
            on_visible(SimpleNamespace(widget=root))
            root.unbind.assert_called_once_with('<Map>', root.bind.return_value)
            popen.assert_not_called()
            root.after_idle.call_args.args[0]()
            popen.assert_called_once()
            self.assertEqual(popen.call_args.args[0][-3:], ['Copy failed', '--level', 'error'])

    def test_successful_window_does_not_schedule_tooltip(self):
        with patch('tkinter.Tk') as factory, \
             patch.object(text, 'build_inspector_window'), \
             patch.object(text, 'activate_window'), \
             patch.object(text.subprocess, 'Popen') as popen:
            text.show_inspector(text.inspect_text('selected text'))
            factory.return_value.bind.assert_not_called()
            popen.assert_not_called()

    def test_failed_launch_releases_private_pasteboard(self):
        with patch.object(text, '_inspector_pasteboard') as factory, \
             patch.object(text.clipboard, 'restore_pasteboard'), \
             patch.object(text.subprocess, 'run') as run:
            run.return_value.returncode = 1
            run.return_value.stderr = 'Launch failed'
            with self.assertRaisesRegex(RuntimeError, 'Launch failed'):
                text.launch_inspector('')
            factory.return_value.releaseGlobally.assert_called_once()


if __name__ == '__main__':
    unittest.main()
