"""Modifier state, event routing and ZL layer regressions with mocked output."""

import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import keyboard_events as events
import test_keyboard as keyboard


class KeyboardTests(unittest.TestCase):
    def setUp(self):
        self.post = patch.object(keyboard, 'post_key_event').start()
        self.variables = patch.object(keyboard, 'set_caps_layer').start()
        patch.object(keyboard, 'current_modifier_flags', return_value=0).start()
        self.addCleanup(patch.stopall)
        self.state = keyboard.KeyboardState()

    def test_caps_is_variable_only(self):
        self.assertEqual(keyboard.CAPS_VARIABLE, 'caps_primary_layer')
        self.assertTrue(self.state.toggle('Caps'))
        self.variables.assert_called_with(True)
        self.assertFalse(self.state.toggle('Caps'))
        self.variables.assert_called_with(False)
        self.post.assert_not_called()

    def test_each_modifier_press_and_release(self):
        for name, (code, generic, side) in events.MODIFIER_KEYS.items():
            with self.subTest(name=name):
                self.assertTrue(self.state.toggle(name))
                self.post.assert_called_with(code, True, generic | side, flags_changed=True, event_tap=events.HID_EVENT_TAP)
                self.assertFalse(self.state.toggle(name))
                self.post.assert_called_with(code, False, 0, flags_changed=True, event_tap=events.HID_EVENT_TAP)

    def test_left_and_right_shift(self):
        self.state.toggle('LShift')
        self.state.toggle('RShift')
        self.state.toggle('LShift')
        self.assertEqual(self.state.flags(), events.SHIFT_FLAG | 0x4)

    def test_order_and_close(self):
        self.state.toggle('Caps')
        self.state.toggle('LOpt')
        self.state.toggle('RShift')
        self.post.reset_mock()
        self.state.release()
        self.assertEqual([c.args[:2] for c in self.post.call_args_list], [(60, False), (58, False)])
        self.assertFalse(self.state.caps)
        self.assertEqual(self.state.held, [])
        self.variables.assert_called_with(False)

    def test_post_failure_rolls_back(self):
        self.post.side_effect = RuntimeError('failed')
        with self.assertRaises(RuntimeError):
            self.state.toggle('LOpt')
        self.assertEqual(self.state.held, [])

    def test_caps_failure_rolls_back(self):
        self.variables.side_effect = RuntimeError('failed')
        with self.assertRaises(RuntimeError):
            self.state.toggle('Caps')
        self.assertFalse(self.state.caps)

    def test_cleanup_continues_on_failure(self):
        self.state.toggle('Caps')
        self.state.toggle('LOpt')
        self.state.toggle('LShift')
        self.post.side_effect = [RuntimeError('failed'), None]
        with self.assertRaises(RuntimeError):
            self.state.release()
        self.variables.assert_called_with(False)
        self.assertEqual(self.state.held, ['LShift'])

    def test_flags_formatting(self):
        self.assertEqual(events.format_modifier_flags(0), 'None')
        self.assertEqual(events.format_modifier_flags(events.OPTION_FLAG | events.SHIFT_FLAG), 'Opt + Shift')

    def test_side_flags_are_not_inferred_from_key_state(self):
        for name, (_, generic, side) in events.MODIFIER_KEYS.items():
            with self.subTest(name=name):
                self.assertEqual(events.format_modifier_flags(generic | side, include_sides=True), name)
        self.assertEqual(events.format_modifier_flags(events.COMMAND_FLAG, include_sides=True), 'Cmd (side unavailable)')
        self.assertEqual(events.format_modifier_flags(0x10, include_sides=True), 'None')
        self.assertEqual(events.format_modifier_flags(events.SHIFT_FLAG | 0x6, include_sides=True), 'LShift + RShift')

    def test_diagnostic_mapping(self):
        data = json.loads((keyboard.ROOT / 'karabiner.json').read_text(encoding='utf-8'))
        profile = next(p for p in data['profiles'] if p['name'] == 'ZL')
        rule = profile['complex_modifications']['rules'][0]['manipulators'][0]
        self.assertEqual(rule['from'], {'key_code': '1', 'modifiers': {'optional': ['any']}})
        self.assertEqual(rule['conditions'][0], {'type': 'variable_if', 'name': 'caps_primary_layer', 'value': 1})
        self.assertFalse(rule['to'][0]['repeat'])
        self.assertEqual(rule['conditions'][1], {'type':'variable_if', 'name':'caps_secondary_layer', 'value':1})
        self.assertTrue(rule['to'][0]['shell_command'].endswith('--layer secondary'))
        fallback = profile['complex_modifications']['rules'][0]['manipulators'][1]
        self.assertTrue(fallback['to'][0]['shell_command'].endswith('--layer primary'))

    def test_release_without_screen_caps_does_not_clear_physical_layer(self):
        self.state.release()
        self.state.toggle('LShift')
        self.state.release()
        self.variables.assert_not_called()

    def test_repeated_release_clears_layer_only_once(self):
        self.state.toggle('Caps')
        self.variables.reset_mock()
        self.state.release()
        self.state.release()
        self.variables.assert_called_once_with(False)


class SecondaryTriggerTests(unittest.TestCase):
    def setUp(self):
        data = json.loads((keyboard.ROOT / 'karabiner.json').read_text(encoding='utf-8'))
        profile = next(p for p in data['profiles'] if p['name'] == 'ZL')
        self.rules = profile['complex_modifications']['rules']

    def test_lcmd_trigger_matches_lopt_and_precedes_normal_mapping(self):
        entry = next(r for r in self.rules if r['description'].startswith('[Layer][Non-RDP]: Caps+'))
        triggers = {m['from']['key_code']: m for m in entry['manipulators']}
        self.assertEqual(set(triggers), {'left_option', 'right_command', 'left_command'})
        expected = json.loads(json.dumps(triggers['left_option']))
        expected['from']['key_code'] = 'left_command'
        self.assertEqual(triggers['left_command'], expected)
        self.assertIn({'type': 'variable_if', 'name': 'caps_primary_layer', 'value': 1}, expected['conditions'])
        self.assertTrue(any(c['type'] == 'frontmost_application_unless' for c in expected['conditions']))
        self.assertEqual(expected['to'], [{'set_variable': {'name': 'caps_secondary_layer', 'value': 1}}])
        self.assertEqual(expected['to_after_key_up'], [{'set_variable': {'name': 'caps_secondary_layer', 'value': 0}}])
        normal = next(r for r in self.rules if r['description'].startswith('[Map]: [LOpt]'))
        self.assertLess(self.rules.index(entry), self.rules.index(normal))
        mappings = [m for m in normal['manipulators'] if m['from']['key_code'] == 'left_command']
        self.assertEqual([(m['conditions'][0]['type'], m['to'][0]['key_code']) for m in mappings],
                         [('frontmost_application_if', 'left_option'), ('frontmost_application_unless', 'left_control')])

    def test_all_secondary_shortcuts_accept_lcmd(self):
        consumers = [m for r in self.rules for m in r['manipulators']
                     if {'name': 'caps_secondary_layer', 'type': 'variable_if', 'value': 1} in m.get('conditions', [])]
        self.assertGreaterEqual(len(consumers), 10)
        for m in consumers:
            optional = m['from'].get('modifiers', {}).get('optional', [])
            self.assertTrue('any' in optional or 'left_command' in optional, m['from'])
        paste = next(m for m in consumers if m['from']['key_code'] == 'v' and not m['from']['modifiers'].get('mandatory'))
        self.assertTrue(paste['to'][0]['shell_command'].endswith('secondary_clipboard.py paste'))


class EventRoutingTests(unittest.TestCase):
    def test_cancelled_chord_posts_nothing(self):
        cancel = threading.Event()
        cancel.set()
        with patch.object(events, 'post_key_event') as post:
            with self.assertRaises(InterruptedError):
                events.post_keystroke(0, events.SHIFT_FLAG, cancel_event=cancel)
            post.assert_not_called()

    def test_cancellation_during_key_down_releases_key_and_modifier(self):
        cancel = threading.Event()
        def posted(code, down, flags, **kwargs):
            if code == 0 and down:
                cancel.set()
        with patch.object(events, 'post_key_event', side_effect=posted) as post:
            with self.assertRaises(InterruptedError):
                events.post_keystroke(0, events.SHIFT_FLAG, interval=.001, cancel_event=cancel)
        self.assertEqual([c.args[:2] for c in post.call_args_list],
                         [(56, True), (0, True), (0, False), (56, False)])
        self.assertEqual(post.call_args.args[2], 0)

    def test_cancellation_during_modifier_wait_never_presses_main_key(self):
        cancel = threading.Event()
        with patch.object(events, 'post_key_event', side_effect=lambda *a, **kw: cancel.set()) as post:
            with self.assertRaises(InterruptedError):
                events.post_keystroke(0, events.SHIFT_FLAG, interval=1, cancel_event=cancel)
        self.assertEqual([c.args[:2] for c in post.call_args_list], [(56, True), (56, False)])

    def test_unicode_chord_and_custom_interval(self):
        with patch.object(events, 'post_key_event') as post, patch.object(events.time, 'sleep') as sleep:
            events.post_keystroke(0, interval=.002, unicode_text='\u4e2d\U0001f600')
        self.assertEqual([c.args for c in post.call_args_list], [(0, True, 0), (0, False, 0)])
        self.assertTrue(all(c.kwargs['unicode_text'] == '\u4e2d\U0001f600' for c in post.call_args_list))
        self.assertEqual([c.args for c in sleep.call_args_list], [(.002,), (.002,)])

    def test_chord_waits_after_each_event_including_final_release(self):
        calls = []
        with patch.object(events, 'post_key_event', side_effect=lambda *a, **kw: calls.append(('key', a))), \
             patch.object(events.time, 'sleep', side_effect=lambda seconds: calls.append(('wait', seconds))):
            events.post_keystroke(events.V_KEY_CODE, events.COMMAND_FLAG)
        self.assertEqual([kind for kind, _ in calls], ['key', 'wait'] * 4)
        self.assertEqual([value for kind, value in calls if kind == 'wait'], [0.01] * 4)
        self.assertEqual(calls[-2], ('key', (events.LEFT_COMMAND_KEY_CODE, False, 0)))

    def test_output_defaults_to_session_and_test_input_can_use_hid(self):
        with patch.object(events._CG, 'CGEventCreateKeyboardEvent', return_value=123), \
             patch.object(events._CG, 'CGEventSetFlags') as flags, \
             patch.object(events._CG, 'CGEventSetType') as event_type, \
             patch.object(events._CG, 'CGEventPost') as post, \
             patch.object(events._CF, 'CFRelease') as release:
            events.post_keystroke(events.V_KEY_CODE, events.COMMAND_FLAG)
            self.assertEqual([call.args[0] for call in post.call_args_list], [events.SESSION_EVENT_TAP] * 4)
            self.assertEqual([call.args[1] for call in flags.call_args_list],
                             [events.COMMAND_FLAG | 0x8] * 3 + [0])
            self.assertEqual(release.call_count, 4)
            event_type.reset_mock()
            events.post_key_event(events.LEFT_SHIFT_KEY_CODE, True, events.SHIFT_FLAG,
                                  flags_changed=True, event_tap=events.HID_EVENT_TAP)
            event_type.assert_called_once_with(123, events.FLAGS_CHANGED_EVENT)
            post.assert_called_with(events.HID_EVENT_TAP, 123)

    def test_chord_sequence_and_failure_cleanup(self):
        full = events.COMMAND_FLAG | events.SHIFT_FLAG | 0x8 | 0x2
        with patch.object(events, 'post_key_event') as post:
            events.post_keystroke(events.V_KEY_CODE, events.COMMAND_FLAG | events.SHIFT_FLAG)
        self.assertEqual([c.args[:2] for c in post.call_args_list],
                         [(55, True), (56, True), (9, True), (9, False), (56, False), (55, False)])
        self.assertEqual(post.call_args_list[2].args[2], full)
        self.assertTrue(post.call_args_list[0].kwargs['flags_changed'])
        self.assertEqual(post.call_args_list[-1].args[2], 0)
        with patch.object(events, 'post_key_event', side_effect=[None, RuntimeError('failed'), None, None]) as post:
            with self.assertRaises(RuntimeError):
                events.post_keystroke(events.V_KEY_CODE, events.COMMAND_FLAG)
        self.assertEqual(post.call_args_list[-1].args, (55, False, 0))

    def test_chords_preserve_explicit_modifier_sides(self):
        for left, right in (('LCmd', 'RCmd'), ('LShift', 'RShift'), ('LOpt', 'ROpt'), ('LCtrl', 'RCtrl')):
            lc, generic, ls = events.MODIFIER_KEYS[left]
            rc, _, rs = events.MODIFIER_KEYS[right]
            for flags, expected in [(generic, [lc]), (generic | ls, [lc]),
                                    (generic | rs, [rc]), (generic | ls | rs, [lc, rc])]:
                with self.subTest(left=left, flags=flags), patch.object(events, 'post_key_event') as post:
                    events.post_keystroke(0, flags, interval=0)
                    calls = post.call_args_list
                    self.assertEqual([c.args[0] for c in calls if c.args[1] and c.kwargs['flags_changed']], expected)
                    self.assertEqual(calls[-1].args[2], 0)
                    if len(expected) == 2:
                        self.assertEqual(calls[-2].args[2], generic | ls)

    def test_unicode_uses_utf16_units_and_releases_events(self):
        import ctypes
        import insert_unicode_symbol_cgevent as unicode_input
        text = '\u3000\U0001f600'
        captured = []
        def capture(event, count, buffer):
            captured.append((count, ctypes.string_at(buffer, count * 2)))
        with patch.object(events._CG, 'CGEventCreateKeyboardEvent', return_value=123), \
             patch.object(events._CG, 'CGEventSetFlags'), \
             patch.object(events._CG, 'CGEventKeyboardSetUnicodeString', side_effect=capture), \
             patch.object(events._CG, 'CGEventPost') as post, \
             patch.object(events._CF, 'CFRelease') as release:
            unicode_input.insert(text)
        self.assertEqual(captured, [(3, text.encode('utf-16-le'))] * 2)
        self.assertEqual([c.args[0] for c in post.call_args_list], [events.SESSION_EVENT_TAP] * 2)
        self.assertEqual(release.call_count, 2)

    def test_remaining_script_shortcuts_reuse_common_sender(self):
        import indent_select_lines as indent
        import insert_unicode_symbol_clipboard as legacy
        import post_dummy_key as dummy
        import release_shift
        with patch.object(events, 'post_keystroke') as post:
            indent.key_code(8, ['command'])
            post.assert_called_with(8, events.COMMAND_FLAG)
            legacy.paste()
            post.assert_called_with(9, events.COMMAND_FLAG)
        with patch.object(dummy, 'post_keystroke') as post:
            dummy._post_key(79)
            post.assert_called_once_with(79)
        with patch.object(events, 'release_keys') as release:
            release_shift.release_shift()
            release.assert_called_once_with(56, 60)


if __name__ == '__main__':
    unittest.main()
