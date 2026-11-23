# Regression Tests

Run from the repository root on macOS with the project's Miniconda Base interpreter:

```bash
/opt/miniconda3/bin/python3 -m unittest discover -s test -v
```

The tests cover modifier sides, event routing and cancellation, configured ZL shortcuts (including independent GUI/heavy-tool launches and direct short macros), and window-inspector discovery, picking, preview cleanup and tooltip scheduling. Keyboard output, tooltips and window operations are mocked; no windows open or clipboard contents change. Configuration checks read the current `karabiner.json` without modifying it. Screen-keyboard UI tests are maintained in PersonalScripts.

Run one file with, for example:

```bash
/opt/miniconda3/bin/python3 -m unittest discover -s test -p test_keyboard_tools.py -v
```

These tests require macOS frameworks but no Accessibility permission or running Karabiner instance. They do not verify actual RDP delivery or the external screen keyboard's UI. Interactive GUI/mouse probes remain in ignored `tmp/` and are not part of this suite.
