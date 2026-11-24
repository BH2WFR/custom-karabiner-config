#!/bin/sh
# Hand the non-activating tooltip to Launch Services, then start the tool.
tool_name=$1
shift
/usr/bin/open -g -n -a /opt/miniconda3/python.app \
    --env PYTHONEXECUTABLE=/opt/miniconda3/bin/python3 --args \
    "${0%/*}/tooltip.py" "Launching $tool_name, please wait…" --duration-ms 2000
exec "$@"
