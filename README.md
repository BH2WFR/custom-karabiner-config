# Personal Karabiner-Elements Configuration

**Personal** **Karabiner-Elements setup** for macOS.

Designed around a two-level **`Caps` layer** with context-aware remapping for RDP sessions and a named secondary clipboard.

Repository: [BH2WFR/custom-karabiner-config](https://github.com/BH2WFR/custom-karabiner-config)

Related tools: [BH2WFR/PersonalScripts](https://github.com/BH2WFR/PersonalScripts), including the Unicode Inspector used by `Caps+7`.

Sister project for Windows: [BH2WFR/custom-autohotkey-config](https://github.com/BH2WFR/custom-autohotkey-config).

**LICENSE**: GPL v3

## Abbreviation Reference

| Abbreviation | Meaning |
| --- | --- |
| `Caps` | Caps Lock key |
| `Cmd` | Command key; side unspecified |
| `LCmd` / `RCmd` | Left / Right Command key |
| `Ctrl` | Control key; side unspecified |
| `LCtrl` / `RCtrl` | Left / Right Control key |
| `Opt` | Option (Alt) key; side unspecified |
| `LOpt` / `ROpt` | Left / Right Option key |
| `Fn` | Function or Globe key |
| `App` / `Menu` | Application/Menu key on an external keyboard |
| `Kbd` | Keyboard, as used in rule names such as `BuiltInKbd` and `ExternalKbd` |
| `[RDP]` | Remote-window rule group: Microsoft Remote Desktop, Windows App, or UU Remote (UU远程); |
| Physical key | The key actually pressed on the keyboard, before this configuration remaps it |
| Mapped key | The key produced by a mapping and received by macOS or the target application |

In shortcut notation, `A+B` means that the keys are held together. `[LOpt/RCmd/LCmd]` means any one of those physical keys; the square brackets do not mean that the modifier is optional. Secondary Layer triggers use physical key names, before remapping.

## Profile Settings

- The active profile is `ZL`.
- Karabiner's notification window is disabled globally with `enable_notification_window: false`.
- `enable_cgeventtap_fallback` is a global experimental switch: `true` enables it and `false` disables it; saving the configuration applies the change. Close the screen/test keyboard and release all keys before switching. The screen keyboard never changes this setting.
- The inactive `Default profile` contains a simple `F1` to `F13` mapping. It does not affect the selected `ZL` profile.

## Keyboard Mappings

| Physical Key | Normal | RDP <br />(Microsoft Remote Desktop / Windows App / UU Remote) |
| --- | --- | --- |
| `Caps` | Activates **Caps Primary Layer** (hold) / `Caps` (tap) | `F1` |
| `F1` | `F1` | Activates **Caps Primary Layer** (hold) / `F1` (tap) |
| `Fn` (globe key) | `LCmd` | `LCtrl` |
| `LCtrl` <br />(built-in keyboard) | `Fn` | `Fn` |
| `LCtrl` <br />(external keyboard) | `LCmd` | No remap (still `LCtrl`) |
| `LOpt` | No remap (still `LOpt`) | `LCmd` |
| `LCmd` | `LCtrl` | `LOpt` |
| `RCmd` | `ROpt` | `ROpt` |
| `ROpt` <br />(built-in keyboard / Logi Mechanical) | `RCmd` | `RCtrl` |
| `RCtrl` <br />(external keyboard) | `RCmd` | No remap (still `RCtrl`) |
| `App/Menu` (external keyboard) | `Fn` | No remap |

**Modifier layout summary:**

- **Normal**: `Caps` activates `caps_primary_layer`; after `Caps` is already held, physical `LOpt`, `RCmd` or `LCmd` activates `caps_secondary_layer` and suppresses that key's normal modifier output. `Cmd`/`Ctrl` are swapped (Mac-style bottom row on external keyboards); `Fn` becomes `Cmd`.
- **RDP**: `Caps` becomes `F1`; physical `F1` directly controls the same `caps_primary_layer` variable while held and remains `F1` when tapped. The Caps Secondary Layer is disabled, and physical `LOpt`/`RCmd`/`LCmd` follow their normal RDP mappings. Modifier positions mimic a standard Windows keyboard (`Ctrl` where `Cmd` normally is, etc.).

The RDP mappings are separate Complex Modification rules:

- `[Map][RDP]: [Caps] to [F1]`
- `[Layer][RDP]: [F1] to [Caps Primary Layer]`

They can be enabled or disabled independently without changing the normal Caps Primary Layer rule.

## Hotkey Reference

One-shot key shortcuts and editing sequences use `scripts/send_keys.py` and the shared keyboard sender, with complete modifier press/release events that bypass the HID fallback. Modifier remapping, held `Fn` and mouse output remain native Karabiner mappings.

### Caps Primary Layer

Hold `Caps` to activate `caps_primary_layer`. Release it to deactivate the layer. Tapping `Caps` alone sends `Caps` on key-up (i.e., on release), which toggles Caps Lock or switches input method depending on system settings.

When Microsoft Remote Desktop / Windows App / UU Remote is frontmost, hold physical `F1` instead. It sets `caps_primary_layer` directly on key-down and clears it on key-up; it does not map through `Caps`. Tapping `F1` alone still sends `F1`.

#### Editing

| Keys | Function | Notes |
| --- | --- | --- |
| `Caps+C` | Copy (`Cmd+C`) | |
| `Caps+Shift+C` | Copy entire line | |
| `Caps+X` | Cut (`Cmd+X`) | |
| `Caps+Shift+X` | Cut entire line | |
| `Caps+4` | Wrap selected text in `${` and `}` | Replaces the selection through plain-text paste |
| `Caps+6` / `Caps+Shift+6` | Lowercase / uppercase selected text | Supports Unicode |
| `Caps+Shift+7` | Title-case selected text | Capitalizes each word and lowercases the remaining letters |
| `Caps+7` | Inspect selected text in the external Unicode Inspector | Automatically copies the selection and restores the previous clipboard. On copy failure, opens a blank window, then shows an error tooltip. Use `Paste` / `Analyze` to inspect edited text |
| `Caps+V` | **Paste as plain text** | Uses `scripts/paste_without_format.py` (depends on `pyobjc-framework-Cocoa`); sends a paced `Cmd+V` press/release sequence through CoreGraphics to avoid stuck modifiers; <br />when **copying files from Finder, pastes file paths** (one per line for multiple files); rejects content without text and keeps the clipboard unchanged |
| `Caps+Shift+V` | **Advanced paste** | Uses `scripts/paste_without_format.py --advanced`; releases `Shift` and posts `Cmd+V` through CoreGraphics; <br />strips zero-width chars, normalises spaces, converts full-width→half-width, de-quotes, splits ligatures, CJK-aware line-break removal (while copied from paragraphs from a PDF file), path-slash conversion — then pastes with `Cmd+V` |
| `Caps+Tab` | Indent selected lines | Uses `scripts/indent_select_lines.py` <br />(stdlib only) |
| `Caps+Shift+Tab` | Unindent selected lines | Uses `scripts/indent_select_lines.py` <br />(stdlib only) |
| `Caps+Backspace` | **Delete the first character of the preceding two-character word** | e.g. with the cursor after `结果`: <br />moves left → deletes `结` → moves right, **leaving `果` before the cursor** |
| `Caps+Shift+Backspace` | Delete current line | |
| `Caps+;` | Insert `;` **at end of line** | Sends the literal ASCII character through Unicode events, without the clipboard or Chinese punctuation conversion |
| `Caps+Shift+;`<br />`Caps+'` | Insert `:` **at end of line** | Same Unicode input; releases Shift before moving the cursor |
| `Caps+,` / `Caps+Shift+,` | Insert `,` / `\` **at end of line** | Releases Shift before moving; inserts literal ASCII punctuation without the clipboard |
| `Caps+Enter` | **Go to end of line + add newline** | |
| `Caps+Shift+Enter` | Insert blank line above current | |
| `Caps+Space` | Insert full-width space (U+3000) | Uses `scripts/send_keys.py` on key-up; posts Unicode events without modifying the clipboard |
| `Caps+B` | `Fn` | Sends `keyboard_fn` |
| `Caps+Z` | Type clipboard text as keystrokes | ASCII uses US-layout keys; non-ASCII uses experimental Unicode events. Default event interval: 10 ms; leaves the clipboard unchanged |
| `Caps+Shift+Z` | Repair clipboard images | When Windows App controls a remote computer over RDP, images copied on that computer can arrive in this Mac's clipboard as TIFF data mislabeled as PNG. `scripts/repair_clipboard_images.py` converts them into correctly encoded PNG images; runs once without confirmation or automatic paste |
| `Caps+\`<br />`Caps+\|` | ISO `\|` key | Sends `non_us_backslash` / `Shift+non_us_backslash` |

#### Mouse / Navigation

| Keys | Function | Notes |
| --- | --- | --- |
| `Caps+I` / `J` / `K` / `L` | Move mouse pointer (1 logical-coordinate unit) | Uses `scripts/move_mouse_pointer.py`; <br />depends on `pyobjc-framework-Quartz`; `--actual-pixels` is not enabled in the current mappings |
| `Caps+Shift+I` / `J` / `K` / `L` | Move mouse pointer (10 logical-coordinate units) | Uses `scripts/move_mouse_pointer.py`; <br />depends on `pyobjc-framework-Quartz`; `--actual-pixels` is not enabled in the current mappings |
| `Caps+U` | Left mouse click at pointer | Uses `scripts/move_mouse_pointer.py --key_click button1`; <br />depends on `pyobjc-framework-Quartz` |
| `Caps+O` | Right mouse click at pointer | Uses `scripts/move_mouse_pointer.py --key_click button2`; <br />depends on `pyobjc-framework-Quartz` |
| `Caps+-` | **Zoom out (trackpad pinch)** | Uses `scripts/trackpad_zoom.py`; <br />**simulates a native trackpad pinch-zoom gesture** — **not** scroll-wheel zoom or `Cmd+-`; <br />in browsers, this zooms the page like a trackpad pinch, unlike `Cmd+-` which changes font size |
| `Caps+=` | **Zoom in (trackpad pinch)** | Uses `scripts/trackpad_zoom.py`; <br />same as above — native pinch gesture, different from scroll-wheel or `Cmd+=` |
| `Caps+Shift+-` | Horizontal scroll left | |
| `Caps+Shift+=` | Horizontal scroll right | |

#### Other

| Keys | App | Function | Notes |
| --- | --- | --- | --- |
| `Caps+1` | Any | Show frontmost app, layer and modifiers | Non-activating English tooltip for 2.5 seconds; sides are decoded from session flags, or marked unavailable. The layer is captured at trigger time; modifiers are read when the script runs. Secondary Layer triggers suppress their normal modifier output |
| `Caps+A` | Any except Anki | Toggle local Caps Lock | Shows the actual ON/OFF state for 600 ms; does not switch input sources |
| `Caps+E` | Any except Anki | Open a native quick-access menu at the pointer | Folders, system settings and utilities; includes Homebrew's cache when installed. Select with the mouse |
| `Caps+Q` | Any except Anki | `Esc` | Preserves additional mapped modifiers, e.g. `Cmd+Caps+Q` sends `Cmd+Esc` |
| `` Caps+` `` | Any | Release both sides of `Cmd`, `Opt`, `Ctrl` and `Shift`, and turn Caps Lock off | Also works while additional modifiers are held |
| `Caps+P` | Any | **Toggle built-in display on/off** | Uses `scripts/toggle_builtin_screen.py` <br />(ctypes, Apple Silicon only); <br />requires **external monitor** |
| `Caps+R` | Any except Anki | Fit frontmost window to current display, then center | Uses `scripts/center_front_window.py --fit`; <br />shrinks only if the window is larger than the target display; <br />pass `--display main` to target the main display instead; <br />requires Accessibility permission for Python |
| `Caps+Shift+R` | Any except Anki | Resize current window to 1024 x 768 logical points and center | Centers on the window's original display without fitting; if the app enforces a different size, centers the actual size and warns |
| `Caps+S` | Any except Anki | Open or restore the screen keyboard | Requires `~/Applications/Caps Keyboard.app`; does not enable fallback automatically |
| `Caps+W` | Any except Anki | Inspect and manage the current window | Separate app/window tabs, arguments and AX children; double-click copies a single cell. Grouped actions for closing/centering/resizing windows, files and process management; kill/restart requires confirmation |

Image repair, window centering, display toggling and rejected text input/paste show English tooltips without taking focus: gray for results, amber for warnings, red for errors.

Selected-text tools use `Cmd+C` and restore the previous clipboard after processing. `Caps+7` opens the Unicode Inspector from PersonalScripts; its UI and character analysis are maintained there.

The window inspector keeps the captured target when it comes to the foreground. Restart preserves the process's argument list, working directory and readable environment; it cancels if these cannot be obtained or the old process does not exit. A restart launches the executable directly, so applications managed by launchers or services may need their own restart mechanism.

### Caps Secondary Layer

The **Caps Secondary Layer** is a general-purpose extension layer available only outside RDP. **Hold `Caps` first, then physical `LOpt`, `RCmd` or `LCmd`.** Pressing a trigger before `Caps` applies its normal mapping and does not retroactively activate the layer.

Normally, `LOpt` remains `LOpt`, `RCmd` maps to `ROpt`, and `LCmd` maps to `LCtrl`. As Secondary Layer triggers, their normal modifier output is suppressed; all three operate the same shortcuts.

In RDP, none of these keys enters Secondary, even while `F1` activates Primary. Their normal mappings remain `LOpt` → `LCmd`, `RCmd` → `ROpt`, and `LCmd` → `LOpt`.

#### Secondary Clipboard Shortcuts

The **secondary clipboard** is the first set of functions assigned to the Caps Secondary Layer; additional functions can be added to this layer later.

| Keys | Function | Notes |
| --- | --- | --- |
| `Caps+[LOpt/RCmd/LCmd]+C` | Copy selection to the secondary clipboard as plain text | Uses `scripts/secondary_clipboard.py copy` and CoreGraphics keyboard events; image-only and other content without a text representation is rejected; Finder files are converted to full paths |
| `Caps+[LOpt/RCmd/LCmd]+Shift+C` | Copy current line to the secondary clipboard as plain text | Uses the same whole-line selection behavior as `Caps+Shift+C` |
| `Caps+[LOpt/RCmd/LCmd]+X` | Cut selection to the secondary clipboard as plain text | Confirms that a text representation is available before sending `Cmd+X` |
| `Caps+[LOpt/RCmd/LCmd]+Shift+X` | Cut current line to the secondary clipboard as plain text | Uses the same whole-line selection and newline cleanup as `Caps+Shift+X` |
| `Caps+[LOpt/RCmd/LCmd]+V` | Paste the secondary clipboard as plain text | Temporarily writes to the general pasteboard, posts `Cmd+V` through CoreGraphics, then restores the previous general pasteboard |
| `Caps+[LOpt/RCmd/LCmd]+Shift+V` | Advanced paste from the secondary clipboard | Same cleanup as `Caps+Shift+V`; preserves both clipboards |
| `Caps+[LOpt/RCmd/LCmd]+Z` | Type secondary clipboard text as keystrokes | Same ASCII / experimental Unicode input as `Caps+Z`; preserves both clipboards |

ASCII typing uses US key positions: use US/ABC English input locally and a matching English keyboard layout remotely. Unicode support depends on the target application; browser VNC consoles may not accept it. `type_clipboard.py --ascii-only` rejects non-ASCII text before typing; `--interval-ms` controls the wait after each key/modifier event, not each character, and `--pasteboard-name` selects a named clipboard. Other control characters and unpaired surrogates are rejected before any input.

Tab and line breaks send real Tab/Enter keys (and may submit a command). During typing, `Esc` stops input and is swallowed, including repeats and key-up, so it does not reach the target application. Pressed keys are released, but already queued input cannot be withdrawn. Esc works normally outside typing. Switching applications also stops typing; avoid switching tabs within the same browser while it runs.

The secondary clipboard is stored in a named macOS `NSPasteboard`, not a temporary file. The script defaults to `com.personal-scripts.secondary-clipboard` and also supports `--pasteboard-name`, `--multi-items`, `paste --advanced`, `type`, and `clear` from the command line. There are currently no hotkeys for multi-item operations or clearing the secondary clipboard.

#### Text Tools

| Keys | Function | Notes |
| --- | --- | --- |
| `Caps+[LOpt/RCmd/LCmd]+Tab` | Paste a literal tab character | Bypasses Tab-key navigation; the target must accept pasted tabs |
| `Caps+[LOpt/RCmd/LCmd]+Return` | Paste a literal newline (`\n`) | Does not send a Return key; the target must accept pasted line breaks |
| `Caps+[LOpt/RCmd/LCmd]+T` | Paste a setter name | Ordinary clipboard `myItem` becomes `setMyItem`; except Anki |
| `Caps+[LOpt/RCmd/LCmd]+Shift+T` | Paste a getter name | Ordinary clipboard `myItem` becomes `getMyItem`; except Anki |

These tools preserve the ordinary clipboard. Getter/setter names support Unicode and must contain a single name without whitespace.

## Personal Hotkeys

The shortcuts in this section are **tailored** to my own Rime, Anki, and Cherry Studio workflows. **Other users are advised to disable the corresponding Karabiner rules** or remove the app-specific manipulators unless they have configured the same application shortcuts.

| Hotkey or behavior | App | Function | Requirement |
| --- | --- | --- | --- |
| Tap `Caps` | Anki | Sends an additional `F18` dummy key after `Caps` | Personal workaround for Anki/Qt swallowing the first real key after an input-source change; remove the Anki-specific `Caps` manipulator if not needed |
| `Caps+.` | Rime | Toggle punctuation mode by sending `Ctrl+F19` | Rime must configure `F19` as the corresponding hotkey |
| `Caps+Q`/`W`/`E`/`R`/`T`/`A`/`S`/`D`/`F`/`G` (+`Shift` where configured) | Anki | Various card review shortcuts | Anki must configure the corresponding `F13`-based shortcuts |
| `Cmd+Enter` | Cherry Studio | Send `Ctrl+Enter` | Disable unless this matches the desired Cherry Studio send shortcut |

## Other Hotkeys

| Hotkey | App | Function | Notes |
| --- | --- | --- | --- |
| `F2` | Any | Middle mouse button | Intended mainly for **middle-button drag/pan** operations in **CAD applications**; optional rule, disabled by default with `enabled: false` |

## Screen Keyboard

Only one keyboard instance runs at a time. Both first launch and reopening place the window near the pointer, within that display's usable area, without taking keyboard focus. Reopening restores and raises the existing window.

The layer key reads `Layer`, or `Layer(F1)` in RDP. The globe input-source button sits between F12 and Ins and switches without a success tooltip. In the toolbar, Minimize sits immediately left of the `...` menu for extended keys and keyboard actions.

The numeric-keypad toolbar toggle stays highlighted while the keypad is expanded. The five-row keypad sits directly beside the main keys, aligned at the top and bottom, with a green Enter key. Its `Num` / `Nav` button uses dark rust for numbers, peach for navigation and light peach while pressed. This is an independent numbers/navigation mode, not the system or remote NumLock state. Numbers use ordinary digit keys to avoid remote NumLock dependence; navigation mode sends Home/End/arrows/Ins/Del (the center `5` is inactive). Keypad output bypasses Caps layers and preserves mapped modifiers.

Keys show pressed colors immediately, without fade animations. The keyboard content area uses the standard arrow pointer; window-edge resizing retains the system cursor.

Build/register the local Dock launcher with the existing Conda environment and Xcode Command Line Tools:

```bash
/opt/miniconda3/bin/python3 installation/install_screen_keyboard.py
```

The installer creates `~/Applications/Caps Keyboard.app`; drag it into Dock. It uses this checkout and Python installation, not a bundled Python runtime. Grant **Caps Keyboard** Accessibility permission for key output. Enable fallback manually to use Karabiner layers; ordinary keyboard mode works with fallback off. The installer changes neither Dock settings nor fallback.

## Migration Guide

This repository is a personal configuration, **not a drop-in universal preset**. If you use it on another Mac, review the sections below before replacing your own `~/.config/karabiner` directory.

### System Requirements

- macOS (Apple Silicon or Intel)
- [Karabiner-Elements](https://karabiner-elements.pqrs.org/) (latest version)
- Miniconda

### Recommended Porting Workflow

1. Back up your current Karabiner config:

```bash
cp -a ~/.config/karabiner ~/.config/karabiner.backup.$(date +%Y%m%d-%H%M%S)
```

2. Clone or copy this repository to `~/.config/karabiner`.
3. Open `karabiner.json` in Karabiner-Elements and disable rules you do not need before relying on the setup daily.
4. Check all script paths, device identifiers, app bundle identifiers, and external dependencies listed below.
5. Grant macOS permissions, then test the Caps Primary Layer before testing app-specific shortcuts.

### Paths You May Need to Change

Most shell commands **assume this repository is located at**:

```text
${HOME}/.config/karabiner
```

The current configuration launches scripts with the **Python** interpreter from the local **Miniconda Base** environment:

```text
/opt/miniconda3/bin/python3
```

Using an absolute path is intentional: Karabiner does not run commands in an interactive shell, so `PATH`, Conda activation, and shell aliases may not match your Terminal. To find the absolute Python path in your own Conda Base environment, run:

```bash
BASE_PYTHON="$(conda run -n base python -c 'import sys; print(sys.executable)')"
printf '%s\n' "${BASE_PYTHON}"
```

Before adapting the configuration, back it up and replace only the current interpreter path in `karabiner.json`:

```bash
cp "${HOME}/.config/karabiner/karabiner.json" "${HOME}/.config/karabiner/karabiner.json.bak"

OLD_PYTHON='/opt/miniconda3/bin/python3' \
NEW_PYTHON="${BASE_PYTHON}" \
/usr/bin/perl -0pi -e 's/\Q$ENV{OLD_PYTHON}\E/$ENV{NEW_PYTHON}/g' \
  "${HOME}/.config/karabiner/karabiner.json"
```

Verify that the new path appears in the configuration and that the JSON remains valid:

```bash
/usr/bin/grep -nF "${BASE_PYTHON}" "${HOME}/.config/karabiner/karabiner.json"
"${BASE_PYTHON}" -m json.tool "${HOME}/.config/karabiner/karabiner.json" >/dev/null
```

### Unicode Inspector Replacement

`Caps+7` uses `scripts/launch_unicode_inspector.py` to copy the selection, restore the clipboard and open the external `UnicodeInspector` class from `PersonalScripts/tools/others/unicode-inspector.py`. Text is transferred through a private in-memory pasteboard, not temporary files or command-line arguments. The built-in inspector and `text_actions.py stats` have been removed.

Clone the complete [PersonalScripts repository](https://github.com/BH2WFR/PersonalScripts), not just the script: it imports that repository's `utils` package. In the `ZL` profile's `Caps+7` shell command, replace the path after `--inspector` with your local script path. Replace `/opt/miniconda3/bin/python3` when using another Conda environment; its `python.app` and Tkinter must be available. The launcher locates `python.app` in that environment automatically. Disable the `7` manipulator if the external tool is not installed.

### Python Environment

Several shortcuts rely on Python scripts and packages installed in the same Miniconda Base environment.

To replicate:

```bash
# Install Miniconda to /opt/miniconda3
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-$(uname -m).sh -o /tmp/miniconda.sh
sudo bash /tmp/miniconda.sh -b -p /opt/miniconda3
```

Required Python packages (install into base conda env):

```bash
/opt/miniconda3/bin/python3 -m pip install pyobjc-framework-Quartz pyobjc-framework-Cocoa
```

### Device-Specific Rules

Several modifier rules distinguish the built-in keyboard, external keyboards, and specific Logitech devices. These identifiers are machine- and device-specific. Before reusing them, inspect your own devices with:

- Karabiner-Elements → Settings → Devices
- Karabiner-EventViewer → Devices

Then update or remove `conditions` that match fields such as:

- `vendor_id`
- `product_id`
- `is_built_in_keyboard`
- `is_keyboard`
- `is_pointing_device`

If a rule targets a keyboard you do not own, remove that device condition or disable the whole rule. Do not assume another Logitech keyboard has the same `product_id`.

Current device-level settings in the active `ZL` profile:

| Vendor ID | Product ID | Device | Setting |
| --- | --- | --- | --- |
| `1133` | `50475` | Keyboard | Caps Lock LED manipulation disabled |
| `13364` | `2803` | Keyboard/pointing composite device | Explicitly enabled (`ignore: false`) |
| `1133` | `45108` | Pointing device | Pointer movement multiplier `1.3` |
| `1133` | `50504` | Keyboard interface | Device and vendor events ignored |
| `1133` | `50504` | Pointing-device interface | Horizontal wheel reversed; pointer movement multiplier `1.2` |

The horizontal-wheel reversal above is a device setting. There is no longer a Caps-layer shortcut triggered by a mouse wheel or an extra mouse button.

### App-Specific Rules

Rules for RDP, Anki, Cherry Studio, and Rime depend on app bundle identifiers or local app behavior. Check bundle IDs on your machine with:

```bash
osascript -e 'id of app "Anki"'
osascript -e 'id of app "Windows App"'
osascript -e 'id of app "Microsoft Remote Desktop"'
osascript -e 'id of app "UURemote"'
```

Update `frontmost_application_if` / `frontmost_application_unless` conditions if your app has a different bundle ID.

The Rime, Anki, and Cherry Studio rules are personal shortcuts documented in **Personal Hotkeys** above; other users should normally disable them. Disable the RDP / Windows App / UU Remote mappings as well if remote Windows sessions are not used.

### Additional Dependencies

- **Secondary clipboard** — `scripts/secondary_clipboard.py` uses `pyobjc-framework-Cocoa`, a named `NSPasteboard`, and the shared `scripts/keyboard_events.py` CoreGraphics helper; it does not write clipboard data to temporary files
- **Clipboard image repair** — `scripts/repair_clipboard_images.py` uses the same `pyobjc-framework-Cocoa` dependency for AppKit decoding and PNG encoding, entirely in memory.
- **Keystroke typing** — `scripts/type_clipboard.py` uses Cocoa for the clipboard, CoreGraphics for keys, and `pyobjc-framework-Quartz` to intercept Escape during typing and until the cancelling Escape is released. Python needs Accessibility and, if requested by macOS, Input Monitoring permission.
- **Text tools** — `scripts/text_actions.py` reuses the clipboard and keyboard helpers. `Caps+7` separately requires the PersonalScripts checkout and Tkinter; see Unicode Inspector Replacement above.
- **Window inspector** — `scripts/window_inspector.py` uses `tkinter`, `psutil` and the existing Cocoa/Accessibility helpers. Install `psutil` in the same Python environment if missing; window operations require Accessibility permission, and Finder Get Info may request Automation permission.
- **Quick-access menu** — `scripts/quick_menu.py` uses `pyobjc-framework-Cocoa`. Common Folders separates personal files, cloud drives, user app data, system/shared directories and startup items. Cloud drives include iCloud Drive and existing OneDrive, Dropbox, Google Drive and Box folders under `~/Library/CloudStorage`; third-party clients must be installed. Custom sync locations can be added as personal folders. Homebrew's cache comes from `brew --cache`.
- **Custom menu entries** — edit `scripts/quick_menu.json`: `personal_folders` entries use `title` and `path` (`~` supported; relative paths start at the JSON file); `applications` entries use `title`, `name` (without `.app`) and an optional `bundle_id`. Third-party apps appear below a separator in Utilities. Missing directories/apps and empty custom groups are hidden. Changes apply the next time the menu opens.
- **Menu commands** — `commands` entries use `title`, `command` and `output`: `gui` (default) opens immediately with `Running...`, provides a merged Live Output tab (labeled by source, in arrival order), separate stdout/stderr tabs and the final exit code; `terminal` opens Terminal for interactive commands. Commands run through `/bin/zsh -lc`, with optional `cwd` (default `~`; relative paths start at the JSON file). GUI mode strips ANSI controls, supports copying and Stop, has no stdin and retains up to 1 MiB per stream; it does not block reopening the menu. Programs that buffer output may need an unbuffered option, such as Python's `-u`. The included 10-second test outputs the current time once per second, alternating stdout/stderr. Only add commands you trust.
- **Hotkey feedback** — the shared `scripts/tooltip.py` uses a native, non-activating macOS panel (`pyobjc-framework-Cocoa`), with no Tkinter or PySide6. It appears near the pointer, stays within the screen's usable area, and ignores clicks without taking keyboard focus. Results, warnings and errors last 600, 1200 and 1600 ms respectively. `scripts/toggle_caps_lock.py` reads and changes Caps Lock through IOKit.

### Display and Window Scripts

Some scripts use macOS Accessibility APIs or private/display-related behavior:

- `scripts/toggle_builtin_screen.py` is for Apple Silicon and requires an actual external monitor. Sidecar-only use is not reliable because disabling the built-in panel can interrupt Sidecar.
- `scripts/center_front_window.py` uses Accessibility APIs to move and resize the frontmost window. It needs Accessibility permission for the Python interpreter that runs it.
- `scripts/show_front_window_info.sh` opens Terminal to show a snapshot of the frontmost app/window. It is intended for inspection and copying text, not as a persistent GUI.

If these scripts fail after migration, first check permissions and Python package availability before changing the Karabiner rule.

### Accessibility Permissions

After installing, grant these permissions in **System Settings → Privacy & Security**:

- **Input Monitoring** — Karabiner-Elements (`karabiner_grabber`, `karabiner_observer`)
- **Accessibility** — Karabiner-Elements, Terminal (for `osascript` GUI scripting), Python (for mouse/zoom scripts)
- **Automation** — Allow Karabiner to control System Events if prompted

### Verification

Automated regression tests live in [`test/`](test/README.md). Run `/opt/miniconda3/bin/python3 -m unittest discover -s test` from the repository root; they do not send real input or modify the clipboard.

1. Tap `Caps` alone → should toggle Caps Lock
2. Hold `Caps+C` → should copy (`Cmd+C`)
3. Hold `Caps+V` → should paste without formatting
4. Hold `Caps+LOpt+C`, then `Caps+LOpt+V` → should copy and paste through the secondary clipboard without changing the general clipboard
5. Repeat step 4 with physical `RCmd` and `LCmd` as the secondary-layer trigger
6. Hold `Caps+LOpt+Shift+C` or `Caps+LOpt+Shift+X` → should copy or cut the current line through the secondary clipboard
7. Select multiple lines and test `Caps+Tab` / `Caps+Shift+Tab` → should indent or unindent them
8. In RDP session, `Caps` should act as `F1`
9. In RDP session, tap `F1` → should still send `F1`
10. In RDP session, hold `F1+C` → should run the Caps Primary Layer copy shortcut
11. In RDP session, `F1+[LOpt/RCmd/LCmd]` must not activate the Caps Secondary Layer or invoke any of its functions
12. In RDP session, physical `LOpt`, `RCmd` and `LCmd` retain their normal RDP mappings (`LCmd`, `ROpt` and `LOpt`, respectively)
13. In RDP session, `Ctrl`/`Cmd` positions should feel like Windows

If a shortcut does nothing, open Karabiner-EventViewer first. Confirm whether Karabiner sees the physical key, then confirm whether the intended rule matches the current device and frontmost app.
