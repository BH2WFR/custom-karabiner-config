#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec /opt/miniconda3/bin/python3 "$SCRIPT_DIR/window_inspector.py" "$@"
