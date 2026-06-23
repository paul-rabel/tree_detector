#!/bin/bash
# Double-clickable launcher for the annotation tool (macOS).
# Uses the project's existing .tree virtual environment.
cd "$(dirname "$0")" || exit 1

VENV_PY="../.tree/bin/python"

if [ -x "$VENV_PY" ]; then
    PY="$VENV_PY"
elif [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PY="$VIRTUAL_ENV/bin/python"
else
    PY="python3"
fi

# Make sure Pillow is available; install into the chosen interpreter if missing.
if ! "$PY" -c "import PIL" >/dev/null 2>&1; then
    echo "Pillow not found in $PY — installing..."
    "$PY" -m pip install -r requirements.txt || { echo "Failed to install Pillow"; exit 1; }
fi

exec "$PY" annotate.py
