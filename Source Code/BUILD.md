# Building & shipping Open Electribe2 Sampler Loop Utility (macOS)

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

## License

GPL-3.0-or-later (continuation of Oe2sSLE by Jonathan Taquet). Replace the
bundled `LICENSE` with the GPLv3 text if it still contains GPL v2, and keep the
attribution in `ATTRIBUTION.txt`.
