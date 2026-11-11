"""Macro parsing, event sequences and configured shortcuts without key output."""

import contextlib
import io
import json
from pathlib import Path
import shlex
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import keyboard_events as keys
import send_keys as sender


def command_args(command):
    words = shlex.split(command)
    index = next(i for i, word in enumerate(words) if word.endswith('/scripts/send_keys.py'))
    return sender.parse_args(words[index + 1:])


class SenderTests(unittest.TestCase):
    def test_ordered_keys_and_literal_text(self):
        args = sender.parse_args(['--key', 'command+right_arrow', '--text', ';',
                                  '--key', 'shift+f13', '--text', '\u4e2d\U0001f600'])
        self.assertEqual(args.steps, [sender.Step(124, keys.COMMAND_FLAG), sender.Step(0, text=';'),
                                     sender.Step(105, keys.SHIFT_FLAG), sender.Step(0, text='\u4e2d\U0001f600')])

    def test_invalid_commands_rejected_before_events(self):
        for args in ([], ['--key', 'unknown+f13'], ['--key', 'command+unknown'],
                     ['--text', ''], ['--text', '\ud800'], ['--release-key', 'unknown']):
            with self.subTest(args=args), patch.object(keys, 'post_keystroke') as post, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    sender.main(args)
                post.assert_not_called()

    def test_permission_failure_sends_nothing(self):
        with patch.object(keys, 'can_post_events', return_value=False), patch.object(keys, 'release_modifiers') as release:
            with self.assertRaises(RuntimeError):
                sender.send_sequence([sender.Step(105)])
            release.assert_not_called()

    def test_one_ordered_sequence_clears_trigger_then_sends(self):
        calls = []
        with patch.object(keys, 'can_post_events', return_value=True), \
             patch.object(sender.fcntl, 'flock'), patch.object(sender.time, 'sleep'), \
             patch.object(keys, 'release_modifiers', side_effect=lambda: calls.append('release modifiers')), \
             patch.object(keys, 'release_keys', side_effect=lambda code: calls.append(('release', code))), \
             patch.object(keys, 'post_keystroke', side_effect=lambda *a, **kw: calls.append((a, kw))):
            sender.send_sequence([sender.Step(124, keys.COMMAND_FLAG), sender.Step(0, text=':')],
                                 inherited_flags=keys.OPTION_FLAG, trigger_code=41)
        self.assertEqual(calls, ['release modifiers', ('release', 41),
                                ((124, keys.COMMAND_FLAG | keys.OPTION_FLAG), {'unicode_text': None}),
                                ((0, 0), {'unicode_text': ':'})])

    def test_inherited_modifiers_exclude_consumed_shift_and_side_bits(self):
        with patch.object(keys, 'current_modifier_flags', return_value=keys.COMMAND_FLAG | keys.SHIFT_FLAG | 0xA), \
             patch.object(sender, 'send_sequence') as send:
            self.assertEqual(sender.main(['--inherit-modifiers', '--exclude-modifiers', 'shift',
                                          '--release-key', 'quote', '--key', 'command+right_arrow', '--text', ':']), 0)
        self.assertEqual(send.call_args.kwargs, {'inherited_flags': keys.COMMAND_FLAG, 'trigger_code': 39})


class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads((Path(__file__).resolve().parents[1] / 'karabiner.json').read_text(encoding='utf-8'))
        cls.rules = next(p for p in data['profiles'] if p['name'] == 'ZL')['complex_modifications']['rules']

    def test_all_commands_parse_and_no_mixed_native_macros_remain(self):
        count = 0
        for rule in self.rules:
            for m in rule['manipulators']:
                for field in ('to', 'to_after_key_up'):
                    events = m.get(field, [])
                    if not rule['description'].startswith(('[Map', '[Layer')):
                        self.assertFalse(any('key_code' in e for e in events), rule['description'])
                    for event in events:
                        command = event.get('shell_command', '')
                        if 'release_shift.py' in command:
                            self.assertTrue(any('mouse_key' in e for e in events), rule['description'])
                        if '/scripts/send_keys.py' in command:
                            command_args(command)
                            self.assertEqual(len(events), 1)
                            count += 1
        self.assertEqual(count, 34)

    def test_anki_chords_remain_distinct(self):
        rule = next(r for r in self.rules if r['description'].startswith('[Anki]'))
        expected = {
            ('q', False): (15, keys.COMMAND_FLAG),
            ('w', False): (105, keys.COMMAND_FLAG | keys.CONTROL_FLAG),
            ('e', False): (105, keys.OPTION_FLAG), ('e', True): (105, keys.CONTROL_FLAG),
            ('r', False): (105, keys.COMMAND_FLAG | keys.OPTION_FLAG),
            ('t', False): (105, keys.COMMAND_FLAG | keys.OPTION_FLAG | keys.SHIFT_FLAG),
            ('a', False): (105, keys.CONTROL_FLAG | keys.COMMAND_FLAG | keys.SHIFT_FLAG),
            ('a', True): (105, keys.CONTROL_FLAG | keys.COMMAND_FLAG | keys.OPTION_FLAG),
            ('s', False): (105, keys.OPTION_FLAG | keys.CONTROL_FLAG),
            ('s', True): (105, keys.OPTION_FLAG | keys.CONTROL_FLAG | keys.SHIFT_FLAG),
            ('d', False): (105, keys.COMMAND_FLAG | keys.SHIFT_FLAG),
            ('d', True): (105, keys.CONTROL_FLAG | keys.SHIFT_FLAG),
            ('f', False): (105, 0), ('g', False): (105, keys.COMMAND_FLAG),
            ('g', True): (105, keys.SHIFT_FLAG),
        }
        actual = {}
        for m in rule['manipulators']:
            args = command_args(m['to'][0]['shell_command'])
            shifted = 'shift' in m['from'].get('modifiers', {}).get('mandatory', [])
            self.assertEqual(len(args.steps), 1)
            actual[(m['from']['key_code'], shifted)] = args.steps[0][:2]
        self.assertEqual(actual, expected)

    def test_end_of_line_punctuation_uses_unicode(self):
        for rule in self.rules:
            if 'Semicolon' not in rule['description'] and 'Caps+Quote' not in rule['description']:
                continue
            for m in rule['manipulators']:
                args = command_args(m['to'][0]['shell_command'])
                expected = ':' if m['from']['key_code'] == 'quote' or m['from'].get('modifiers', {}).get('mandatory') else ';'
                self.assertEqual(args.steps, [sender.Step(124, keys.COMMAND_FLAG), sender.Step(0, text=expected)])

    def test_caps_q_preserves_extra_modifiers(self):
        rule = next(r for r in self.rules if r['description'].startswith('Caps+A ->'))
        m = next(m for m in rule['manipulators'] if m['from']['key_code'] == 'q')
        args = command_args(m['to'][0]['shell_command'])
        self.assertTrue(args.inherit_modifiers)
        self.assertEqual(args.steps, [sender.Step(keys.ESCAPE_KEY_CODE)])

    def test_comma_and_backslash_at_end_of_line(self):
        rule = next(r for r in self.rules if r['description'].startswith('Caps+(Shift)+Comma'))
        self.assertEqual(len(rule['manipulators']), 2)
        for m, shifted in zip(rule['manipulators'], (True, False)):
            self.assertEqual(m['conditions'], [
                {'name': 'caps_primary_layer', 'type': 'variable_if', 'value': 1}])
            self.assertEqual(m['from']['key_code'], 'comma')
            self.assertEqual(m['from'].get('modifiers', {}).get('mandatory', []),
                             ['shift'] if shifted else [])
            args = command_args(m['to'][0]['shell_command'])
            self.assertEqual(args.release_key, 'comma')
            self.assertEqual(keys.KEY_CODES[args.release_key], 43)
            self.assertFalse(args.inherit_modifiers)
            self.assertEqual(args.steps, [sender.Step(124, keys.COMMAND_FLAG),
                                         sender.Step(0, text='\\' if shifted else ',')])

    def test_secondary_newline_precedes_primary_return(self):
        matches = [m for r in self.rules for m in r['manipulators']
                   if m['from'].get('key_code') == 'return_or_enter']
        m = matches[0]
        self.assertEqual(m['conditions'], [
            {'name': 'caps_primary_layer', 'type': 'variable_if', 'value': 1},
            {'name': 'caps_secondary_layer', 'type': 'variable_if', 'value': 1}])
        self.assertEqual(shlex.split(m['to'][0]['shell_command'])[-1], 'newline')
        self.assertIn('/scripts/text_actions.py', m['to'][0]['shell_command'])
        self.assertFalse(m['to'][0]['repeat'])

    def test_caps_7_launches_external_unicode_inspector(self):
        matches = [m for rule in self.rules for m in rule['manipulators']
                   if m['from'].get('key_code') == '7'
                   and not m['from'].get('modifiers', {}).get('mandatory')]
        self.assertEqual(len(matches), 1)
        m = matches[0]
        self.assertIn({'name': 'caps_primary_layer', 'type': 'variable_if', 'value': 1},
                      m['conditions'])
        self.assertFalse(m['to'][0]['repeat'])
        command = shlex.split(m['to'][0]['shell_command'])
        self.assertEqual(command, [
            '/opt/miniconda3/bin/python3', '${HOME}/.config/karabiner/scripts/launch_unicode_inspector.py',
            '--inspector', '${HOME}/gitRepo/PersonalScripts/tools/others/unicode-inspector.py'])
        self.assertNotIn('text_actions.py stats', json.dumps(self.rules))


if __name__ == '__main__':
    unittest.main()
