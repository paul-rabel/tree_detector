#!/bin/bash
# Double-clickable launcher for the annotation tool (macOS).
# Reuses an active virtualenv if present, otherwise sets up a local ./venv.
cd "$(dirname "$0")" || exit 1

if [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PY="$VIRTUAL_ENV/bin/python"
elif [ -x "venv/bin/python" ]; then
    PY="venv/bin/python"
else
    echo "Creating local virtual environment (first run)..."
    python3 -m venv venv || { echo "Failed to create venv"; exit 1; }
    PY="venv/bin/python"
    "$PY" -m pip install --upgrade pip >/dev/null
    "$PY" -m pip install -r requirements.txt || { echo "Failed to install deps"; exit 1; }
fi

# Ensure Pillow is available in whichever interpreter we chose.
if ! "$PY" -c "import PIL" >/dev/null 2>&1; then
    echo "Installing dependencies into $PY ..."
    "$PY" -m pip install -r requirements.txt || { echo "Failed to install deps"; exit 1; }
fi

exec "$PY" annotate.py
