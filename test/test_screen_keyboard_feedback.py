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
        self.controller.menu_tracking = False
        self.controller.menu_feedback = None

    def tearDown(self):
        self.assertFalse(self.panel.isVisible())
        self.assertFalse(self.panel.isKeyWindow())
        self.assertEqual(self.A.NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier(), self.front_pid)

    def rgb(self, button):
        return tuple(self.A.NSColor.colorWithCGColor_(button.layer().backgroundColor()).getRed_green_blue_alpha_(None, None, None, None))

    def test_hover_brightens_all_regions_and_restores_on_exit(self):
        for name in ('a', '1', 'LCmd', 'Caps', 'left_arrow', 'f1', 'extended'):
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
        for button in (*self.controller.toolbar.values(), self.controller.buttons['extended']):
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

    def test_reset_size_feedback(self):
        self.panel.setContentSize_((700, 300))
        self.controller.resetSize_(None)
        self.assertEqual(self.panel.contentView().bounds().size, sk.DEFAULT_SIZE)
        self.notice.assert_called_once_with('Window size reset', level='info')

    def test_input_source_feedback(self):
        with patch.object(sk, 'switch_input_source', return_value='previous') as switch:
            self.controller.inputSource_(None)
            switch.assert_called_once()
            self.notice.assert_called_once_with('Input source switched', level='info')

    def test_remote_feedback_only_claims_key_delivery(self):
        with patch.object(sk, 'is_remote', return_value=True), \
             patch.object(sk.keys, 'post_keystroke') as post, \
             patch.object(sk, 'switch_input_source') as switch:
            self.controller.inputSource_(None)
            post.assert_called_once_with(sk.keys.KEY_CODES['f1'])
            switch.assert_not_called()
            self.notice.assert_called_once_with('Remote language key sent (F1)', level='info')

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
            self.controller.refresh_(None)
            self.notice.assert_not_called()
        with patch.object(self.controller, 'menu', Mock()) as menu:
            menu.popUpMenuPositioningItem_atLocation_inView_.side_effect = choose
            self.controller.menu_(self.controller.toolbar['menu:'])
        self.notice.assert_called_once_with('Karabiner layers available', level='info')
        self.assertFalse(self.controller.menu_tracking)

    def test_cancelled_menu_is_silent(self):
        with patch.object(self.controller, 'menu', Mock()):
            self.controller.menu_(self.controller.toolbar['menu:'])
        self.notice.assert_not_called()

    def test_release_all_keeps_existing_child_feedback(self):
        with patch.object(sk.subprocess, 'Popen') as launch:
            self.controller.releaseAll_(None)
            launch.assert_called_once()
            self.notice.assert_not_called()
        with patch.object(sk.subprocess, 'Popen', side_effect=OSError('launch failed')):
            self.controller.releaseAll_(None)
            self.error.assert_called_once()

    def test_minimize_feedback_only_when_minimized(self):
        with patch.object(self.controller, 'panel', Mock()) as panel:
            panel.isMiniaturized.return_value = True
            self.controller.minimize_(None)
            panel.miniaturize_.assert_called_once_with(None)
            self.notice.assert_called_once_with('Keyboard minimized', level='info')


if __name__ == '__main__':
    unittest.main()
