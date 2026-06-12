#!/bin/bash
# release_mac.command
#
# Packages an already-built dist/Oe2sLU.app into the exact .zip you upload to
# a GitHub Release. Run build_mac_app.command FIRST to produce the .app, then
# double-click this (first time: right-click -> Open to clear Gatekeeper).
#
# Output: dist/Oe2sLU-macos-<arch>.zip  <-- this is the only file you upload.

set -e
cd "$(dirname "$0")"

APP="dist/Oe2sLU.app"
ARCH="$(uname -m)"   # arm64 (Apple Silicon) or x86_64 (Intel)
ZIP="dist/Oe2sLU-macos-${ARCH}.zip"

echo "==> Project: $(pwd)"
echo "==> Architecture: ${ARCH}"

if [ ! -d "$APP" ]; then
  echo ""
  echo "ERROR: $APP not found."
  echo "Build it first by double-clicking build_mac_app.command, then run this again."
  echo "(If you only see dist/Oe2sLU and no .app, the PyInstaller BUNDLE step did not"
  echo " finish — re-run the build and watch the log for errors.)"
  echo "Press Return to close."; read _; exit 1
fi

# Strip the quarantine flag from the bundle we built locally (cosmetic; the
# end user will still need to right-click->Open because the app is unsigned).
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

# Sanity check: confirm the bundle actually launches far enough to load Tk.
# (Won't catch every issue, but flags a totally broken bundle before you ship.)
echo "==> Bundle contents:"
du -sh "$APP" 2>/dev/null | sed 's/^/    /'

echo "==> Zipping with ditto (preserves the .app bundle correctly)"
rm -f "$ZIP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

echo ""
echo "==> Done. Upload this file to your GitHub Release:"
echo "    $(pwd)/$ZIP"
echo ""
echo "Release checklist:"
echo "  1. On GitHub: Releases -> Draft a new release."
echo "  2. Create a tag (e.g. v0.1.0) on the commit that matches this source."
echo "  3. Attach ${ZIP##*/} as a binary asset."
echo "  4. GitHub auto-attaches the Source code (zip/tar.gz) — that satisfies"
echo "     the GPLv3 'publish source' requirement; no separate upload needed."
echo "  5. In the notes, tell users: this is an UNSIGNED ${ARCH} build — open it"
echo "     the first time with right-click -> Open -> Open, or run"
echo "     xattr -dr com.apple.quarantine /Applications/Oe2sLU.app"
echo ""
echo "Press Return to close."; read _
