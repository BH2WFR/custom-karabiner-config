"""Screen layout, held-key state and status checks without a live panel."""

import json
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, mock_open, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import screen_keyboard as sk
import test_keyboard as backend
import keyboard_events as keys


class LayoutTests(unittest.TestCase):
    def test_rows_align(self):
        self.assertEqual([sum(item[2] for item in row) for row in sk.ROWS], [sk.ROW_UNITS] * 6)
        self.assertEqual([item[0] for item in sk.ROWS[-1]],
                         ['LCtrl', 'LOpt', 'LCmd', 'spacebar', 'RCmd', 'Fn', 'ROpt',
                          'left_arrow', 'down_arrow', 'right_arrow'])

    def test_keys_are_unique_and_supported(self):
        names = [key[0] for row in sk.ROWS for key in row if key[0]]
        self.assertEqual(len(names), 85)
        self.assertFalse({'f13', 'f14', 'f15'} & set(names))
        self.assertIn('non_us_backslash', names)
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertTrue(name in keys.KEY_CODES or name in sk.EVENT_KEYS or name in ('Caps', 'input_source'), name)

    def test_extended_and_navigation_keys_are_one_unit(self):
        self.assertEqual(sk.ROWS[0][-4:], [('f12', 'F12', 1), ('input_source', '', 1),
                                          ('insert', 'Ins', 1), ('delete_forward', 'Del', 1)])

    def test_normal_labels(self):
        self.assertEqual(list(sk.NORMAL_LABELS.values()), ['LCmd', 'LOpt', 'LCtrl', 'ROpt', 'Fn', 'RCmd'])

    def test_platform_labels(self):
        self.assertEqual(sk.key_label('delete_or_backspace', 'Backspace'), '\u232b')
        self.assertEqual(sk.key_label('delete_forward', 'Del'), '\u2326')
        self.assertEqual(sk.key_label('LCmd', 'Cmd'), '\u2318')
        self.assertEqual(sk.key_label('Caps', 'Caps'), 'Layer')
        self.assertEqual(sk.key_label('Caps', 'Caps', remote=True), 'Layer(F1)')
        self.assertEqual(sk.key_label('delete_or_backspace', 'Backspace', remote=True), '\u232b')
        self.assertEqual(sk.key_label('delete_forward', 'Del', remote=True), 'Del')
        for name in ('tab', 'escape', 'return_or_enter', 'LShift', 'home', 'end', 'page_up', 'page_down'):
            self.assertEqual(sk.key_label(name, '', remote=True), sk.MAC_SYMBOLS[name])
        self.assertEqual([sk.key_label(name, '', remote=True) for name in sk.RDP_LABELS],
                         ['Ctrl', 'Win', 'Alt', 'Alt', 'Win', 'Ctrl'])

    def test_symbol_pairs_keep_a_space(self):
        for name, label, _ in (key for row in sk.ROWS for key in row):
            if '  ' in label:
                for remote in (True, False):
                    self.assertIn(' ', sk.key_label(name, label, remote=remote, compact=True))

    def test_all_labels_are_strings(self):
        for row in sk.ROWS:
            for name, label, _ in row:
                for remote in (False, True):
                    for compact in (False, True):
                        self.assertIsInstance(sk.key_label(name, label, remote=remote, compact=compact), str)

    def test_key_regions_have_distinct_colors(self):
        names = ['a', '1', 'LCmd', 'Caps', 'left_arrow', 'f1', 'return_or_enter']
        self.assertEqual(len({sk.key_color(name) for name in names}), len(names))
        self.assertEqual(sk.key_color('input_source'), (24, 83, 55))
        self.assertEqual(sk.key_color('pad_enter'), sk.key_color('return_or_enter'))
        self.assertNotIn(sk.key_color('input_source'), {sk.key_color(name) for name in names})

    def test_numpad_geometry_has_no_overlap(self):
        occupied = set()
        self.assertEqual(len(sk.NUMPAD), 17)
        for name, _, _, _, _, x, y, width, height in sk.NUMPAD:
            cells = {(i, j) for i in range(x, x + width) for j in range(y, y + height)}
            self.assertFalse(cells & occupied, name)
            self.assertTrue(all(0 <= i < 4 and 0 <= j < 5 for i, j in cells))
            occupied.update(cells)
        self.assertEqual(len(occupied), 20)

    def test_numeric_mode_ignores_remote_numlock(self):
        for digit in '0123456789':
            self.assertEqual(sk.numpad_output('pad_' + digit, True), (keys.KEY_CODES[digit], 0))
        self.assertEqual(sk.numpad_output('pad_decimal', True), (keys.KEY_CODES['.'], 0))
        for name, key in [('pad_0', 'insert'), ('pad_1', 'end'), ('pad_2', 'down_arrow'),
                          ('pad_3', 'page_down'), ('pad_4', 'left_arrow'), ('pad_6', 'right_arrow'),
                          ('pad_7', 'home'), ('pad_8', 'up_arrow'), ('pad_9', 'page_up'),
                          ('pad_decimal', 'delete_forward')]:
            self.assertEqual(sk.numpad_output(name, False), (keys.KEY_CODES[key], 0))
        self.assertIsNone(sk.numpad_output('pad_5', False))
        for mode in (True, False):
            self.assertEqual(sk.numpad_output('pad_plus', mode),
                             (keys.KEY_CODES['keypad_plus'], keys.NUMERIC_PAD_FLAG))
            self.assertIsNone(sk.numpad_output('pad_mode', mode))

    def test_expanding_preserves_main_key_width(self):
        for width in (sk.MINIMUM_SIZE[0], sk.DEFAULT_SIZE[0], 1000):
            expanded = sk.resized_width(width, False, True)
            self.assertAlmostEqual((width - 5) / sk.ROW_UNITS,
                                   (expanded - 5) / (sk.ROW_UNITS + sk.NUMPAD_UNITS))
            self.assertAlmostEqual(sk.resized_width(expanded, True, False), width)

    def test_authorized_process_does_not_prompt(self):
        with patch.object(keys, 'can_post_events', return_value=True), \
             patch.object(keys._CG, 'CGRequestPostEventAccess') as request:
            self.assertTrue(keys.request_post_events())
            request.assert_not_called()

    def test_missing_permission_requests_system_authorization(self):
        with patch.object(keys, 'can_post_events', return_value=False), \
             patch.object(keys._CG, 'CGRequestPostEventAccess', return_value=False) as request:
            self.assertFalse(keys.request_post_events())
            request.assert_called_once_with()

    def test_main_requests_once_on_startup(self):
        app, panel, controller = Mock(), Mock(), Mock()
        with patch.object(sys, 'argv', ['screen_keyboard.py']), \
             patch.object(Path, 'mkdir'), \
             patch.object(Path, 'open', mock_open()), \
             patch.object(sk.fcntl, 'flock'), \
             patch.object(sk, 'send_command') as command, \
             patch.object(keys, 'request_post_events', return_value=False) as request, \
             patch.object(sk, 'create_panel', return_value=(app, panel, controller)), \
             patch.object(sk, 'run_panel'):
            self.assertEqual(sk.main(), 0)
            request.assert_called_once_with()
            command.assert_not_called()
            controller.show_near_pointer.assert_called_once_with()
            panel.orderFrontRegardless.assert_not_called()

    def test_duplicate_launch_restores_existing_instance(self):
        with patch.object(sys, 'argv', ['screen_keyboard.py']), \
             patch.object(Path, 'mkdir'), \
             patch.object(Path, 'open', mock_open()), \
             patch.object(sk.fcntl, 'flock', side_effect=BlockingIOError), \
             patch.object(sk, 'send_command') as command, \
             patch.object(keys, 'request_post_events') as request, \
             patch.object(sk, 'create_panel') as create:
            self.assertEqual(sk.main(), 0)
            command.assert_called_once_with('show')
            request.assert_not_called()
            create.assert_not_called()

    def test_check_does_not_prompt(self):
        with patch.object(sys, 'argv', ['screen_keyboard.py', '--check']), \
             patch.object(sys, 'stdout', new_callable=io.StringIO), \
             patch.object(sk, 'keyboard_status', return_value=({}, 'Permission required', False)), \
             patch.object(keys, 'request_post_events') as request:
            self.assertEqual(sk.main(), 1)
            request.assert_not_called()

    def test_remote_detection_uses_project_patterns(self):
        config = json.loads((ROOT / 'karabiner.json').read_text(encoding='utf-8'))
        for bundle, path, remote in [
            ('com.netease.uuremote', '', True), ('com.microsoft.rdc.macos', '', True),
            ('unknown', '/Applications/Windows App.app/Contents/MacOS/Windows App', True),
            ('com.apple.TextEdit', '', False), ('com.microsoft.rdc.macos.other', '', False),
        ]:
            app = Mock()
            app.bundleIdentifier.return_value = bundle
            app.executableURL.return_value.path.return_value = path
            self.assertEqual(sk.is_remote(app, config), remote)

    def test_external_semantic_transport(self):
        self.assertEqual(sk.EVENT_KEYS['LCtrl'], keys.MODIFIER_KEYS['Fn'])
        self.assertEqual(sk.EVENT_KEYS['ROpt'], keys.MODIFIER_KEYS['RCtrl'])
        self.assertEqual(sk.EVENT_KEYS['Fn'], (110, 0, 0))

    def test_rdp_final_modifier_flags(self):
        self.assertEqual(sk.mapped_modifier_flags(['LCtrl'], sk.RDP_LABELS),
                         keys.MODIFIER_KEYS['LCtrl'][1] | keys.MODIFIER_KEYS['LCtrl'][2])
        self.assertEqual(sk.mapped_modifier_flags(['LOpt'], sk.RDP_LABELS),
                         keys.MODIFIER_KEYS['LCmd'][1] | keys.MODIFIER_KEYS['LCmd'][2])
        self.assertEqual(sk.mapped_modifier_flags(['LCmd'], sk.RDP_LABELS),
                         keys.MODIFIER_KEYS['LOpt'][1] | keys.MODIFIER_KEYS['LOpt'][2])
        self.assertEqual(sk.mapped_modifier_flags(['Fn'], sk.RDP_LABELS),
                         keys.MODIFIER_KEYS['RCmd'][1] | keys.MODIFIER_KEYS['RCmd'][2])
        self.assertEqual(sk.RDP_KEYS['Fn'], keys.MODIFIER_KEYS['RCmd'])

    def test_extended_keys(self):
        for remote in (False, True):
            options = sk.extended_keys(remote)
            self.assertEqual(len(options), 2 if remote else 3)
            self.assertFalse({'f14', 'f15'} & {name for _, name, _ in options})
            for title, name, flags in options:
                self.assertTrue(title)
                self.assertIn(name, keys.KEY_CODES)
                self.assertIsInstance(flags, int)
        self.assertEqual(sk.extended_keys(False)[0][1:], ('5', keys.COMMAND_FLAG | keys.SHIFT_FLAG))
        self.assertEqual(sk.extended_keys(True)[-1][1:], ('f10', keys.SHIFT_FLAG))
        self.assertEqual(sk.extended_keys(True)[0], ('F13', 'f13', 0))

    def test_normal_and_direct_final_modifiers(self):
        self.assertEqual(sk.mapped_modifier_flags(['LCtrl'], sk.NORMAL_LABELS),
                         keys.MODIFIER_KEYS['LCmd'][1] | keys.MODIFIER_KEYS['LCmd'][2])
        self.assertEqual(sk.mapped_modifier_flags(['LCtrl'], sk.DIRECT_LABELS),
                         keys.MODIFIER_KEYS['LCtrl'][1] | keys.MODIFIER_KEYS['LCtrl'][2])

    def test_release_retains_only_requested_modifiers(self):
        with patch.object(backend, 'post_key_event') as post, \
             patch.object(backend, 'set_caps_layer') as caps, \
             patch.object(backend, 'current_modifier_flags', return_value=0):
            state = backend.KeyboardState()
            state.toggle('Caps')
            state.toggle('LShift')
            state.toggle('LOpt')
            post.reset_mock()
            state.release(keep={'LShift'})
            self.assertEqual(state.held, ['LShift'])
            self.assertFalse(state.caps)
            caps.assert_called_with(False)
            self.assertEqual(post.call_count, 1)
            self.assertEqual(post.call_args.args[:2], (keys.MODIFIER_KEYS['LOpt'][0], False))
            self.assertTrue(state.flags() & keys.SHIFT_FLAG)
            state.release()
            self.assertEqual(state.held, [])

    def test_remote_caps_is_held_f1_not_a_local_variable(self):
        with patch.object(backend, 'post_key_event') as post, \
             patch.object(backend, 'set_caps_layer') as caps, \
             patch.object(backend, 'current_modifier_flags', return_value=0):
            state = backend.KeyboardState(sk.RDP_KEYS, event_tap=keys.SESSION_EVENT_TAP)
            state.toggle('Caps')
            self.assertEqual(state.held, ['Caps'])
            self.assertFalse(state.caps)
            post.assert_called_once_with(keys.KEY_CODES['f1'], True, 0,
                                         flags_changed=False, event_tap=keys.SESSION_EVENT_TAP)
            state.release(keep={'Caps'})
            self.assertEqual(post.call_count, 1)
            state.release()
            self.assertEqual(post.call_args.args[:2], (keys.KEY_CODES['f1'], False))
            caps.assert_not_called()

    def test_menu_input_is_not_a_flags_changed_event(self):
        with patch.object(backend, 'post_key_event') as post, \
             patch.object(backend, 'current_modifier_flags', return_value=0):
            state = sk.KeyboardState(sk.EVENT_KEYS)
            state.toggle('Fn')
            post.assert_called_with(110, True, 0, flags_changed=False, event_tap=keys.HID_EVENT_TAP)
            state.release()
            post.assert_called_with(110, False, 0, flags_changed=False, event_tap=keys.HID_EVENT_TAP)

    def test_caps_release_and_modifier_order(self):
        calls = []
        with patch.object(backend, 'post_key_event', side_effect=lambda code, down, *a, **kw: calls.append((code, down))), \
             patch.object(backend, 'set_caps_layer', side_effect=lambda on: calls.append(('caps', on))), \
             patch.object(backend, 'current_modifier_flags', return_value=0):
            state = sk.KeyboardState(sk.EVENT_KEYS)
            state.toggle('Caps')
            state.toggle('LOpt')
            state.toggle('LShift')
            state.release()
        self.assertEqual(calls[-3:], [(56, False), (58, False), ('caps', False)])

    def test_disabled_fallback_is_rejected_without_mutation(self):
        with patch.object(Path, 'read_text', return_value='{"global":{"enable_cgeventtap_fallback":false}}'), \
             patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(RuntimeError, 'fallback'):
                backend.check_setup()
            write.assert_not_called()

    def test_direct_mode_uses_session_tap(self):
        with patch.object(backend, 'post_key_event') as post, \
             patch.object(backend, 'current_modifier_flags', return_value=0):
            state = sk.KeyboardState(sk.DIRECT_KEYS, event_tap=keys.SESSION_EVENT_TAP)
            state.toggle('LCtrl')
            self.assertEqual(post.call_args.kwargs['event_tap'], keys.SESSION_EVENT_TAP)
            self.assertEqual(post.call_args.args[0], keys.MODIFIER_KEYS['LCtrl'][0])
            state.release()

    def test_fallback_off_is_a_warning_not_a_startup_failure(self):
        with patch.object(Path, 'read_text', return_value='{"global":{}}'), \
             patch.object(keys, 'can_post_events', return_value=True):
            config, warning, permitted = sk.keyboard_status()
            self.assertTrue(permitted)
            self.assertIn('ordinary Caps Lock', warning)

    def test_bad_config_is_a_warning(self):
        with patch.object(Path, 'read_text', return_value='invalid json'), \
             patch.object(keys, 'can_post_events', return_value=True), \
             patch.object(sys, 'stderr', new_callable=io.StringIO) as stderr:
            self.assertIn('status error', sk.keyboard_status()[1])
            self.assertIn('JSONDecodeError', stderr.getvalue())

    def test_error_reports_traceback_to_stderr_and_tooltip(self):
        with patch.object(sys, 'stderr', new_callable=io.StringIO) as stderr, \
             patch.object(sk, 'notify') as notify:
            try:
                raise RuntimeError('test keyboard failure')
            except RuntimeError as exc:
                sk.report_error(exc)
            self.assertIn('Traceback (most recent call last)', stderr.getvalue())
            self.assertIn('RuntimeError: test keyboard failure', stderr.getvalue())
            notify.assert_called_once_with('test keyboard failure', level='error')

    def test_caps_tap_preserves_native_flags_and_releases(self):
        with patch.object(keys, 'post_key_event') as post, patch.object(keys.time, 'sleep'):
            keys.tap_caps_lock()
            self.assertEqual(post.call_count, 2)
            self.assertEqual(post.call_args_list[0].args, (57, True))
            self.assertEqual(post.call_args_list[1].args, (57, False))
            self.assertIsNone(post.call_args_list[0].kwargs['flags'])

    def test_missing_live_tap_disables_layers(self):
        config = {'global': {'enable_cgeventtap_fallback': True},
                  'profiles': [{'name': 'ZL', 'selected': True}]}
        quartz = Mock()
        quartz.CGGetEventTapList.return_value = (0, [], 0)
        with patch.object(Path, 'read_text', return_value=json.dumps(config)), \
             patch.object(Path, 'is_file', return_value=True), \
             patch.object(keys, 'can_post_events', return_value=True), \
             patch.object(sk.importlib, 'import_module', return_value=quartz):
            self.assertIn('tap unavailable', sk.keyboard_status()[1])

    def test_other_profile_disables_layers(self):
        config = {'global': {'enable_cgeventtap_fallback': True},
                  'profiles': [{'name': 'Other', 'selected': True}]}
        with patch.object(Path, 'read_text', return_value=json.dumps(config)), \
             patch.object(keys, 'can_post_events', return_value=True):
            self.assertIn('ZL profile inactive', sk.keyboard_status()[1])


if __name__ == '__main__':
    unittest.main()
