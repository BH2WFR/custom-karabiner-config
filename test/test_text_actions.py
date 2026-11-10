"""Literal text pasting without real keyboard events or clipboard changes."""

import contextlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import text_actions as text


class LiteralPasteTests(unittest.TestCase):
    def test_literal_actions_do_not_require_source_text(self):
        for action, expected in (('tab', '\t'), ('newline', '\n')):
            for source in (None, '', 'ignored'):
                self.assertEqual(text.transform_text(action, source), expected)

    def test_literal_paste_restores_all_formats_or_empty_clipboard(self):
        for action, expected in (('tab', '\t'), ('newline', '\n')):
            for original in ([], [[('public.png', b'image'), ('public.html', b'<b>text</b>')]]):
                with self.subTest(action=action, original=original), contextlib.ExitStack() as stack:
                    board = Mock()
                    board.changeCount.side_effect = [10, 10, 10, 11, 11]
                    stack.enter_context(patch.object(text, '_frontmost_pid', return_value=123))
                    stack.enter_context(patch.object(text.clipboard, 'snapshot_pasteboard', return_value=original))
                    restore = stack.enter_context(patch.object(text.clipboard, 'restore_pasteboard'))
                    copy = stack.enter_context(patch.object(text.clipboard, 'send_selection_to_general'))
                    read = stack.enter_context(patch.object(text, 'read_clipboard_text'))
                    post = stack.enter_context(patch.object(text.clipboard, 'post_shortcut', return_value=True))
                    stack.enter_context(patch.object(text.time, 'sleep'))
                    self.assertIsNone(text.perform_action(action, board))
                    read.assert_not_called()
                    copy.assert_not_called()
                    post.assert_called_once_with(text.keys.V_KEY_CODE)
                    self.assertEqual(restore.call_args_list, [
                        call(board, text.clipboard.text_snapshot(expected)), call(board, original)])

    def test_newline_does_not_overwrite_newer_clipboard(self):
        board = Mock()
        board.changeCount.side_effect = [10, 10, 10, 11, 12]
        with patch.object(text, '_frontmost_pid', return_value=123), \
             patch.object(text.clipboard, 'snapshot_pasteboard'), \
             patch.object(text.clipboard, 'restore_pasteboard') as restore, \
             patch.object(text.clipboard, 'post_shortcut', return_value=True), \
             patch.object(text.time, 'sleep'):
            text.perform_action('newline', board)
        restore.assert_called_once_with(board, text.clipboard.text_snapshot('\n'))

    def test_newline_cli_is_accepted(self):
        with patch.object(sys, 'argv', ['text_actions.py', 'newline']), \
             patch.object(text.keys, 'can_post_events', return_value=True), \
             patch.object(text.clipboard, 'NSPasteboard') as factory, \
             patch.object(text, 'perform_action', return_value=None) as perform, \
             patch.object(text, 'launch_inspector') as launch:
            self.assertEqual(text.main(), 0)
        perform.assert_called_once_with('newline', factory.generalPasteboard.return_value)
        launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
