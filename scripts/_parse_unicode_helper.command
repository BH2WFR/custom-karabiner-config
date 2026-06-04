#!/bin/bash
clear
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
/opt/miniconda3/bin/python3 -S "$SCRIPT_DIR/parse_unicode_string.py" --from-clipboard --pause
