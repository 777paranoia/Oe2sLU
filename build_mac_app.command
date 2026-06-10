#!/bin/bash
# build_mac_app.command
#
# Double-click this in Finder to build a standalone Oe2sLU.app.
# It creates a throwaway virtual environment, installs PyInstaller + the
# project's requirements into it, and runs the build. Nothing is installed
# system-wide. When it finishes, the app is in the "dist" folder.
#
# First time only: macOS may block a downloaded .command. If double-click
# does nothing, right-click it -> Open, or run once:
#     chmod +x build_mac_app.command

set -e
cd "$(dirname "$0")"

echo "==> Project: $(pwd)"

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "ERROR: python3 not found. Install Python 3 from https://www.python.org/downloads/ and retry."
  echo "Press Return to close."; read _; exit 1
fi
echo "==> Using $($PY --version) at $PY"

# --- Tk check first (fail fast, before the long torch install) --------
check_tk() { "$PY" -c "import tkinter" >/dev/null 2>&1; }

if ! check_tk; then
  echo "==> This Python has no Tkinter; attempting to fix..."
  # Homebrew pythons need the matching python-tk formula.
  case "$PY" in
    /opt/homebrew/*|/usr/local/*)
      if command -v brew >/dev/null 2>&1; then
        XY="$("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
        echo "    Installing python-tk@${XY} via Homebrew..."
        brew install "python-tk@${XY}" || brew install python-tk || true
      else
        echo "    Homebrew not found."
      fi
      ;;
  esac
fi

if ! check_tk; then
  echo ""
  echo "ERROR: this Python ($PY) still has no Tkinter."
  echo "Fix options:"
  echo "  - Homebrew:   brew install python-tk@<your version>"
  echo "  - Or install a python.org build (includes Tk) and re-run this."
  echo "Press Return to close."; read _; exit 1
fi
echo "    tkinter OK"

VENV=".build-venv"
echo "==> Creating build environment in $VENV"
"$PY" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> Verifying Tkinter inside the venv"
python -c "import tkinter; print('    tkinter', tkinter.TkVersion, 'OK')" || {
  echo "ERROR: the venv cannot see Tkinter even though the base Python can."
  echo "Try a python.org Python instead. Press Return to close."; read _; exit 1
}

echo "==> Installing build dependencies (this includes demucs + torch; large)"
python -m pip install --upgrade pip >/dev/null
# Required: PyInstaller (build tool) + numpy (the only hard runtime dep).
python -m pip install pyinstaller "numpy<2"
# Optional niceties — install each separately so one failure can't block the
# rest. tkextrafont is intentionally omitted (it needs a C toolchain/cmake);
# bundled fonts are loaded at runtime via macOS CoreText instead.
for pkg in sounddevice Pillow tkinterdnd2 soundfile imageio-ffmpeg; do
  python -m pip install "$pkg" || echo "    (skipped $pkg; app still works)"
done
# Optional stem-splitting (large: torch). Skipped without aborting on failure.
python -m pip install demucs || echo "    (demucs/torch skipped; stem split off)"
# keep numpy < 2.0 in case demucs/torch pulled in 2.x
python -m pip install "numpy<2"

# Bundle ffmpeg so the app can convert any input (m4a/aac/wma/etc.) to WAV.
# A static binary is best for portability; we try imageio-ffmpeg (ships a
# static ffmpeg via pip), then fall back to copying a system ffmpeg.
echo "==> Sourcing ffmpeg for the bundle"
mkdir -p bin
if [ ! -x bin/ffmpeg ]; then
  python -m pip install imageio-ffmpeg >/dev/null 2>&1 && \
    FF=$(python -c "import imageio_ffmpeg,shutil,sys;print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null) && \
    [ -n "$FF" ] && cp "$FF" bin/ffmpeg && chmod +x bin/ffmpeg && \
    echo "    bundled static ffmpeg from imageio-ffmpeg"
fi
if [ ! -x bin/ffmpeg ]; then
  SYS=$(command -v ffmpeg || true)
  [ -n "$SYS" ] && cp "$SYS" bin/ffmpeg && chmod +x bin/ffmpeg && \
    echo "    copied system ffmpeg ($SYS)"
fi
[ -x bin/ffmpeg ] || echo "    no ffmpeg bundled; flac/aiff/ogg/mp3 still convert via soundfile"

echo "==> Building app (this can take a couple of minutes)"
rm -rf build dist
pyinstaller --noconfirm e2s_autoslice_gui.spec

deactivate

APP="dist/Oe2sLU.app"
if [ -d "$APP" ]; then
  echo ""
  echo "==> Success. Built: $(pwd)/$APP"
  echo "    Opening the dist folder..."
  open dist
else
  echo "ERROR: build finished but $APP was not found. See messages above."
fi

echo ""
echo "Done. Press Return to close this window."
read _
