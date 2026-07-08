#!/bin/bash
clear
OUT="${TMPDIR:-/tmp}/karabiner_front_window_info.txt"

if [[ -s "$OUT" ]]; then
    cat "$OUT"
else
    echo "No front window info snapshot found."
fi

echo
read -r -p "Press Enter to exit..."
