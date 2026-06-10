#!/bin/bash
# e2s_autoslice_gui.command
#
# Double-click to launch the GUI without building anything.
# This uses the Python already on your Mac (no standalone app), so Python 3
# with Tkinter and numpy must be installed. It's the quick path; for a fully
# self-contained app that needs nothing installed, run build_mac_app.command.

cd "$(dirname "$0")"

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "python3 not found. Install Python 3 from https://www.python.org/downloads/"
  echo "Press Return to close."; read _; exit 1
fi

# Ensure numpy is present; offer to install into the user account if missing.
if ! "$PY" -c "import numpy" 2>/dev/null; then
  echo "numpy is not installed for $PY."
  echo "Installing it now into your user account..."
  "$PY" -m pip install --user numpy || {
    echo "Could not install numpy automatically. Run: $PY -m pip install numpy"
    echo "Press Return to close."; read _; exit 1
  }
fi

exec "$PY" e2s_autoslice_gui.py
