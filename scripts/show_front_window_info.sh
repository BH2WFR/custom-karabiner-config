#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="${TMPDIR:-/tmp}/karabiner_front_window_info.txt"

/opt/miniconda3/bin/python3 "$SCRIPT_DIR/front_window_info.py" >"$OUT" 2>&1
open -a Terminal "$SCRIPT_DIR/_front_window_info_helper.command"
