# -*- coding: utf-8 -*-
"""
slice_export.py - chop a sliced WAV into one file per slice.

Reads the slice positions already embedded in a WAV (cue points, or the Korg
'korg'/'esli' slice table, or standard 'smpl' loop/cue) and writes each region
out as its own WAV. Pairs naturally with e2s_autoslice: slice a loop, then chop
it into individual hits.

Pure standard library + numpy (numpy only for the optional click-free fades).
"""

import os
import struct
import wave

import numpy as np


# --------------------------------------------------------------- RIFF reading

def _read_riff_chunks(path):
    """Return (fmt_dict, data_bytes, cue_positions, esli_slices)."""
    with open(path, 'rb') as f:
        riff = f.read(12)
        if len(riff) < 12 or riff[:4] != b'RIFF' or riff[8:12] != b'WAVE':
            raise ValueError('not a RIFF/WAVE file')
        fmt = None
        data = None
        cue_positions = []
        esli_slices = []
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            cid, size = struct.unpack('<4sI', hdr)
            body = f.read(size)
            if size % 2 == 1:
                f.read(1)  # padding byte
            if cid == b'fmt ':
                (fmt_tag, channels, rate, _byte_rate, block_align,
                 bits) = struct.unpack('<HHIIHH', body[:16])
                fmt = dict(tag=fmt_tag, channels=channels, rate=rate,
                           block_align=block_align, bits=bits)
            elif cid == b'data':
                data = body
            elif cid == b'cue ':
                (count,) = struct.unpack('<I', body[:4])
                off = 4
                for _ in range(count):
                    (_id, _pos, _fcc, _cs, _bs, sample_off) = struct.unpack(
                        '<II4sIII', body[off:off + 24])
                    cue_positions.append(sample_off)
                    off += 24
            elif cid == b'korg':
                esli_slices = _parse_korg_esli(body)
    if fmt is None or data is None:
        raise ValueError('missing fmt or data chunk')
    return fmt, data, sorted(set(cue_positions)), esli_slices


def _parse_korg_esli(korg_body):
    """Find the esli sub-chunk and pull slice (start,length) pairs."""
    # korg body is itself a chunk list: [id(4) size(4) data...]
    off = 0
    slices = []
    while off + 8 <= len(korg_body):
        cid, size = struct.unpack('<4sI', korg_body[off:off + 8])
        sub = korg_body[off + 8:off + 8 + size]
        off += 8 + size
        if size % 2 == 1:
            off += 1
        if cid == b'esli':
            # slice table lives at a fixed offset in the esli struct; rather
            # than hard-code it, defer to e2s_sample_all which knows the layout.
            try:
                import e2s_sample_all as e2s
                esli = e2s.RIFF_korg_esli()
                n = min(len(sub), len(esli.rawdata))
                esli.rawdata[:n] = sub[:n]
                for sl in esli.slices:
                    if sl.length:
                        slices.append((int(sl.start), int(sl.length)))
            except Exception:
                pass
            break
    return slices


# ------------------------------------------------------------------- chopping

def _boundaries(fmt, data, cue_positions, esli_slices):
    """Return list of (start_frame, end_frame) regions to export."""
    total = len(data) // fmt['block_align']
    regions = []
    if esli_slices:
        for start, length in esli_slices:
            end = min(total, start + length)
            if 0 <= start < end:
                regions.append((start, end))
    elif cue_positions:
        pts = [p for p in cue_positions if 0 <= p < total]
        pts = sorted(set(pts))
        if pts and pts[0] != 0:
            pts = [0] + pts
        bounds = pts + [total]
        for i in range(len(pts)):
            if bounds[i] < bounds[i + 1]:
                regions.append((bounds[i], bounds[i + 1]))
    return regions


def _apply_fade(seg_bytes, fmt, fade_frames):
    """Linear fade in/out on a 16-bit PCM byte segment to avoid clicks."""
    if fade_frames <= 0 or fmt['bits'] != 16:
        return seg_bytes
    ch = fmt['channels']
    a = np.frombuffer(seg_bytes, dtype='<i2').astype(np.float32)
    frames = len(a) // ch
    if frames < 2:
        return seg_bytes
    a = a.reshape(-1, ch)
    n = min(fade_frames, frames // 2)
    if n > 0:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)[:, None]
        a[:n] *= ramp
        a[-n:] *= ramp[::-1]
    return a.astype('<i2').reshape(-1).tobytes()


def chop_wav(path, out_dir, suffix='', fade_ms=0.0, log=print):
    """
    Write one WAV per slice found in `path` into `out_dir`.
    Returns the number of slices written.
    """
    fmt, data, cue_positions, esli_slices = _read_riff_chunks(path)
    if fmt['tag'] != 1:
        raise ValueError('only PCM WAV is supported (got format tag %d)'
                         % fmt['tag'])
    regions = _boundaries(fmt, data, cue_positions, esli_slices)
    src = 'esli' if esli_slices else ('cue' if cue_positions else 'none')
    base = os.path.splitext(os.path.basename(path))[0]
    if not regions:
        log('  %s: no slice markers found (cue/esli); skipped' % base)
        return 0

    os.makedirs(out_dir, exist_ok=True)
    ba = fmt['block_align']
    fade_frames = int(fade_ms * fmt['rate'] / 1000.0)
    width = max(2, len(str(len(regions))))
    count = 0
    for i, (start, end) in enumerate(regions, 1):
        seg = data[start * ba:end * ba]
        if not seg:
            continue
        seg = _apply_fade(seg, fmt, fade_frames)
        name = '%s_%0*d%s.wav' % (base, width, i, suffix)
        with wave.open(os.path.join(out_dir, name), 'wb') as w:
            w.setnchannels(fmt['channels'])
            w.setsampwidth(fmt['bits'] // 8)
            w.setframerate(fmt['rate'])
            w.writeframes(seg)
        count += 1
    log('  %s: wrote %d slice(s) from %s markers' % (base, count, src))
    return count


def chop_many(paths, out_dir, suffix='', fade_ms=0.0, log=print):
    total = 0
    for p in paths:
        try:
            total += chop_wav(p, out_dir, suffix=suffix, fade_ms=fade_ms,
                              log=log)
        except Exception as e:
            log('  FAILED on %s (%s)' % (os.path.basename(p), e))
    return total
