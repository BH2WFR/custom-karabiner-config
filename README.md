# Personal Karabiner-Elements Configuration

**Personal** **Karabiner-Elements setup** for macOS.

Designed around a **`Capslock` hyper-layer** with context-aware remapping for RDP sessions.

Repository: [BH2WFR/custom-karabiner-config](https://github.com/BH2WFR/custom-karabiner-config)



## Keyboard Mappings

| Physical Key | Normal | RDP <br />(Microsoft Remote Desktop / Windows App) |
| --- | --- | --- |
| `Capslock` | Activates **Caps Layer** (hold) / `Capslock` (tap) | `F1` |
| `Fn` (globe key) | `Left Cmd` | `Left Ctrl` |
| `Left Ctrl` <br />(built-in keyboard) | `Fn` | `Fn` |
| `Left Ctrl` <br />(external keyboard) | `Left Cmd` | No remap (still `Left Ctrl`) |
| `Left Opt` | — | `Left Cmd` |
| `Left Cmd` | `Left Ctrl` | `Left Opt` |
| `Right Cmd` | `Right Opt` | `Right Opt` |
| `Right Opt` <br />(built-in keyboard / Logi Mechanical) | `Right Cmd` | `Right Ctrl` |
| `Right Ctrl` <br />(external keyboard) | `Right Cmd` | No remap (still `Right Cmd`) |
| `Application` (external keyboard) or  `Menu` | `Fn` | `Fn` |

**Modifier layout summary:**

- **Normal**: `Capslock` is a hyper-layer trigger; `Cmd`/`Ctrl` are swapped (Mac-style bottom row on external keyboards); `Fn` key becomes `Cmd`.
- **RDP**: `Capslock` becomes `F1`; modifier positions mimic a standard Windows keyboard (`Ctrl` where `Cmd` normally is, etc.).

## Caps Layer Shortcuts

Hold `Capslock` to activate the Caps layer. Release to deactivate. Tapping `Capslock` alone sends `Capslock` on key-up (i.e., on release), which toggles Caps Lock or switches input method depending on system settings. In Anki, tapping `Capslock` also sends an `F18` dummy key to work around Anki/Qt swallowing the first real key after input-source changes.

### Editing

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
| `Caps+Backspace` | **Delete character left of cursor** | e.g. with cursor after **Chinese two-character word** `结果`: <br />moves left → deletes `果` → moves right, **leaving `结` before the cursor** |
| `Caps+Shift+Backspace` | Delete current line | |
| `Caps+;` | Insert `;` **at end of line** | |
| `Caps+Shift+;`<br />`Caps+'` | Insert `:` **at end of line** | |
| `Caps+Enter` | **Go to end of line + add newline** | |
| `Caps+Shift+Enter` | Insert blank line above current | |
| `Caps+Space` | Insert full-width space (U+3000) | Uses `scripts/insert_unicode_symbol.py`; <br />depends on `pyobjc-framework-Cocoa` |
| `Caps+Z` | `Fn` | Sends `keyboard_fn` |
| `Caps+\`<br />`Caps+|` | ISO `\|` key | Sends `non_us_backslash` / `Shift+non_us_backslash` |

### Mouse / Navigation

| Keys | Function | Notes |
| --- | --- | --- |
| `Caps+I` / `J` / `K` / `L` | Move mouse pointer (1px steps) | Uses `scripts/move_mouse_pointer.py`; <br />depends on `pyobjc-framework-Quartz` |
| `Caps+Shift+I` / `J` / `K` / `L` | Move mouse pointer (10px steps) | Uses `scripts/move_mouse_pointer.py`; <br />depends on `pyobjc-framework-Quartz` |
| `Caps+U` | Left mouse click at pointer | Uses `scripts/move_mouse_pointer.py --key_click button1`; de<br />pends on `pyobjc-framework-Quartz` |
| `Caps+O` | Right mouse click at pointer | Uses `scripts/move_mouse_pointer.py --key_click button2`; <br />depends on `pyobjc-framework-Quartz` |
| `Caps+Scroll wheel` | Horizontal scroll | Wheel swap |
| `Caps+-` | **Zoom out (trackpad pinch)** | Uses `scripts/trackpad_zoom.py`; <br />**simulates a native trackpad pinch-zoom gesture** — **not** scroll-wheel zoom or `Cmd+-`; <br />in browsers, this zooms the page like a trackpad pinch, unlike `Cmd+-` which changes font size |
| `Caps+=` | **Zoom in (trackpad pinch)** | Uses `scripts/trackpad_zoom.py`; <br />same as above — native pinch gesture, different from scroll-wheel or `Cmd+=` |
| `Caps+Shift+-` | Horizontal scroll left | |
| `Caps+Shift+=` | Horizontal scroll right | |

### Other

| Keys | App | Function | Notes |
| --- | --- | --- | --- |
| `Caps+P` | Any | **Toggle built-in display on/off** | Uses `scripts/toggle_builtin_screen.py` <br />(ctypes, Apple Silicon only); <br />requires **external monitor** |
| `Caps+R` | Any except Anki | Fit frontmost window to current display, then center | Uses `scripts/center_front_window.py --fit`; <br />shrinks only if the window is larger than the target display; <br />pass `--display main` to target the main display instead; <br />requires Accessibility permission for Python |
| `Caps+W` | Any except Anki | Show frontmost window/app information | Captures a snapshot via `scripts/show_front_window_info.sh`, then opens Terminal; <br />shows process, bundle, focused window, and AX child summary |
| `Caps+Shift+U` | Any | Parse Unicode from clipboard | Copies selection, opens Terminal with helper |
| `Caps+.` | Any | Toggle Rime punctuation mode | **Delete or turn off** (personal use); <br />sends `Ctrl+F19` |
| `Caps+Q`/`W`/`E`/`R`/`T`/`Y`/`A`/`S`/`D`/`F`/`G`/`H` (+`Shift`) | Anki | Various card review shortcuts | **Delete or turn off** (personal use); <br />mapped to `F13` + modifier combos |

## Other Hotkeys

| Hotkey | App | Function | Notes |
| --- | --- | --- | --- |
| `Mouse Button 4` | Finder | `Cmd+[` (Back) | |
| `Shift+Mouse Button 4` | Finder | `Cmd+Up` (Go to parent folder) | |
| `Mouse Button 5` | Finder | `Cmd+]` (Forward) | |
| `Cmd+Enter` | Cherry Studio | `Ctrl+Enter` (send message) | |


## Migration Guide

This repository is a personal configuration, not a drop-in universal preset.
If you use it on another Mac, review the sections below before replacing your
own `~/.config/karabiner` directory.

### System Requirements

- macOS (Apple Silicon or Intel)
- [Karabiner-Elements](https://karabiner-elements.pqrs.org/) (latest version)

### Recommended Porting Workflow

1. Back up your current Karabiner config:

```bash
cp -a ~/.config/karabiner ~/.config/karabiner.backup.$(date +%Y%m%d-%H%M%S)
```

2. Clone or copy this repository to `~/.config/karabiner`.
3. Open `karabiner.json` in Karabiner-Elements and disable rules you do not
   need before relying on the setup daily.
4. Check all script paths, device identifiers, app bundle identifiers, and
   external dependencies listed below.
5. Grant macOS permissions, then test the basic Caps layer before testing app-
   specific shortcuts.

### Paths You May Need to Change

Most shell commands assume this repository is located at:

```text
${HOME}/.config/karabiner
```

Python commands assume Miniconda is installed at:

```text
/opt/miniconda3/bin/python3
```

If your Python lives elsewhere, replace every `/opt/miniconda3/bin/python3`
entry in `karabiner.json`. Using an absolute path is intentional: Karabiner
does not run commands in an interactive shell, so `PATH`, Conda activation, and
shell aliases may not match your Terminal.

### Python Environment

Several shortcuts rely on Python scripts. The **Miniconda** installation is expected at a hard-coded path:

```
/opt/miniconda3/bin/python3
```

To replicate:

```bash
# Install Miniconda to /opt/miniconda3
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-$(uname -m).sh -o /tmp/miniconda.sh
sudo bash /tmp/miniconda.sh -b -p /opt/miniconda3
```

Required Python packages (install into base conda env):

```bash
/opt/miniconda3/bin/pip install pyobjc-framework-Quartz pyobjc-framework-Cocoa
```

### Device-Specific Rules

Several modifier rules distinguish the built-in keyboard, external keyboards,
and specific Logitech devices. These identifiers are machine- and device-
specific. Before reusing them, inspect your own devices with:

- Karabiner-Elements → Settings → Devices
- Karabiner-EventViewer → Devices

Then update or remove `conditions` that match fields such as:

- `vendor_id`
- `product_id`
- `is_built_in_keyboard`
- `is_keyboard`
- `is_pointing_device`

If a rule targets a keyboard you do not own, remove that device condition or
disable the whole rule. Do not assume another Logitech keyboard has the same
`product_id`.

### App-Specific Rules

Rules for RDP, Anki, Cherry Studio, Rime, Finder, and Terminal depend on app
bundle identifiers or local app behavior. Check bundle IDs on your machine with:

```bash
osascript -e 'id of app "Anki"'
osascript -e 'id of app "Windows App"'
osascript -e 'id of app "Microsoft Remote Desktop"'
```

Update `frontmost_application_if` / `frontmost_application_unless` conditions
if your app has a different bundle ID.

Personal app-specific parts you may want to delete or disable:

- **RDP / Windows App** mappings if you do not use remote Windows sessions.
- **Anki** review shortcuts if your Anki shortcuts are not based on `F13`
  combinations.
- **Rime** punctuation toggle if you do not use Rime or do not bind `Ctrl+F19`
  inside Rime.
- **Cherry Studio** `Cmd+Enter` remap if you do not use Cherry Studio.

### Additional Dependencies

- **Rime input method** (personal — delete or turn off) — `Caps+.` toggles punctuation mode via `Ctrl+F19` (configure `F19` as the hotkey in Rime settings)
- **Anki** (personal — delete or turn off) — `Caps+Q`/`W`/`E`/`R`/`T`/`Y`/`A`/`S`/`D`/`F`/`G`/`H` shortcuts only active when Anki (`net.ankiweb.launcher`) is frontmost; Anki must have `F13`-based shortcuts configured
- **Cherry Studio** — `Cmd+Enter` remap only active when Cherry Studio is frontmost

### Display and Window Scripts

Some scripts use macOS Accessibility APIs or private/display-related behavior:

- `scripts/toggle_builtin_screen.py` is for Apple Silicon and requires an
  actual external monitor. Sidecar-only use is not reliable because disabling
  the built-in panel can interrupt Sidecar.
- `scripts/center_front_window.py` uses Accessibility APIs to move and resize
  the frontmost window. It needs Accessibility permission for the Python
  interpreter that runs it.
- `scripts/show_front_window_info.sh` opens Terminal to show a snapshot of the
  frontmost app/window. It is intended for inspection and copying text, not as a
  persistent GUI.

If these scripts fail after migration, first check permissions and Python
package availability before changing the Karabiner rule.

### Accessibility Permissions

After installing, grant these permissions in **System Settings → Privacy & Security**:

- **Input Monitoring** — Karabiner-Elements (`karabiner_grabber`, `karabiner_observer`)
- **Accessibility** — Karabiner-Elements, Terminal (for `osascript` GUI scripting), Python (for mouse/zoom scripts)
- **Automation** — Allow Karabiner to control System Events if prompted

### Verification

1. Tap `Capslock` alone → should toggle Caps Lock
2. Hold `Caps+C` → should copy (`Cmd+C`)
3. Hold `Caps+V` → should paste without formatting
4. In RDP session, `Capslock` should act as `F1`
5. In RDP session, `Ctrl`/`Cmd` positions should feel like Windows

If a shortcut does nothing, open Karabiner-EventViewer first. Confirm whether
Karabiner sees the physical key, then confirm whether the intended rule matches
the current device and frontmost app.
