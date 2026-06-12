# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the e2s auto-slice GUI -- WINDOWS build.
# Produces a one-folder distribution: dist/Oe2sLU/Oe2sLU.exe plus its
# support files. One-folder (not one-file) is deliberate: the bundle pulls
# in torch/demucs and is ~1 GB; a one-file .exe would unpack that to a temp
# dir on every launch (slow). The folder launches instantly.
#
# Build (on Windows):
#     pyinstaller e2s_autoslice_gui_win.spec
# Result:
#     dist\Oe2sLU\Oe2sLU.exe
#
# NOTE: PyInstaller cannot cross-build. This must run on Windows (locally or
# on a windows-latest CI runner) -- a Mac/Linux host cannot emit a Windows exe.

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
# bundle ffmpeg.exe (for m4a/aac/wma conversion) if one was placed in bin/
import os as _os
if _os.path.isdir('bin'):
    datas += [('bin', 'bin')]
binaries = []
ICON = 'images/AppIcon.ico'

# Pull in demucs + torch (and their data/weights helpers) so the optional
# stem-split pre-pass works inside the bundled app. Missing packages are
# skipped, so the app still builds without the stem feature installed.
from PyInstaller.utils.hooks import collect_all
for _pkg in ('demucs', 'torch', 'torchaudio', 'julius', 'openunmix',
             'dora', 'einops', 'lameenc', 'soundfile', 'ffmpeg',
             'PIL', 'tkinterdnd2'):
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

# One-folder layout: EXE holds only the bootstrap; COLLECT gathers the rest.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Oe2sLU',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # GUI app: no console window
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Oe2sLU',
)
