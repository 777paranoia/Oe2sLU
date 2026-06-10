# -*- coding: utf-8 -*-
"""
audio_convert.py - auto-convert any input audio to 16-bit PCM WAV.

The slicer works on WAV; this lets users drop in mp3/flac/aiff/m4a/ogg/etc.
Each non-WAV input is decoded to a temporary 16-bit WAV before processing.
Decoding tries soundfile (libsndfile: wav/flac/aiff/ogg, and mp3 on recent
builds) and falls back to ffmpeg if present. Plain WAVs are passed through
untouched (the importer already handles 8/24/32-bit WAV).
"""

import os
import shutil
import stat
import subprocess
import sys
import wave


def _resource(rel):
    base = getattr(sys, "_MEIPASS",
                   os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def ffmpeg_path():
    """Locate an ffmpeg: bundled bin/ first, then PATH, then common installs."""
    for c in (_resource("bin/ffmpeg"), _resource("ffmpeg")):
        if os.path.isfile(c):
            try:
                os.chmod(c, os.stat(c).st_mode | stat.S_IEXEC | stat.S_IXGRP
                         | stat.S_IXOTH)
            except Exception:
                pass
            return c
    w = shutil.which("ffmpeg")
    if w:
        return w
    for d in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg",
              "/usr/bin/ffmpeg"):
        if os.path.isfile(d):
            return d
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

AUDIO_EXTS = ('.wav', '.aif', '.aiff', '.aifc', '.flac', '.mp3', '.m4a',
              '.aac', '.ogg', '.oga', '.opus', '.wma', '.alac', '.caf', '.w64')


def is_audio(path):
    return os.path.splitext(path)[1].lower() in AUDIO_EXTS


def _convert_soundfile(path, out):
    import soundfile as sf
    data, sr = sf.read(path, always_2d=False)
    sf.write(out, data, sr, subtype='PCM_16')


def _convert_ffmpeg(path, out):
    exe = ffmpeg_path()
    if not exe:
        raise RuntimeError('ffmpeg not found')
    subprocess.run([exe, '-y', '-i', path, '-c:a', 'pcm_s16le', out],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   check=True)


def ensure_wav16(path, out_dir, log=print):
    """Return a path to a WAV for `path`, converting to 16-bit PCM if needed.

    .wav inputs are returned unchanged (the importer handles their bit depth);
    any other supported format is decoded into out_dir as 16-bit WAV.
    Raises RuntimeError if it can't be converted.
    """
    if os.path.splitext(path)[1].lower() == '.wav':
        return path
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(out_dir, base + '.wav')
    n = 1
    while os.path.exists(out):
        out = os.path.join(out_dir, '%s_%d.wav' % (base, n))
        n += 1
    errs = []
    for fn in (_convert_soundfile, _convert_ffmpeg):
        try:
            fn(path, out)
            log('  converted %s -> 16-bit wav' % os.path.basename(path))
            return out
        except Exception as e:
            errs.append('%s: %s' % (fn.__name__.replace('_convert_', ''), e))
    raise RuntimeError('could not convert (%s)' % '; '.join(errs))
