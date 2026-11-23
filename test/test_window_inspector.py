"""Window discovery and inspector lifecycle without activating apps or posting input."""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import window_picker as picker
import window_inspector as inspector
import tooltip


def target(pid=123, window="window", title="Test"):
    process = Mock(pid=pid, created=456)
    app = Mock()
    app.localizedName.return_value = "Test App"
    app.isHidden.return_value = False
    return picker.WindowTarget(app, window, process, title)


class TargetTests(unittest.TestCase):
    def test_reused_pid_is_not_the_same_target(self):
        first, second = target(), target()
        second.process.created = 789
        self.assertFalse(first.matches(second))

    def test_valid_window_need_not_appear_in_axwindows(self):
        item = target()
        with patch.object(picker.info.AS, "AXUIElementGetPid", return_value=(0, 123)), \
             patch.object(picker.info, "_ax_copy", return_value=(0, "AXWindow")):
            self.assertEqual(item.checked(), "window")
        item.process.checked.assert_called_once()

    def test_wrong_pid_and_invalid_ax_element_are_rejected(self):
        for pid, error in ((124, 0), (123, -25202)):
            with self.subTest(pid=pid, error=error), \
                 patch.object(picker.info.AS, "AXUIElementGetPid", return_value=(0, pid)), \
                 patch.object(picker.info, "_ax_copy", return_value=(error, "AXWindow")):
                with self.assertRaisesRegex(RuntimeError, "原窗口已关闭"):
                    target().checked()

    def test_hit_test_converts_global_coordinates_and_excludes_self(self):
        screen = Mock()
        screen.frame.return_value = SimpleNamespace(size=SimpleNamespace(height=900))
        with patch.object(picker.info, "AppKit") as appkit, \
             patch.object(picker.info.AS, "AXUIElementCreateSystemWide", return_value="system"), \
             patch.object(picker.info.AS, "AXUIElementSetMessagingTimeout"), \
             patch.object(picker.info.AS, "AXUIElementCopyElementAtPosition", return_value=(0, "self")) as hit, \
             patch.object(picker.info.AS, "AXUIElementGetPid", return_value=(0, picker.os.getpid())):
            appkit.NSEvent.mouseLocation.return_value = SimpleNamespace(x=-100, y=1000)
            appkit.NSScreen.screens.return_value = [screen]
            self.assertIsNone(picker.window_at_pointer())
            hit.assert_called_once_with("system", -100, -100, None)

    def test_list_includes_current_window_omitted_from_axwindows(self):
        app = Mock()
        app.processIdentifier.return_value = 123
        app.isTerminated.return_value = app.isHidden.return_value = False
        def attr(element, name, default=""):
            return {"AXWindows": ["one"], "AXFocusedWindow": "two", "AXMainWindow": "one",
                    "AXMinimized": element == "two"}.get(name, default)
        with patch.object(picker.info, "AppKit") as appkit, \
             patch.object(picker.info.AS, "AXUIElementCreateApplication", return_value="app"), \
             patch.object(picker.info.AS, "AXUIElementSetMessagingTimeout"), \
             patch.object(picker.info, "_ax_attr", side_effect=attr), \
             patch.object(picker.WindowTarget, "capture", side_effect=lambda app, window: window):
            appkit.NSWorkspace.sharedWorkspace.return_value.runningApplications.return_value = [app]
            self.assertEqual(picker.list_windows(), ["one"])
            self.assertEqual(picker.list_windows(True), ["one", "two"])


class PickerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.root, self.control, self.border = Mock(), Mock(), Mock()
        self.selected, self.status = Mock(), Mock()
        self.picker = picker.WindowPicker(self.root, self.control, self.border,
                                          self.selected, self.status, lambda: True)
        self.control.grab_current.return_value = self.control

    def test_release_selects_only_after_releasing_capture_and_border(self):
        item = target()
        def selected(value):
            self.assertIs(value, item)
            self.assertFalse(self.picker.dragging)
            self.control.grab_release.assert_called_once()
            self.border.hide.assert_called()
        self.selected.side_effect = selected
        with patch.object(picker, "window_at_pointer", return_value=item):
            self.picker.start()
            self.picker.motion()
            self.picker.release()
        self.selected.assert_called_once_with(item)

    def test_cancel_never_selects_and_cleans_up(self):
        self.picker.start()
        self.picker.cancel()
        self.picker.release()
        self.control.grab_release.assert_called_once()
        self.selected.assert_not_called()
        self.assertFalse(self.picker.dragging)

    def test_hit_test_error_releases_capture(self):
        with patch.object(picker, "window_at_pointer", side_effect=RuntimeError("gone")):
            self.picker.start()
            self.picker.motion()
        self.control.grab_release.assert_called_once()
        self.assertFalse(self.picker.dragging)
        self.status.assert_called_with("gone")

    def test_hidden_owner_cancels_drag(self):
        self.picker.start()
        self.picker.unmap(SimpleNamespace(widget=self.root))
        self.assertFalse(self.picker.dragging)
        self.control.grab_release.assert_called_once()

    def test_capture_loss_clears_outline_without_selecting(self):
        self.picker.start()
        self.control.grab_current.return_value = None
        self.picker.motion()
        self.assertFalse(self.picker.dragging)
        self.selected.assert_not_called()
        self.border.hide.assert_called()

    def test_outline_stays_within_small_and_negative_coordinate_windows(self):
        edges = picker.outline_rectangles(-200, -50, 2, 3)
        for (x, y), (w, h) in edges:
            self.assertGreaterEqual(x, -200)
            self.assertGreaterEqual(y, -50)
            self.assertLessEqual(x + w, -198)
            self.assertLessEqual(y + h, -47)


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.ui = inspector.WindowInspector.__new__(inspector.WindowInspector)
        self.ui.root = Mock()
        self.ui.status = Mock()
        self.ui.border = Mock()
        self.ui.topmost = Mock()
        self.ui.topmost.get.return_value = True
        self.ui.return_timer = self.ui.preview_timer = None
        self.ui.activation_timer = None

    def test_preview_cancellation_restores_level_and_cancels_both_timers(self):
        self.ui.return_timer, self.ui.preview_timer = "return", "restore"
        self.ui.cancel_preview()
        self.ui.root.after_cancel.assert_any_call("return")
        self.ui.root.after_cancel.assert_any_call("restore")
        self.ui.root.attributes.assert_called_with("-topmost", True)
        self.assertIsNone(self.ui.return_timer)
        self.assertIsNone(self.ui.preview_timer)

    def test_preview_failure_returns_focus_and_removes_outline(self):
        self.ui.selection = target()
        self.ui.feedback = Mock()
        with patch.object(inspector.info, "_frontmost_app", return_value=None), \
             patch.object(inspector, "activate_window") as activate:
            self.ui.finish_preview(self.ui.selection)
        activate.assert_called_once_with(self.ui.root)
        self.ui.border.hide.assert_called_once()
        self.ui.root.attributes.assert_called_with("-topmost", True)

    def test_selected_hint_does_not_clear_target(self):
        self.ui.selector = Mock()
        self.ui.selector.current.return_value = 0
        self.ui.busy = False
        self.ui.entries = [target()]
        self.ui.sync_selector = Mock()
        self.ui.run = Mock()
        self.ui.select_window()
        self.ui.sync_selector.assert_called_once()
        self.ui.run.assert_not_called()

    def test_pid_search_does_not_match_pid_prefix(self):
        self.ui.entries = [target(pid=123), target(pid=12)]
        self.ui.load = Mock()
        self.ui.find_in_list("PID:12")
        self.ui.load.assert_called_once_with(self.ui.entries[1])

    def test_stale_window_is_cleared_before_any_action(self):
        self.ui.selection = Mock()
        self.ui.selection.checked.side_effect = RuntimeError("gone")
        self.ui.clear_target, self.ui.sync_selector = Mock(), Mock()
        with self.assertRaisesRegex(RuntimeError, "gone"):
            self.ui.checked_window()
        self.ui.clear_target.assert_called_once()
        self.ui.sync_selector.assert_called_once()

    def test_delayed_refresh_does_not_retarget_new_selection(self):
        first = target()
        self.ui.selection = target(pid=456)
        self.ui.busy = False
        self.ui.run = Mock()
        self.ui.refresh_after_action(first)
        self.ui.root.after.call_args.args[1]()
        self.ui.run.assert_not_called()


class TooltipTests(unittest.TestCase):
    def test_hover_stays_visible_until_hidden(self):
        root = Mock()
        with patch.object(tooltip, "_create_panel") as create:
            tip = tooltip.TkTooltip(root)
            tip.show("hint", 0)
            root.after.assert_not_called()
            tip.hide()
            create.return_value.close.assert_called_once()

    def test_tk_tooltip_replacement_cancels_old_timer_without_changing_app_policy(self):
        root = Mock()
        root.after.return_value = "timer"
        first, second = Mock(), Mock()
        with patch.object(tooltip, "_create_panel", side_effect=[first, second]) as create:
            tip = tooltip.TkTooltip(root)
            tip.show("first", 3000)
            tip.show("second")
            create.assert_called_with("second", "info", standalone=False)
            first.close.assert_called_once()
            root.after_cancel.assert_called_once_with("timer")
            tip.hide()
            second.close.assert_called_once()
            self.assertIsNone(tip.panel)


if __name__ == "__main__":
    unittest.main()
