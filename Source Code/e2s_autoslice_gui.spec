# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the e2s auto-slice GUI.
# Builds a standalone macOS .app that bundles Python + numpy + Tkinter,
# so the tool runs by double-click with no terminal and no Python install.
#
# Build (on a Mac):
#     pyinstaller e2s_autoslice_gui.spec
# Result:
#     dist/Oe2sLU.app   (and dist/Oe2sLU for the raw binary)
#
# A .spec works on Windows/Linux too, but produces an .exe / ELF binary
# there, not a .app -- PyInstaller cannot cross-build a macOS bundle.

block_cipher = None

# Local sibling modules are reached through normal imports; numpy is handled by
# PyInstaller's bundled hooks. List extras here if a build reports a missing
# module.
hiddenimports = ['e2s_autoslice', 'slice_engine', 'e2s_sample_all',
                 'e2s_sample_import', 'slice_export', 'stem_split',
                 'audio_convert',
                 'RIFF', 'RIFF.smpl', 'RIFF.cue',
                 # the embeddable Oe2sSLE editor (lazy-imported on toggle)
                 'Oe2sSLE_GUI', 'VerticalScrolledFrame', 'audio',
                 'e2s_sample_trim', 'utils', 'version', 'wav_tools',
                 'GUI', 'GUI.res', 'GUI.widgets', 'GUI.tooltip',
                 'GUI.stereo_to_mono', 'GUI.wait_dialog', 'GUI.about_dialog',
                 'GUI.import_options', 'GUI.export_options',
                 'GUI.exchange_sample_dialog']
# Bundle the icon, steak background, and the editor's image resources.
datas = [('steak.png', '.'),
         ('images', 'images'),
         ('fonts', 'fonts')]
# bundle ffmpeg (for m4a/aac/wma conversion) if one was placed in bin/
import os as _os
if _os.path.isdir('bin'):
    datas += [('bin', 'bin')]
binaries = []
ICON = 'images/AppIcon.icns'

# Pull in demucs + torch (and their data/weights helpers) so the optional
# stem-split pre-pass works inside the bundled app. Missing packages are
# skipped, so the app still builds without the stem feature installed.
from PyInstaller.utils.hooks import collect_all
for _pkg in ('demucs', 'torch', 'torchaudio', 'julius', 'openunmix',
             'dora', 'einops', 'lameenc', 'soundfile', 'ffmpeg',
             'PIL', 'tkinterdnd2', 'tkextrafont'):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass

a = Analysis(
    ['e2s_autoslice_gui.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Oe2sLU',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon=ICON,
)

app = BUNDLE(
    exe,
    name='Oe2sLU.app',
    icon=ICON,
    bundle_identifier='org.oe2slu.app',
    info_plist={
        'CFBundleName': 'Oe2sLU',
        'CFBundleDisplayName': 'Open Electribe2 Sampler Loop Utility',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13.0',
    },
)
