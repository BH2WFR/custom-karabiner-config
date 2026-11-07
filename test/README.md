# Regression Tests

Run from the repository root on macOS with the project's Miniconda Base interpreter:

```bash
/opt/miniconda3/bin/python3 -m unittest discover -s test -v
```

The tests cover screen-keyboard layout, hover colors, action feedback and held-key state, modifier sides, event routing and cancellation, configured ZL shortcuts, and input-source selection. Native button checks use an unshown panel. Keyboard output, tooltips, layer writes, permission requests and input-source changes are mocked; no windows open or clipboard contents change. Configuration checks read the current `karabiner.json` without modifying it.

Run one file with, for example:

```bash
/opt/miniconda3/bin/python3 -m unittest discover -s test -p test_screen_keyboard.py -v
```

These tests require macOS frameworks but no Accessibility permission or running Karabiner instance. They do not verify actual RDP delivery or system key repeat. Interactive GUI/mouse probes remain in ignored `tmp/` and are not part of this suite. `scripts/test_keyboard.py` is the mini keyboard application, not a test suite.
