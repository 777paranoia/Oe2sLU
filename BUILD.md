# Building & shipping Open Electribe2 Sampler Loop Utility

This produces a self-contained app that bundles Python, Tk, numpy, and all
optional features. End users install nothing — they double-click.

- **macOS** → `Oe2sLU.app` (see below).
- **Windows** → `dist\Oe2sLU\Oe2sLU.exe`, built in the cloud via GitHub Actions
  ([jump to Windows](#building-for-windows)).
- **Linux** → `dist/Oe2sLU/Oe2sLU`, built in the cloud via GitHub Actions
  ([jump to Linux](#building-for-linux)).

> **PyInstaller cannot cross-compile.** A macOS `.app` can only be built on a
> Mac, and a Windows `.exe` can only be built on Windows. There is no way to
> emit a Windows binary from a Mac (or vice versa) — hence the CI job below.

## macOS build

This produces a self-contained `Oe2sLU.app` that bundles Python, Tk,
numpy, and all optional features. End users install nothing — they double-click.

## Prerequisites (build machine only)

- A Mac (a macOS `.app` can only be built on macOS).
- Python 3 **with Tk**. A python.org installer build includes Tk; a Homebrew
  Python needs `brew install python-tk@<version>`. The build script checks this
  and tries to install it for you on Homebrew Pythons.
- Architecture: the app is built for the chip you build on (Apple Silicon
  arm64 or Intel x86_64). Build on each arch you want to ship, or ship two apps.

## Build

Double-click **`build_mac_app.command`** in Finder (first time: right-click →
Open to clear Gatekeeper), or run:

```
./build_mac_app.command
```

It creates a throwaway venv (`.build-venv`), installs PyInstaller + numpy and
the optional extras (sounddevice, Pillow, tkinterdnd2, tkextrafont, demucs),
pins `numpy<2`, then runs `pyinstaller e2s_autoslice_gui.spec`. Result:

```
dist/Oe2sLU.app
```

Notes:
- Only PyInstaller + numpy are mandatory; if an optional extra (or torch/demucs)
  fails to install, the build still completes and that feature is just off.
- demucs pulls in torch, so the bundle is large (often 1 GB+). To ship a lean
  app without stem-splitting, remove `demucs` from the install line in
  `build_mac_app.command` before building.
- To bundle the Gohu font, drop the `.ttf` into `fonts/` before building.

## Drag-and-drop: build with Tk 8.6 (important)

The `tkinterdnd2` drag-and-drop library ships a `tkdnd` binary built for **Tcl/Tk
8.6**. If you build against a Python whose Tk is **9.0** (newer Homebrew
pythons), `tkdnd` fails to load with *"interpreter uses an incompatible stubs
mechanism"*. The app now **survives this** — it detects the failure at startup
and launches with drag-and-drop simply disabled (the Add files / Add folder
buttons still work) — but to keep drag-and-drop working in the shipped app,
build with a Tk-8.6 Python:

- A **python.org** installer build of Python 3.11 or 3.12 bundles Tk 8.6. Install
  that, then run the build with it (e.g. `python3.12 ... ` / point the build
  script at it).
- Check what you have: `python3 -c "import tkinter; print(tkinter.TkVersion)"`.
  `8.6` → drag-and-drop will work; `9.0` → it'll be auto-disabled in the bundle.

This is the only known launch-crash cause and it's now non-fatal regardless.

## First launch / Gatekeeper

The app is **unsigned**, so the first open on any Mac shows a warning. Either:
- Right-click the app → **Open** → Open (one time), or
- `xattr -dr com.apple.quarantine /path/to/Oe2sLU.app` after download.

## Shipping

1. Build `dist/Oe2sLU.app`.
2. Zip it for distribution (preserves the bundle):
   ```
   cd dist && ditto -c -k --sequesterRsrc --keepParent Oe2sLU.app Oe2sLU-macos-arm64.zip
   ```
3. Attach the zip to a GitHub Release. In the release notes, tell users about
   the right-click→Open step (unsigned app) and which chip the build targets.
4. Because this is GPLv3, **publish the source** alongside any binary you
   distribute (the repo satisfies this) and include the `LICENSE` file.

### Optional: signed + notarized (no scary warning)

Requires an Apple Developer ID ($99/yr):

```
codesign --deep --force --options runtime --sign "Developer ID Application: <you>" dist/Oe2sLU.app
ditto -c -k --keepParent dist/Oe2sLU.app upload.zip
xcrun notarytool submit upload.zip --apple-id <id> --team-id <team> --password <app-pw> --wait
xcrun stapler staple dist/Oe2sLU.app
```

## Building for Windows

Windows builds run on a GitHub Actions **windows-latest** runner — no Windows
machine required. The pieces:

- `e2s_autoslice_gui_win.spec` — the Windows PyInstaller spec. Same module/data
  list as the Mac spec, but uses the `.ico` icon, drops the macOS `BUNDLE`
  step, and emits a **one-folder** distribution (deliberate: the torch/demucs
  payload is ~1 GB, and a one-file `.exe` would unpack that to a temp dir on
  every launch).
- `.github/workflows/build-windows.yml` — the CI job: installs PyInstaller +
  `numpy<2` + the optional extras + demucs/torch (CPU), fetches a static
  `ffmpeg.exe` via `imageio-ffmpeg`, runs the spec, zips `dist\Oe2sLU\`, and
  uploads it as a build artifact.

### One-time prerequisite

The repo must live on GitHub (this local folder isn't a git repo yet):

```
git init
git add -A
git commit -m "Oe2sLU"
git branch -M main
git remote add origin https://github.com/<you>/Oe2sLU.git
git push -u origin main
```

### Run it

- In the repo on GitHub → **Actions** tab → **Build Windows app** →
  **Run workflow**. (It also runs automatically when you push a `v*` tag, e.g.
  `git tag v0.2.0 && git push --tags`, and on a tag it attaches the zip to the
  GitHub Release.)
- When the run finishes, download **Oe2sLU-windows-x64** from the run's
  **Artifacts** section. Unzip and run `Oe2sLU.exe`.

### Notes

- The build is large and takes several minutes because of torch/demucs. To ship
  a lean Windows build with no stem-splitting, delete the `demucs` install line
  in the workflow and remove `'demucs'`/`'torch'`/`'torchaudio'` from the
  `collect_all` loop in `e2s_autoslice_gui_win.spec`.
- The `.exe` is **unsigned**, so SmartScreen will show a "Windows protected your
  PC" prompt on first run — users click **More info → Run anyway**. Code-signing
  needs a paid certificate (Authenticode / EV).
- `ffmpeg_path()` in `audio_convert.py` now checks for `bin/ffmpeg.exe` first,
  so the bundled converter is found on Windows; if it's somehow missing,
  conversion falls back to `imageio-ffmpeg`/`soundfile`.

### Local Windows build (optional)

If you do have a Windows machine, you can skip CI and build directly:

```
py -3.12 -m venv .build-venv
.build-venv\Scripts\activate
python -m pip install pyinstaller "numpy<2" sounddevice Pillow tkinterdnd2 soundfile imageio-ffmpeg demucs
python -m pip install "numpy<2"
python -c "import imageio_ffmpeg,shutil;shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(),'bin/ffmpeg.exe')"
pyinstaller --noconfirm e2s_autoslice_gui_win.spec
```

Result: `dist\Oe2sLU\Oe2sLU.exe`.

## Building for Linux

Linux builds run on a GitHub Actions **ubuntu-latest** runner — no Linux
machine required. The pieces:

- `e2s_autoslice_gui_linux.spec` — the Linux PyInstaller spec. Same module/data
  list as the others, but emits a **one-folder** ELF distribution and omits the
  icon (Linux executables carry no embedded icon — that's a `.desktop`-file
  concern, not a binary one).
- `.github/workflows/build-linux.yml` — the CI job: installs Tk + PortAudio via
  apt, then PyInstaller + `numpy<2` + the optional extras + demucs/torch (CPU),
  fetches a static `ffmpeg` via `imageio-ffmpeg`, runs the spec, tars
  `dist/Oe2sLU/`, and uploads it as a build artifact.

### Run it

- In the repo on GitHub → **Actions** tab → **Build Linux app** →
  **Run workflow**. (Also runs on a `v*` tag, and on a tag attaches the tarball
  to the Release.)
- Download **Oe2sLU-linux-x64** from the run's **Artifacts**, then:
  ```
  tar -xzf Oe2sLU-linux-x64.tar.gz
  ./Oe2sLU/Oe2sLU
  ```

### Notes

- The runner builds against the **glibc** of `ubuntu-latest`. The binary runs on
  that glibc or newer; very old distros may be too old. Build on the oldest
  Ubuntu you want to support (pin `runs-on: ubuntu-22.04`) if that matters.
- Runtime needs the GUI/audio shared libs present on the user's machine: most
  desktops already have Tk; audio preview needs `libportaudio2`
  (`sudo apt-get install libportaudio2`). Slicing/BPM/conversion work without it.
- No `ffmpeg.exe`/extension issue here — `ffmpeg_path()` already checks
  `bin/ffmpeg`, which is exactly the Linux name the workflow drops in.
- To ship a lean build without stem-splitting, drop the `demucs` install line in
  the workflow and remove `'demucs'`/`'torch'`/`'torchaudio'` from the
  `collect_all` loop in `e2s_autoslice_gui_linux.spec`.

### Local Linux build (optional)

```
sudo apt-get install -y python3-tk tk libportaudio2
python3 -m venv .build-venv && source .build-venv/bin/activate
pip install pyinstaller "numpy<2" sounddevice Pillow tkinterdnd2 soundfile imageio-ffmpeg demucs
pip install "numpy<2"
mkdir -p bin && cp "$(python -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')" bin/ffmpeg
pyinstaller --noconfirm e2s_autoslice_gui_linux.spec
```

Result: `dist/Oe2sLU/Oe2sLU`.

## License

GPL-3.0-or-later (continuation of Oe2sSLE by Jonathan Taquet). Replace the
bundled `LICENSE` with the GPLv3 text if it still contains GPL v2, and keep the
attribution in `ATTRIBUTION.txt`.
