# Project Instructions

## Session Startup

- Read `README.md` once at the beginning of every session to understand the project's current features, mappings, layers, dependencies, and migration notes before making changes.

## Configuration And Layout

- `karabiner.json` is the Karabiner-Elements configuration file.
- The active profile in `karabiner.json` is named `ZL`; make configuration changes in that profile unless the user explicitly requests another profile.
- Project scripts are stored in `./scripts`.
- Run project scripts and Python checks with the local Miniconda Base interpreter at `/opt/miniconda3/bin/python3`. Preserve `-S` for commands that intentionally use it in `karabiner.json`.
- Put disposable project-local files in `./tmp`; this directory is ignored by Git.

## Implementation

- Implement additions and changes concisely and in sympathy with the existing structure.
- Do not keep appending one-off rules, branches, or patches when they create duplication or obscure the design. Refactor scripts or configuration when that is the clearer and more maintainable solution.
- Keep changes focused on the requested behavior and preserve unrelated user work.

## Documentation

- After completing a feature or behavior change, update `README.md` so its mappings, behavior, dependencies, and migration instructions remain accurate.

## Reusable Script Helpers

- `scripts/gui_helpers.py`: one-time Tk window activation on macOS and copying text. Importing it must not create or activate a GUI.
- `scripts/menu_command.py`: `launch_command(spec)` runs a configured shell command in Terminal or a separate Tk output window; reuse it for quick-menu command execution.
- `scripts/front_window_info.py`: `collect_info(app, window)` collects structured application, bundle and AX window information for an explicit target; the CLI remains available.
- `scripts/center_front_window.py`: `center_window(args, window=None)` accepts an explicit AX window. GUI callers must pass their captured window instead of operating on the current frontmost window.
- `scripts/process_actions.py`: `ProcessTarget` checks PID/start-time identity; `prepare_restart()` captures the executable, full argv, cwd and environment before termination. GUI callers must confirm kill/restart first. Restart uses an argument array without a shell and waits for exit; it must not silently force-kill on timeout.
- `scripts/keyboard_events.py`, `scripts/secondary_clipboard.py`, `scripts/paste_without_format.py`, and `scripts/tooltip.py` provide the existing keyboard, pasteboard, text-normalization and non-activating notification helpers. Reuse them for related features.
- `scripts/tooltip.py`: `panel_frame_near_pointer(mouse, bounds, width, height)` positions and fits an AppKit window frame near the pointer within a screen's visible bounds, without creating or activating a window.
- `scripts/keyboard_events.py`: `current_modifier_flags()` and `format_modifier_flags(..., include_sides=True)` inspect session modifiers, decoding sides from flags rather than `CGEventSourceKeyState`; `MODIFIER_KEYS` includes left/right flags. `post_key_event()` defaults to the Session tap so script output bypasses Karabiner's HID fallback; screen-keyboard/test input intended for remapping uses `event_tap=HID_EVENT_TAP`, with `flags_changed=True` for modifier transitions. `post_keystroke()` sends complete modifier-down/key-down/key-up/modifier-up chords, waiting 10 ms by default after each event, including the final release before process exit; `interval` and `unicode_text` support faster text typing through the same sender. Optional `cancel_event` interrupts waits and prevents further key-downs while still releasing pressed keys; `post_key_event(..., unicode_text=...)` sends Unicode text. Reuse these for script-generated keyboard output instead of independent CoreGraphics or System Events calls.
- `scripts/send_keys.py`: `send_sequence()` and its ordered `--key` / `--text` CLI run one-shot keyboard macros through `keyboard_events.post_keystroke()`. Reuse this instead of mixing asynchronous shell releases with native key output. `keyboard_events.KEY_CODES` and `US_KEY_CODES` provide shared virtual keycode tables.
- `scripts/keyboard_events.py`: `tap_caps_lock()` sends a short native Caps Lock press through the Session tap, preserving system-generated flags (`post_key_event(..., flags=None)`). Use it for Caps Lock input-source behavior; `toggle_caps_lock.LockState` changes the lock state directly instead. `request_post_events()` requests macOS event-posting authorization only when missing; call it explicitly at interactive startup, not during status checks or imports.
- `scripts/test_keyboard.py`: `KeyboardState(event_keys=None, *, event_tap=HID_EVENT_TAP)` owns screen-held keys and the Caps variable; `event_keys` optionally supplies input keycode/flag triples. `check_setup()` only checks fallback/permissions, and `run_panel()` dispatches non-activating AppKit events without idle polling. The full keyboard in `scripts/screen_keyboard.py` checks live fallback availability on interaction and uses Session output for ordinary-keyboard mode; `create_panel(..., remember_frame=False)` supports isolated layout tests without saving window geometry.
- `scripts/input_sources.py`: `switch_input_source(previous=None)` selects an enabled keyboard source through macOS TIS and returns the old ID for the next toggle; it uses system history when no previous ID is available. `current_input_source()` and `select_input_source(id)` support explicit reads/restoration. Selection verifies the result without posting keys, activating a window, or enabling disabled sources.
- Screen-keyboard holds use `keyboard_events.post_key_event()` for one down/up pair, leaving repetition to the system/input path. RDP screen input uses final modifier keycodes through the Session tap; non-RDP layer input uses HID aliases. `post_keystroke()` honors explicit left/right flags (including both sides); generic-only modifier flags retain the left-side default. `KeyboardState` treats an explicit `event_keys["Caps"]` as a held key instead of the local Caps variable (RDP uses F1). `KeyboardState.release(keep=())` optionally retains named held keys while clearing the others and the local Caps variable. Lifecycle cleanup still releases everything.
- Update this helper inventory when adding or changing reusable APIs; the user has authorized these maintenance updates. Keep implementation details in the source.

## Updating These Instructions

- For structural or instruction changes beyond the reusable-helper inventory above, ask the user before modifying this file.
