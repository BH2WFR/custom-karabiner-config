"""Literal text pasting without real keyboard events or clipboard changes."""

import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import text_actions as text


class TextTransformTests(unittest.TestCase):
    def test_remaining_transforms_support_unicode(self):
        cases = (
            ('wrap', '\u4e2d\ntext', '${\u4e2d\ntext}'),
            ('lower', '\u00c9L\u00c8VE', '\u00e9l\u00e8ve'),
            ('upper', 'stra\u00dfe', 'STRASSE'),
            ('title', "hELLO wORLD, DON'T", "Hello World, Don't"),
            ('setter', ' myItem\n', 'setMyItem'),
            ('getter', '\u9879\u76ee', 'get\u9879\u76ee'),
        )
        for action, source, expected in cases:
            with self.subTest(action=action):
                self.assertEqual(text.transform_text(action, source), expected)

    def test_removed_inspector_cli_is_rejected(self):
        with patch.object(sys, 'argv', ['text_actions.py', 'stats']), \
             contextlib.redirect_stderr(io.StringIO()), \
             patch.object(text, 'perform_action') as perform:
            with self.assertRaises(SystemExit) as error:
                text.main()
        self.assertEqual(error.exception.code, 2)
        perform.assert_not_called()

    def test_failed_copy_does_not_use_old_clipboard(self):
        board = Mock()
        board.changeCount.return_value = 0
        with patch.object(text, '_frontmost_pid', return_value=123), \
             patch.object(text.clipboard, 'snapshot_pasteboard'), \
             patch.object(text.clipboard, 'send_selection_to_general', return_value=False), \
             patch.object(text, 'read_clipboard_text') as read, \
             patch.object(text.clipboard, 'restore_pasteboard') as restore:
            with self.assertRaisesRegex(ValueError, 'Cannot copy selected text'):
                text.perform_action('lower', board)
        read.assert_not_called()
        restore.assert_not_called()

    def test_transform_restores_clipboard_after_paste(self):
        board = Mock()
        board.changeCount.side_effect = [0, 0, 1, 1, 2, 2]
        board.types.return_value = ['public.utf8-plain-text']
        original = [[('public.html', b'<b>original</b>')]]
        with patch.object(text, '_frontmost_pid', return_value=123), \
             patch.object(text.clipboard, 'snapshot_pasteboard', return_value=original), \
             patch.object(text.clipboard, 'send_selection_to_general', return_value=True), \
             patch.object(text, 'read_clipboard_text', return_value='Hello'), \
             patch.object(text.clipboard, 'restore_pasteboard') as restore, \
             patch.object(text.clipboard, 'post_shortcut', return_value=True), \
             patch.object(text.time, 'sleep'):
            text.perform_action('upper', board)
        self.assertEqual(restore.call_args_list, [
            call(board, text.clipboard.text_snapshot('HELLO')), call(board, original)])


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
             patch.object(text, 'perform_action', return_value=None) as perform:
            self.assertEqual(text.main(), 0)
        perform.assert_called_once_with('newline', factory.generalPasteboard.return_value)


if __name__ == '__main__':
    unittest.main()
