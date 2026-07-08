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
| `Right Opt` <br />(built-in keyboard) | `Right Cmd` | `Right Ctrl` |
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

### System Requirements

- macOS (Apple Silicon or Intel)
- [Karabiner-Elements](https://karabiner-elements.pqrs.org/) (latest version)

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


### Additional Dependencies

- **Rime input method** (personal — delete or turn off) — `Caps+.` toggles punctuation mode via `Ctrl+F19` (configure `F19` as the hotkey in Rime settings)
- **Anki** (personal — delete or turn off) — `Caps+Q`/`W`/`E`/`R`/`T`/`Y`/`A`/`S`/`D`/`F`/`G`/`H` shortcuts only active when Anki (`net.ankiweb.launcher`) is frontmost; Anki must have `F13`-based shortcuts configured
- **Cherry Studio** — `Cmd+Enter` remap only active when Cherry Studio is frontmost

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
