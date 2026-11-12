"""Native button styling and action feedback on an unshown, isolated panel."""

from contextlib import ExitStack
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import screen_keyboard as sk
import test_keyboard as backend


class FeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mocks = ExitStack()
        cls.addClassCleanup(cls.mocks.close)
        cls.mocks.enter_context(patch.object(sk, 'keyboard_status', return_value=({}, '', True)))
        cls.mocks.enter_context(patch.object(sk, 'is_remote', return_value=False))
        cls.mocks.enter_context(patch.object(backend, 'current_modifier_flags', return_value=0))
        cls.mocks.enter_context(patch.object(backend, 'post_key_event'))
        cls.mocks.enter_context(patch.object(backend, 'set_caps_layer'))
        cls.mocks.enter_context(patch.object(sk.keys, 'post_key_event'))
        cls.mocks.enter_context(patch.object(sk.keys, 'post_keystroke'))
        cls.mocks.enter_context(patch.object(sk.keys, 'can_post_events', return_value=True))
        cls.A = importlib.import_module('AppKit')
        cls.F = importlib.import_module('Foundation')
        cls.front_pid = cls.A.NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()
        cls.app, cls.panel, cls.controller = sk.create_panel(sk.KeyboardState(sk.EVENT_KEYS), remember_frame=False)

    @classmethod
    def tearDownClass(cls):
        cls.A.NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(cls.controller)
        cls.F.NSDistributedNotificationCenter.defaultCenter().removeObserver_(cls.controller)
        cls.panel.setDelegate_(None)
        cls.panel.close()

    def setUp(self):
        self.notice = self.enterContext(patch.object(sk, 'notify'))
        self.error = self.enterContext(patch.object(sk, 'report_error'))

    def tearDown(self):
        self.assertFalse(self.panel.isVisible())
        self.assertFalse(self.panel.isKeyWindow())
        self.assertEqual(self.A.NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier(), self.front_pid)

    def rgb(self, button):
        return tuple(self.A.NSColor.colorWithCGColor_(button.layer().backgroundColor()).getRed_green_blue_alpha_(None, None, None, None))

    def test_hover_brightens_all_regions_and_restores_on_exit(self):
        for name in ('a', '1', 'LCmd', 'Caps', 'left_arrow', 'f1', 'input_source'):
            with self.subTest(name=name):
                button = self.controller.buttons[name]
                button.mouseExited_(None)
                normal = self.rgb(button)
                button.mouseEntered_(None)
                hover = self.rgb(button)
                self.assertTrue(all(h >= n for h, n in zip(hover[:3], normal[:3])))
                self.assertNotEqual(hover, normal)
                button.mouseExited_(None)
                self.assertEqual(self.rgb(button), normal)

    def test_hover_preserves_pressed_and_locked_colors(self):
        button = self.controller.buttons['LShift']
        try:
            for locked in (False, True):
                button.locked = locked
                button.setState_(1)
                button.mouseExited_(None)
                active = self.rgb(button)
                button.mouseEntered_(None)
                self.assertEqual(self.rgb(button), active)
        finally:
            button.locked = False
            button.setState_(0)
            button.mouseExited_(None)

    def test_disabled_key_does_not_highlight(self):
        button = self.controller.buttons['a']
        try:
            button.setEnabled_(False)
            button.mouseExited_(None)
            normal = self.rgb(button)
            button.mouseEntered_(None)
            self.assertEqual(self.rgb(button), normal)
        finally:
            button.setEnabled_(True)
            button.mouseExited_(None)

    def test_toolbar_hover_and_tracking_without_activation(self):
        for button in (*self.controller.buttons.values(), *self.controller.toolbar.values()):
            self.assertTrue(any(area.owner() == button for area in button.trackingAreas()))
        for button in self.controller.toolbar.values():
            button.mouseEntered_(None)
            self.assertEqual(self.rgb(button)[3], 1)
            button.mouseExited_(None)
            self.assertEqual(self.rgb(button)[3], 0)

    def test_release_reports_success_only_after_release(self):
        with patch.object(self.controller, 'release') as release:
            self.controller.reset_(None)
            release.assert_called_once_with()
            self.notice.assert_called_once_with('Screen keys released', level='info')
        self.notice.reset_mock()
        with patch.object(self.controller, 'release', side_effect=RuntimeError('release failed')):
            self.controller.reset_(None)
            self.notice.assert_not_called()
            self.error.assert_called_once()

    def test_content_and_buttons_request_arrow_cursor_without_focus(self):
        areas = [(self.panel.contentView(), self.controller)]
        areas.extend((button, button) for button in
                     (*self.controller.buttons.values(), *self.controller.toolbar.values()))
        with patch.object(self.A, 'NSCursor') as cursors:
            arrow = cursors.arrowCursor
            for view, owner in areas:
                with self.subTest(view=str(view)):
                    required = (self.A.NSTrackingCursorUpdate | self.A.NSTrackingActiveAlways
                                | self.A.NSTrackingInVisibleRect)
                    self.assertTrue(any(area.owner() == owner and area.options() & required == required
                                        for area in view.trackingAreas()))
                    arrow.reset_mock()
                    owner.cursorUpdate_(None)
                    arrow.assert_called_once_with()
                    arrow.return_value.set.assert_called_once_with()

    def test_toolbar_click_does_not_leave_pressed_color(self):
        button = self.controller.toolbar['resetSize:']
        button.mouseExited_(None)
        normal = self.rgb(button)
        button.performClick_(None)
        button.mouseEntered_(None)
        self.assertEqual(button.layer().borderWidth(), 1)
        button.mouseExited_(None)
        self.assertEqual(self.rgb(button), normal)

    def test_menu_controls_ignore_residual_native_state(self):
        for button in (*self.controller.toolbar.values(), self.controller.buttons['input_source']):
            if button.toggle_button:
                continue
            with self.subTest(action=str(button.action())):
                button.setState_(0)
                button.mouseExited_(None)
                normal = self.rgb(button)
                try:
                    button.setState_(1)
                    button.mouseExited_(None)
                    self.assertEqual(self.rgb(button), normal)
                    button.pointer_down = True
                    button.update_appearance()
                    self.assertNotEqual(self.rgb(button), normal)
                finally:
                    button.pointer_down = False
                    button.setState_(0)
                    button.mouseExited_(None)

    def test_unchanged_sync_reuses_titles_and_appearance(self):
        self.controller.sync_buttons()
        button = self.controller.buttons['a']
        with patch.object(button, 'setAttributedTitle_') as title, \
             patch.object(button, 'setFont_') as font:
            self.controller.sync_buttons()
            self.controller.sync_buttons()
            title.assert_not_called()
            font.assert_not_called()

    def test_layer_color_updates_without_rebuilding_labels(self):
        button = self.controller.buttons['Caps']
        button.mouseExited_(None)
        normal = self.rgb(button)
        try:
            with patch.object(button, 'setFont_') as font, \
                 patch.object(backend, 'set_caps_layer') as layer:
                self.controller.clicked_(button)
                layer.assert_called_once_with(True)
                self.assertEqual(button.state(), 1)
                self.assertNotEqual(self.rgb(button), normal)
                self.controller.clicked_(button)
                self.assertEqual(layer.call_args.args, (False,))
                self.assertEqual(button.state(), 0)
                self.assertEqual(self.rgb(button), normal)
                font.assert_not_called()
        finally:
            self.controller.release_safely()

    def test_button_colors_have_no_implicit_animation(self):
        for button in (*self.controller.buttons.values(), *self.controller.toolbar.values()):
            actions = button.layer().actions()
            self.assertEqual(actions['backgroundColor'], self.F.NSNull.null())
            self.assertEqual(actions['borderWidth'], self.F.NSNull.null())

    def test_reset_size_feedback(self):
        self.panel.setContentSize_((700, 300))
        self.controller.resetSize_(None)
        self.assertEqual(self.panel.contentView().bounds().size, sk.DEFAULT_SIZE)
        self.notice.assert_called_once_with('Window size reset', level='info')

    def test_input_source_switch_is_silent(self):
        with patch.object(sk, 'switch_input_source', return_value='previous') as switch:
            self.controller.clicked_(self.controller.buttons['input_source'])
            switch.assert_called_once()
            self.assertEqual(self.controller.previous_input_source, 'previous')
            self.notice.assert_not_called()
            self.error.assert_not_called()

    def test_remote_input_source_switch_is_silent(self):
        with patch.object(sk, 'is_remote', return_value=True), \
             patch.object(sk.keys, 'post_keystroke') as post, \
             patch.object(sk, 'switch_input_source') as switch:
            self.controller.clicked_(self.controller.buttons['input_source'])
            post.assert_called_once_with(sk.keys.KEY_CODES['f1'])
            switch.assert_not_called()
            self.notice.assert_not_called()
            self.error.assert_not_called()

    def test_failed_source_switch_has_no_success_feedback(self):
        with patch.object(sk, 'switch_input_source', side_effect=RuntimeError('unavailable')):
            self.controller.inputSource_(None)
            self.notice.assert_not_called()
            self.error.assert_called_once()

    def test_refresh_feedback_levels(self):
        for warning, permitted, level in (('', True, 'info'), ('Fallback off', True, 'warning'),
                                           ('Permission required', False, 'error')):
            with patch.object(sk, 'keyboard_status', return_value=({}, warning, permitted)):
                self.controller.refresh_(None)
                self.notice.assert_called_with(warning or 'Karabiner layers available', level=level)
        self.controller.refresh_status()

    def test_menu_feedback_waits_until_menu_closes(self):
        def choose(*args):
            self.controller.extendedSelected_(menu.addItem_.call_args_list[-2].args[0])
            self.notice.assert_not_called()
        with patch.object(self.A, 'NSMenu') as factory:
            menu = factory.alloc.return_value.initWithTitle_.return_value
            menu.popUpMenuPositioningItem_atLocation_inView_.side_effect = choose
            self.controller.extended_(self.controller.toolbar['extended:'])
        self.notice.assert_called_once_with('Karabiner layers available', level='info')

    def test_cancelled_menu_is_silent(self):
        with patch.object(self.A, 'NSMenu'):
            self.controller.extended_(self.controller.toolbar['extended:'])
        self.notice.assert_not_called()

    def test_toolbar_and_input_source_swap(self):
        self.assertEqual(list(self.controller.toolbar),
                         ['minimize:', 'extended:', 'numpad:', 'reset:', 'resetSize:'])
        self.assertLess(self.A.NSMaxX(self.controller.toolbar['minimize:'].frame()),
                        self.A.NSMinX(self.controller.toolbar['extended:'].frame()))
        self.assertNotIn('extended', self.controller.buttons)
        self.assertIsNotNone(self.controller.buttons['input_source'].image())
        with patch.object(sk, 'switch_input_source') as switch:
            self.controller.clicked_(self.controller.buttons['input_source'])
            switch.assert_called_once()

    def test_numpad_toolbar_toggle_tracks_visibility(self):
        button = self.controller.toolbar['numpad:']
        button.mouseExited_(None)
        normal = self.rgb(button)
        try:
            button.performClick_(None)
            button.mouseExited_(None)
            self.assertTrue(self.controller.numpad_visible)
            self.assertEqual(button.state(), 1)
            selected = self.rgb(button)
            self.assertNotEqual(selected, normal)
            self.controller.refresh_status()
            self.assertEqual(self.rgb(button), selected)
            button.mouseEntered_(None)
            button.mouseExited_(None)
            self.assertEqual(self.rgb(button), selected)
            button.performClick_(None)
            self.assertFalse(self.controller.numpad_visible)
            self.assertEqual(button.state(), 0)
            self.assertEqual(self.rgb(button), normal)
        finally:
            if self.controller.numpad_visible:
                self.controller.numpad_(None)

    def test_numpad_mode_exact_colors(self):
        button = self.controller.buttons['pad_mode']
        try:
            for enabled, idle in ((False, (232, 160, 125)), (True, (159, 73, 41))):
                button.setState_(int(enabled))
                for hovered in (False, True):
                    button.hovered = hovered
                    for pressed in (False, True):
                        button.pointer_down = pressed
                        button.update_appearance()
                        expected = (244, 189, 157) if pressed else idle
                        self.assertEqual(tuple(round(c * 255) for c in self.rgb(button)[:3]), expected)
        finally:
            button.pointer_down = False
            button.hovered = False
            self.controller.sync_buttons()

    def test_numpad_expansion_and_mode_colors(self):
        sk.reset_window_size(self.panel)
        before = self.controller.buttons['a'].frame().size.width
        self.controller.numpad_(None)
        try:
            self.assertTrue(self.controller.numpad_visible)
            self.assertAlmostEqual(self.controller.buttons['a'].frame().size.width, before, delta=.1)
            self.assertTrue(all(not self.controller.buttons[row[0]].isHidden() for row in sk.NUMPAD))
            button = self.controller.buttons['pad_mode']
            numeric_color = self.rgb(button)
            self.assertEqual(button.title(), 'Num')
            self.controller.clicked_(button)
            self.assertEqual(button.title(), 'Nav')
            self.assertNotEqual(self.rgb(button), numeric_color)
            self.assertEqual(self.controller.buttons['pad_7'].title(), 'Home')
            self.assertFalse(self.controller.buttons['pad_5'].isEnabled())
            self.controller.clicked_(button)
            self.assertEqual(self.rgb(button), numeric_color)
            self.assertEqual(self.controller.buttons['pad_7'].title(), '7')
            self.assertTrue(self.controller.buttons['pad_5'].isEnabled())
        finally:
            self.controller.numeric_mode = True
            self.controller.numpad_(None)
        self.assertEqual(self.panel.contentView().bounds().size, sk.DEFAULT_SIZE)
        self.assertTrue(all(self.controller.buttons[row[0]].isHidden() for row in sk.NUMPAD))
        for _ in range(3):
            self.controller.numpad_(None)
            self.controller.numpad_(None)
        self.assertEqual(self.panel.contentView().bounds().size, sk.DEFAULT_SIZE)

    def test_numpad_outputs_use_final_session_keys_in_both_contexts(self):
        try:
            for remote in (False, True):
                with patch.object(sk, 'is_remote', return_value=remote):
                    for mode in (False, True):
                        self.controller.numeric_mode = mode
                        self.controller.refresh_status()
                        for row in sk.NUMPAD:
                            name = row[0]
                            output = sk.numpad_output(name, mode)
                            if output is None:
                                continue
                            code, flags = output
                            with patch.object(sk.keys, 'post_key_event') as post:
                                self.controller.clicked_(self.controller.buttons[name])
                                self.assertEqual(self.controller.key_down_name, name)
                                self.assertEqual(self.controller.buttons[name].state(), 1)
                                self.controller.releaseKey_(None)
                                self.assertEqual([c.args for c in post.call_args_list],
                                                 [(code, True, flags), (code, False, flags)])
                                self.assertTrue(all(c.kwargs['event_tap'] == sk.keys.SESSION_EVENT_TAP
                                                    for c in post.call_args_list))
        finally:
            self.controller.numeric_mode = True
            self.controller.refresh_status()

    def test_expanded_labels_fit_without_overlaps(self):
        self.controller.numpad_(None)
        try:
            for size in (sk.MINIMUM_SIZE, sk.DEFAULT_SIZE, (1000, 400)):
                self.panel.setContentSize_((sk.resized_width(size[0], False, True), size[1]))
                for remote in (False, True):
                    with patch.object(sk, 'is_remote', return_value=remote):
                        for mode in (False, True):
                            self.controller.numeric_mode = mode
                            self.controller.refresh_status()
                            self.controller.layout()
                            self.assertEqual(self.controller.buttons['Caps'].title(), 'Layer(F1)' if remote else 'Layer')
                            frames = {name: button.frame() for name, button in self.controller.buttons.items()}
                            self.assertAlmostEqual(self.A.NSMaxY(frames['pad_mode']),
                                                   self.A.NSMaxY(frames['escape']))
                            self.assertAlmostEqual(self.A.NSMinY(frames['pad_0']),
                                                   self.A.NSMinY(frames['spacebar']))
                            self.assertAlmostEqual(self.A.NSMinX(frames['pad_mode']) -
                                                   self.A.NSMaxX(frames['delete_forward']), 3)
                            self.assertEqual(self.rgb(self.controller.buttons['pad_enter']),
                                             self.rgb(self.controller.buttons['return_or_enter']))
                            bounds = self.panel.contentView().bounds()
                            buttons = list(self.controller.buttons.items())
                            for index, (name, button) in enumerate(buttons):
                                rect = button.frame()
                                self.assertTrue(self.A.NSContainsRect(bounds, rect), name)
                                self.assertLessEqual(button.attributedTitle().size().width + 4,
                                                     rect.size.width + .01, name)
                                for other_name, other in buttons[index + 1:]:
                                    self.assertFalse(self.A.NSIntersectsRect(rect, other.frame()), (name, other_name))
        finally:
            self.controller.numeric_mode = True
            self.controller.numpad_(None)
            sk.reset_window_size(self.panel)
            self.controller.refresh_status()

    def test_release_all_keeps_existing_child_feedback(self):
        with patch.object(sk.subprocess, 'Popen') as launch:
            self.controller.releaseAll_(None)
            launch.assert_called_once()
            self.notice.assert_not_called()
        with patch.object(sk.subprocess, 'Popen', side_effect=OSError('launch failed')):
            self.controller.releaseAll_(None)
            self.error.assert_called_once()

    def test_reopen_places_existing_window_on_pointer_display(self):
        main, other = Mock(), Mock()
        main.frame.return_value = self.A.NSMakeRect(0, 0, 1920, 1080)
        other.frame.return_value = self.A.NSMakeRect(-1440, -200, 1440, 900)
        other.visibleFrame.return_value = self.A.NSMakeRect(-1440, -160, 1440, 830)
        notification = Mock()
        notification.userInfo.return_value = {'command': 'show'}
        for minimized in (False, True):
            for point in ((-1000, 300), (-1439, 699), (-1, -199)):
                with self.subTest(minimized=minimized, point=point), \
                     patch.object(self.controller, 'panel', Mock()) as panel, \
                     patch.object(self.controller, 'refresh_status'), \
                     patch.object(self.A, 'NSScreen') as screens, \
                     patch.object(self.A, 'NSEvent') as events:
                    screens.screens.return_value = [main, other]
                    screens.mainScreen.return_value = main
                    events.mouseLocation.return_value = self.A.NSMakePoint(*point)
                    panel.isMiniaturized.return_value = minimized
                    panel.frame.return_value = self.A.NSMakeRect(0, 0, 700, 260)
                    self.controller.command_(notification)
                    frame = panel.setFrame_display_.call_args.args[0]
                    self.assertTrue(self.A.NSContainsRect(other.visibleFrame(), frame))
                    self.assertEqual(frame[1], (700, 260))
                    if point == (-1000, 300):
                        self.assertEqual(frame[0], (-984, 24))
                    self.assertEqual(panel.deminiaturize_.call_count, int(minimized))
                    panel.orderFrontRegardless.assert_called_once_with()
                    names = [call[0] for call in panel.method_calls]
                    self.assertLess(names.index('setFrame_display_'), names.index('orderFrontRegardless'))
                    if minimized:
                        self.assertLess(names.index('deminiaturize_'), names.index('setFrame_display_'))
                    panel.makeKeyAndOrderFront_.assert_not_called()

    def test_pointer_frame_fits_oversized_keyboard(self):
        bounds = self.A.NSMakeRect(-1440, -160, 1440, 830)
        frame = sk.panel_frame_near_pointer(self.A.NSMakePoint(-700, 300), bounds, 2200, 1200)
        self.assertTrue(self.A.NSContainsRect(bounds, frame))
        self.assertEqual(frame, ((-1432, -152), (1424, 814)))

    def test_minimize_feedback_only_when_minimized(self):
        with patch.object(self.controller, 'panel', Mock()) as panel:
            panel.isMiniaturized.return_value = True
            self.controller.minimize_(None)
            panel.miniaturize_.assert_called_once_with(None)
            self.notice.assert_called_once_with('Keyboard minimized', level='info')


if __name__ == '__main__':
    unittest.main()
