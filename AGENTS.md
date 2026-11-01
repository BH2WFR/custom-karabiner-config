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
- Update this helper inventory when adding or changing reusable APIs; the user has authorized these maintenance updates. Keep implementation details in the source.

## Updating These Instructions

- For structural or instruction changes beyond the reusable-helper inventory above, ask the user before modifying this file.
