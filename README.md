# Personal Karabiner-Elements Configuration

**Personal** **Karabiner-Elements setup** for macOS.

Designed around a two-level **`Caps` layer** with context-aware remapping for RDP sessions and a named secondary clipboard.

Repository: [BH2WFR/custom-karabiner-config](https://github.com/BH2WFR/custom-karabiner-config)

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
| `[RDP]` | Remote Desktop Protocol; Microsoft Remote Desktop or Windows App |
| Physical key | The key actually pressed on the keyboard, before this configuration remaps it |
| Mapped key | The key produced by a mapping and received by macOS or the target application |

In shortcut notation, `A+B` means that the keys are held together. A group such as `[LOpt/RCmd]` means either physical `LOpt` or physical `RCmd`; the square brackets do not mean that the modifier is optional. Outside RDP, the Caps Secondary Layer can be activated by physical `RCmd`, even though that key is normally mapped to `ROpt` when it is not being used as the layer trigger.

## Profile Settings

- The active profile is `ZL`.
- Karabiner's notification window is disabled globally with `enable_notification_window: false`.
- The inactive `Default profile` contains a simple `F1` to `F13` mapping. It does not affect the selected `ZL` profile.

## Keyboard Mappings

| Physical Key | Normal | RDP <br />(Microsoft Remote Desktop / Windows App) |
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

- **Normal**: `Caps` activates `caps_primary_layer`; after `Caps` is already held, physical `LOpt` or `RCmd` activates `caps_secondary_layer`. Physical `LOpt` remains `LOpt`, while physical `RCmd` maps to `ROpt`, so both keys are mapped Option keys outside RDP. `Cmd`/`Ctrl` are swapped (Mac-style bottom row on external keyboards); `Fn` becomes `Cmd`.
- **RDP**: `Caps` becomes `F1`; physical `F1` directly controls the same `caps_primary_layer` variable while held and remains `F1` when tapped. The Caps Secondary Layer is disabled, and physical `LOpt`/`RCmd` follow their normal RDP mappings. Modifier positions mimic a standard Windows keyboard (`Ctrl` where `Cmd` normally is, etc.).

The RDP mappings are separate Complex Modification rules:

- `[Map][RDP]: [Caps] to [F1]`
- `[Layer][RDP]: [F1] to [Caps Primary Layer]`

They can be enabled or disabled independently without changing the normal Caps Primary Layer rule.

## Hotkey Reference

### Caps Primary Layer

Hold `Caps` to activate `caps_primary_layer`. Release it to deactivate the layer. Tapping `Caps` alone sends `Caps` on key-up (i.e., on release), which toggles Caps Lock or switches input method depending on system settings.

When Microsoft Remote Desktop / Windows App is frontmost, hold physical `F1` instead. It sets `caps_primary_layer` directly on key-down and clears it on key-up; it does not map through `Caps`. Tapping `F1` alone still sends `F1`.

#### Editing

| Keys | Function | Notes |
| --- | --- | --- |
| `Caps+C` | Copy (`Cmd+C`) | |
| `Caps+Shift+C` | Copy entire line | |
| `Caps+X` | Cut (`Cmd+X`) | |
| `Caps+Shift+X` | Cut entire line | |
| `Caps+V` | **Paste as plain text** | Uses `scripts/paste_without_format.py` (depends on `pyobjc-framework-Cocoa` for Finder path extraction); <br />when **copying files from Finder, pastes file paths** (one per line for multiple files) |
| `Caps+Shift+V` | **Advanced paste** | Uses `scripts/paste_without_format.py --advanced`; <br />strips zero-width chars, normalises spaces, converts full-width→half-width, de-quotes, splits ligatures, CJK-aware line-break removal (while copied from paragraphs from a PDF file), path-slash conversion — then pastes with `Cmd+V` |
| `Caps+Tab` | Indent selected lines | Uses `scripts/indent_select_lines.py` <br />(stdlib only) |
| `Caps+Shift+Tab` | Unindent selected lines | Uses `scripts/indent_select_lines.py` <br />(stdlib only) |
| `Caps+Backspace` | **Delete the first character of the preceding two-character word** | e.g. with the cursor after `结果`: <br />moves left → deletes `结` → moves right, **leaving `果` before the cursor** |
| `Caps+Shift+Backspace` | Delete current line | |
| `Caps+;` | Insert `;` **at end of line** | |
| `Caps+Shift+;`<br />`Caps+'` | Insert `:` **at end of line** | |
| `Caps+Enter` | **Go to end of line + add newline** | |
| `Caps+Shift+Enter` | Insert blank line above current | |
| `Caps+Space` | Insert full-width space (U+3000) | Uses `scripts/insert_unicode_symbol_cgevent.py`; <br />posts Unicode keyboard events with `ctypes` and does not modify the clipboard |
| `Caps+Z` | `Fn` | Sends `keyboard_fn` |
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
| `Caps+P` | Any | **Toggle built-in display on/off** | Uses `scripts/toggle_builtin_screen.py` <br />(ctypes, Apple Silicon only); <br />requires **external monitor** |
| `Caps+R` | Any except Anki | Fit frontmost window to current display, then center | Uses `scripts/center_front_window.py --fit`; <br />shrinks only if the window is larger than the target display; <br />pass `--display main` to target the main display instead; <br />requires Accessibility permission for Python |
| `Caps+W` | Any except Anki | Show frontmost window/app information | Captures a snapshot via `scripts/show_front_window_info.sh`, then opens Terminal; <br />shows process, bundle, focused window, and AX child summary |
| `Caps+Shift+U` | Any | Parse Unicode from clipboard | Copies selection, opens Terminal with helper |

### Caps Secondary Layer

The **Caps Secondary Layer** is a general-purpose extension layer and is available only outside RDP. To activate `caps_secondary_layer`, **press and hold `Caps` first**, then **press and hold physical `LOpt` or physical `RCmd`** (outside RDP, they are both mapped to `Opt`). The order is required: pressing either trigger before `Caps` applies its normal mapping and does not retroactively activate the layer.

Outside RDP, physical `LOpt` remains `LOpt`, while physical `RCmd` maps to `ROpt`; therefore, both triggers are mapped `Opt` keys during normal use. When the secondary layer captures them after `Caps`, their Option output is suppressed so it does not leak into the frontmost application.

In RDP, `caps_secondary_layer` cannot be activated. Physical `LOpt` maps normally to `LCmd`, physical `RCmd` maps normally to `ROpt`, and neither key participates in the special layer even while the RDP Primary Layer is active through `F1`.

#### Secondary Clipboard Shortcuts

The **secondary clipboard** is the first set of functions assigned to the Caps Secondary Layer; additional functions can be added to this layer later.

| Keys | Function | Notes |
| --- | --- | --- |
| `Caps+[LOpt/RCmd]+C` | Copy selection to the secondary clipboard as plain text | Uses `scripts/secondary_clipboard.py copy`; image-only and other content without a text representation is rejected; Finder files are converted to full paths |
| `Caps+[LOpt/RCmd]+Shift+C` | Copy current line to the secondary clipboard as plain text | Uses the same whole-line selection behavior as `Caps+Shift+C` |
| `Caps+[LOpt/RCmd]+X` | Cut selection to the secondary clipboard as plain text | Confirms that a text representation is available before sending `Cmd+X` |
| `Caps+[LOpt/RCmd]+Shift+X` | Cut current line to the secondary clipboard as plain text | Uses the same whole-line selection and newline cleanup as `Caps+Shift+X` |
| `Caps+[LOpt/RCmd]+V` | Paste the secondary clipboard as plain text | Temporarily writes to the general pasteboard, pastes, then restores the previous general pasteboard |

The secondary clipboard is stored in a named macOS `NSPasteboard`, not a temporary file. The script defaults to `com.bh2wfr.secondary-clipboard` and also supports `--pasteboard-name`, `--multi-items`, and the `clear` action from the command line. There are currently no hotkeys for multi-item operations or clearing the secondary clipboard.

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
```

Update `frontmost_application_if` / `frontmost_application_unless` conditions if your app has a different bundle ID.

The Rime, Anki, and Cherry Studio rules are personal shortcuts documented in **Personal Hotkeys** above; other users should normally disable them. Disable the RDP / Windows App mappings as well if remote Windows sessions are not used.

### Additional Dependencies

- **Secondary clipboard** — `scripts/secondary_clipboard.py` uses `pyobjc-framework-Cocoa`, a named `NSPasteboard`, and System Events keyboard automation; it does not write clipboard data to temporary files

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

1. Tap `Caps` alone → should toggle Caps Lock
2. Hold `Caps+C` → should copy (`Cmd+C`)
3. Hold `Caps+V` → should paste without formatting
4. Hold `Caps+LOpt+C`, then `Caps+LOpt+V` → should copy and paste through the secondary clipboard without changing the general clipboard
5. Repeat step 4 with physical `RCmd` as the secondary-layer trigger
6. Hold `Caps+LOpt+Shift+C` or `Caps+LOpt+Shift+X` → should copy or cut the current line through the secondary clipboard
7. Select multiple lines and test `Caps+Tab` / `Caps+Shift+Tab` → should indent or unindent them
8. In RDP session, `Caps` should act as `F1`
9. In RDP session, tap `F1` → should still send `F1`
10. In RDP session, hold `F1+C` → should run the Caps Primary Layer copy shortcut
11. In RDP session, `F1+[LOpt/RCmd]` must not activate the Caps Secondary Layer or invoke any of its functions
12. In RDP session, physical `LOpt` and `RCmd` should retain their normal RDP mappings (`LCmd` and `ROpt`, respectively)
13. In RDP session, `Ctrl`/`Cmd` positions should feel like Windows

If a shortcut does nothing, open Karabiner-EventViewer first. Confirm whether Karabiner sees the physical key, then confirm whether the intended rule matches the current device and frontmost app.
