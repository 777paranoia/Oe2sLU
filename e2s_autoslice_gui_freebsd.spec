# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the e2s auto-slice GUI -- FreeBSD build (LEAN).
# Produces a one-folder distribution: dist/Oe2sLU/Oe2sLU (an ELF binary) plus
# its support files.
#
# IMPORTANT — this is a LEAN build with NO stem-splitting:
#   * PyTorch has no FreeBSD wheels, so demucs/torch are deliberately NOT
#     collected here. The Stem-split feature is simply unavailable on FreeBSD;
#     everything else (slicing, BPM detection, conversion, the editor) works.
#   * No ffmpeg is bundled (imageio-ffmpeg ships no FreeBSD binary). m4a/aac/wma
#     conversion uses a system ffmpeg (pkg install ffmpeg) via PATH; wav/flac/
#     aiff/ogg/mp3 go through libsndfile. ffmpeg_path() already falls back to
#     shutil.which("ffmpeg") at runtime, so nothing extra is needed.
#
# Build (on FreeBSD, with Tk available):
#     pyinstaller e2s_autoslice_gui_freebsd.spec
# Result:
#     dist/Oe2sLU/Oe2sLU
#
# NOTE: PyInstaller cannot cross-build. This must run on FreeBSD (the CI job
# uses a FreeBSD VM on an Ubuntu runner via vmactions/freebsd-vm).

block_cipher = None

hiddenimports = ['e2s_autoslice', 'slice_engine', 'e2s_sample_all',
                 'e2s_sample_import', 'slice_export', 'stem_split',
                 'audio_convert',
                 'RIFF', 'RIFF.smpl', 'RIFF.cue',
                 'Oe2sSLE_GUI', 'VerticalScrolledFrame', 'audio',
                 'e2s_sample_trim', 'utils', 'version', 'wav_tools',
                 'GUI', 'GUI.res', 'GUI.widgets', 'GUI.tooltip',
                 'GUI.stereo_to_mono', 'GUI.wait_dialog', 'GUI.about_dialog',
                 'GUI.import_options', 'GUI.export_options',
                 'GUI.exchange_sample_dialog']
datas = [('steak.png', '.'),
         ('images', 'images'),
         ('fonts', 'fonts')]
# bundle a static ffmpeg only if one happens to be present in bin/ (normally
# not on FreeBSD).
import os as _os
if _os.path.isdir('bin'):
    datas += [('bin', 'bin')]
binaries = []

# Only the lightweight optional extras -- NOT demucs/torch (no FreeBSD wheels).
from PyInstaller.utils.hooks import collect_all
for _pkg in ('soundfile', 'sounddevice', 'PIL', 'tkinterdnd2'):
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
    excludes=['torch', 'demucs', 'torchaudio'],   # ensure no accidental pull-in
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    console=False,
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
