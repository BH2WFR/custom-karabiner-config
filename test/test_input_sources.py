"""Input-source selection logic; system selection calls are mocked."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import input_sources as sources


class InputSourceTests(unittest.TestCase):
    def test_previous_source_wins(self):
        self.assertEqual(sources.choose_input_source('A', ['A', 'B', 'C'], 'C', []), 'C')

    def test_history_skips_current_and_unavailable_sources(self):
        history = [{'Input Mode': 'missing'}, {'Input Mode': 'A'}, {'Input Mode': 'C'}]
        self.assertEqual(sources.choose_input_source('A', ['A', 'B', 'C'], None, history), 'C')

    def test_layout_history(self):
        history = [{'InputSourceKind': 'Keyboard Layout', 'KeyboardLayout Name': 'ABC'}]
        self.assertEqual(sources.choose_input_source('rime', ['rime', 'com.apple.keylayout.ABC'], None, history),
                         'com.apple.keylayout.ABC')

    def test_only_one_source_is_an_error(self):
        with self.assertRaisesRegex(RuntimeError, 'No other'):
            sources.choose_input_source('A', ['A'], 'A', [])

    def test_selection_failure_is_reported(self):
        with patch.object(sources._TIS, 'TISSelectInputSource', return_value=-50):
            with self.assertRaisesRegex(RuntimeError, '-50'):
                sources._select('A', 1)

    def test_success_is_verified(self):
        with patch.object(sources._TIS, 'TISSelectInputSource', return_value=0), \
             patch.object(sources, 'current_input_source', return_value='A'):
            sources._select('A', 1)

    def test_silent_failure_is_not_reported_as_success(self):
        with patch.object(sources._TIS, 'TISSelectInputSource', return_value=0), \
             patch.object(sources, 'current_input_source', return_value='B'), \
             patch.object(sources.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'did not change'):
                sources._select('A', 1)


if __name__ == '__main__':
    unittest.main()
