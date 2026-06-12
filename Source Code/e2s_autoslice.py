#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
e2s_autoslice.py - batch auto-slice loop samples for the Korg electribe
sampler (e2s), offline.

Examples:
  python e2s_autoslice.py loops/ -o sliced/
  python e2s_autoslice.py loops/ -o sliced/ --mode transient --format plain
  python e2s_autoslice.py loops/ -o bank/ --format all --first-slot 19
  python e2s_autoslice.py break.wav -o out/ --bpm 174 --steps 32

Modes:
  grid       equal divisions (default steps from inferred bars x 16)
  transient  onset detection only
  hybrid     equal grid snapped to onsets, silent steps deactivated (default)

Formats:
  esli   one WAV per input with korg/esli chunk + standard smpl/cue (default)
  all    a single e2sSample.all bank
  plain  one WAV per input with only standard smpl + cue chunks (DAW use)
"""

import argparse
import math
import os
import struct
import sys

import numpy as np

import RIFF
import e2s_sample_all as e2s
from e2s_sample_import import from_wav, FromWavError
import slice_engine as se

MAX_SLICES = 64
# Korg e2s total sample memory; output may not exceed this.
MAX_TOTAL_BYTES = 26214396
# Sequencer steps per bar for each Beat setting - this sets the slicing grid
# resolution. 32 gives 32nd-note steps (slices finer than a 16th).
BEAT_STEPS_PER_BAR = {'16': 16, '32': 32, '8 Tri': 12, '16 Tri': 24}


def gather_inputs(paths):
    import audio_convert
    files = []
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if audio_convert.is_audio(name):
                    files.append(os.path.join(p, name))
        elif audio_convert.is_audio(p):
            files.append(p)
        else:
            print('skipping (unsupported audio): %s' % p, file=sys.stderr)
    return files


def convert_inputs(files):
    """Auto-convert any non-WAV inputs to temp 16-bit WAVs. Returns the new
    file list (WAVs unchanged, others replaced with converted paths)."""
    import audio_convert, tempfile
    if not any(not f.lower().endswith('.wav') for f in files):
        return files
    conv_dir = tempfile.mkdtemp(prefix='oe2slu_conv_')
    out = []
    for f in files:
        try:
            out.append(audio_convert.ensure_wav16(f, conv_dir, log=print))
        except Exception as e:
            print('%s: skipped (%s)' % (os.path.basename(f), e),
                  file=sys.stderr)
    return out


def to_mono_float(sample):
    """e2s_sample (16-bit PCM after from_wav) -> mono float array in [-1,1]."""
    fmt = sample.get_fmt()
    raw = sample.get_data().rawdata
    x = np.frombuffer(bytes(raw), dtype='<i2').astype(np.float32) / 32768.0
    if fmt.channels > 1:
        x = x.reshape(-1, fmt.channels).mean(axis=1)
    return x


def resolve_bpm_steps(args, filename, x, sr):
    """Returns (bpm, steps, bars, bpm_source). BPM is resolved first because the
    step (16th-note) size derives from it: step_frames = sr*60/(4*bpm)."""
    num_frames = len(x)
    bpm = args.bpm
    source = 'flag'
    bars = None
    if bpm is None:
        bpm = se.bpm_from_name(os.path.basename(filename))
        source = 'filename'
    if bpm is None:
        # primary: detect tempo from the audio, snapped to a bar-exact value
        bpm, bars = se.bpm_from_audio(num_frames, sr, x)
        source = 'audio'
    if bpm is None:
        bpm, bars = se.bpm_from_length(num_frames, sr)
        source = 'length'
    if bpm is not None and bars is None:
        bars = max(1, int(round(num_frames / sr * bpm / 240.0)))

    spb = BEAT_STEPS_PER_BAR.get(args.beat, 16)
    steps = args.steps
    if steps is None:
        if bars is not None:
            steps = min(MAX_SLICES, bars * spb)
        else:
            steps = spb
    steps = max(1, min(MAX_SLICES, steps))
    return bpm, steps, bars, source


def grid_unit_frames(args, bpm, x, steps, sr):
    """Frames in one grid unit (e.g. a 16th) - the minimum allowed slice length.
    Derived from the BPM and Beat, NOT from loop length, so it stays correct
    even when the loop isn't an exact whole number of bars. Falls back to
    loop/steps only if BPM is unknown."""
    spb = BEAT_STEPS_PER_BAR.get(args.beat, 16)
    if bpm:
        return (240.0 * sr / float(bpm)) / spb
    return len(x) / float(steps) if steps else float(len(x))


def compute_slices(x, sr, args, steps, bpm=None):
    """Returns (starts, active) in frames."""
    if args.mode == 'grid':
        starts = se.grid_slices(len(x), steps)
        active = se.slice_activity(x, starts)
    elif args.mode == 'transient':
        # Minimum slice = one grid unit (a 16th at the detected BPM). Detect
        # onsets, then enforce that spacing so no slice is ever shorter than a
        # 16th - independent of whether the loop is an exact bar count.
        unit = grid_unit_frames(args, bpm, x, steps, sr)
        onsets = se.detect_onsets(x, sr, sensitivity=args.sensitivity,
                                  min_sep_s=max(0.005, unit / sr))
        starts = [0]
        for o in sorted(int(v) for v in onsets):
            if o - starts[-1] >= unit:
                starts.append(o)
        starts = np.array(starts[:max(1, steps)], dtype=int)
        active = se.slice_activity(x, starts)
    else:  # hybrid
        starts, active = se.hybrid_slices(
            x, sr, steps, tolerance=args.tolerance,
            sensitivity=args.sensitivity)
    if not args.drop_silent:
        active = np.ones(len(starts), dtype=bool)
    return starts.astype(int), active


def fill_esli(sample, starts, active, args, steps):
    """Write slice table, step map and full loop setup into the esli chunk."""
    esli = sample.get_esli()
    fmt = sample.get_fmt()
    data = sample.get_data()
    num_frames = len(data) // fmt.blockAlign

    # --- loop setup: loop the whole sample
    if args.loop:
        esli.OSC_LoopStartPoint_offset = 0
        esli.OSC_EndPoint_offset = (num_frames - 1) * fmt.blockAlign
        esli.OSC_OneShot = 0
    esli.OSC_category = e2s.esli_str_to_OSC_cat[args.category]

    # --- slice table
    metrics = None
    if args.slice_metrics:
        x = to_mono_float(sample)
        metrics = se.slice_metrics(x, starts, fmt.samplesPerSec)

    bounds = list(starts) + [num_frames]
    for i in range(MAX_SLICES):
        sl = esli.slices[i]
        if i < len(starts):
            sl.start = int(starts[i])
            sl.length = int(bounds[i + 1] - bounds[i])
            if metrics:
                peak_q16, attack = metrics[i]
                sl.amplitude = peak_q16
                sl.attack_length = min(attack, max(0, sl.length - 1))
            else:
                sl.amplitude = 0
                sl.attack_length = 0
        else:
            sl.start = 0
            sl.length = 0
            sl.attack_length = 0
            sl.amplitude = 0

    # --- step map: place each slice on the grid step nearest its real start
    # over a fixed grid of `steps`. Steps a slice spans are left OFF (-1) so the
    # device holds that slice until the next trigger - this is what lets a slice
    # last several beats instead of one step each. (For grid/hybrid the starts
    # already sit on the grid, so this maps slice i -> step i as before.)
    for i in range(MAX_SLICES):
        esli.sliceSteps[i] = -1
    step_frames = num_frames / float(steps) if steps else float(num_frames)
    for idx, start in enumerate(starts):
        if not active[idx]:
            continue
        step = int(round(start / step_frames)) if step_frames else 0
        step = max(0, min(steps - 1, step))
        esli.sliceSteps[step] = idx
    num_active = sum(1 for i in range(MAX_SLICES) if esli.sliceSteps[i] != -1)
    esli.slicingNumSteps = steps
    esli.slicingBeat = e2s.esli_beat[args.beat]
    esli.slicesNumActiveSteps = num_active


def write_plain_wav(sample, path):
    """Standard WAV with smpl/cue but without the korg chunk."""
    clean = sample.get_clean_copy()
    # drop the korg chunk from the copy
    clean.RIFF.chunkList.chunks = [
        ck for ck in clean.RIFF.chunkList.chunks if ck.header.id != b'korg']
    # reuse e2s export logic for smpl/cue by temporarily re-adding esli data
    # (e2s_sample.write reads esli for loop/cue export), so export manually:
    esli = sample.get_esli()
    fmt = clean.get_fmt()
    uid = 0
    if esli.OSC_LoopStartPoint_offset < esli.OSC_EndPoint_offset and not esli.OSC_OneShot:
        from RIFF.smpl import RIFF_smpl
        smpl = RIFF_smpl()
        smpl.samplePeriod = int(round(1. / esli.samplingFreq * 10. ** 9))
        loop = smpl.add_loop()
        loop.identifier = uid
        loop.start = (esli.OSC_StartPoint_address + esli.OSC_LoopStartPoint_offset) // fmt.blockAlign
        loop.end = (esli.OSC_StartPoint_address + esli.OSC_EndPoint_offset) // fmt.blockAlign
        clean.RIFF.chunkList.chunks.append(
            RIFF.Chunk(header=RIFF.ChunkHeader(id=b'smpl'), data=smpl))
        uid += 1
    from RIFF.cue import RIFF_cue
    cue = RIFF_cue()
    num_frames = len(clean.get_data()) // fmt.blockAlign
    start_frame = esli.OSC_StartPoint_address // fmt.blockAlign
    for sl in esli.slices:
        if not sl.length or sl.start >= num_frames:
            continue
        cp = cue.add_cue_point()
        cp.identifier = uid
        cp.position = sl.start + start_frame
        cp.fccChunk = b'data'
        cp.sampleOffset = sl.start + start_frame
        uid += 1
    if cue.numCuePoints:
        clean.RIFF.chunkList.chunks.append(
            RIFF.Chunk(header=RIFF.ChunkHeader(id=b'cue '), data=cue))
    clean.update_header()
    with open(path, 'wb') as f:
        clean.header.write(f)
        clean.RIFF.write(f)


def build_parser():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('inputs', nargs='+', help='wav files and/or folders')
    ap.add_argument('-o', '--output', default=None, help='output folder')
    ap.add_argument('--mode', choices=('grid', 'transient', 'hybrid'),
                    default='transient')
    ap.add_argument('--format', choices=('esli', 'all'),
                    default='esli', dest='out_format')
    ap.add_argument('--steps', type=int, default=None,
                    help='number of grid steps/slices (default: bars x 16, max 64)')
    ap.add_argument('--bpm', type=float, default=None,
                    help='force BPM (default: filename hint, then loop-length inference)')
    ap.add_argument('--beat', choices=tuple(e2s.esli_beat), default='16')
    ap.add_argument('--tolerance', type=float, default=0.35,
                    help='hybrid: max snap distance as fraction of a step (default 0.15)')
    ap.add_argument('--sensitivity', type=float, default=8.0,
                    help='onset sensitivity on the electribe 1..15 scale; '
                         'higher = more (quieter) hits (default 8)')
    ap.add_argument('--category', choices=tuple(e2s.esli_str_to_OSC_cat),
                    default='Loop')
    ap.add_argument('--no-loop', dest='loop', action='store_false',
                    help='do not set loop points (leave one-shot)')
    ap.add_argument('--keep-silent', dest='drop_silent', action='store_false',
                    help='keep silent steps active in the step map')
    ap.add_argument('--no-metrics', dest='slice_metrics', action='store_false',
                    help='leave per-slice attack/amplitude fields at 0')
    ap.add_argument('--first-slot', type=int, default=19,
                    help='--format all: first sample number to assign (default 19)')
    ap.add_argument('--mono', action='store_true',
                    help='convert stereo inputs to mono (center mix)')
    ap.add_argument('--suffix', default='',
                    help='text appended to each output file name (before .wav)')
    ap.add_argument('--demucs', action='store_true',
                    help='pre-split each input into stems with demucs, '
                         'then slice the selected stems')
    ap.add_argument('--demucs-model', default='htdemucs',
                    help='demucs model name (default htdemucs)')
    ap.add_argument('--stems', default='drums',
                    help='comma-separated stems to slice with --demucs '
                         '(any of drums,bass,other,vocals; default drums)')
    ap.add_argument('--demucs-out', default=None,
                    help='folder for separated stems (default: <output>/_stems)')
    ap.add_argument('--stems-only', action='store_true',
                    help='only split stems into the output folder; do not slice')
    ap.add_argument('-v', '--verbose', action='store_true')
    return ap


def detect_bpms(argv=None):
    """Detect BPM/bars/steps for each input WITHOUT slicing (pre-flight check).
    Returns a list of (name, bpm, bars, steps, source, duration_seconds), using
    the exact same detection the slicer would use for the given options."""
    args = build_parser().parse_args(argv)
    files = convert_inputs(gather_inputs(args.inputs))
    from e2s_sample_import import from_wav, ImportOptions
    out = []
    for p in files:
        name = os.path.basename(p)
        try:
            opts = ImportOptions()
            if args.mono:
                opts.force_mono = 1
            sample, _, _ = from_wav(p, opts)
            fmt = sample.get_fmt()
            sr = fmt.samplesPerSec
            x = to_mono_float(sample)
            bpm, steps, bars, src = resolve_bpm_steps(args, p, x, sr)
            out.append((name, bpm, bars, steps, src, len(x) / float(sr)))
        except Exception as e:
            out.append((name, None, None, None, 'error: %s' % e, 0.0))
    return out


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.output:
        print('error: -o/--output is required', file=sys.stderr)
        return 2

    files = convert_inputs(gather_inputs(args.inputs))
    if not files:
        print('no audio files found', file=sys.stderr)
        return 1
    os.makedirs(args.output, exist_ok=True)

    if args.stems_only:
        import stem_split, shutil
        if not stem_split.is_available():
            print('Stem split needs demucs, which is not installed.\n'
                  '  Install it:  python3 -m pip install demucs "numpy<2"\n'
                  '  detail: %s' % stem_split.unavailable_reason(),
                  file=sys.stderr)
            return 1
        stems = [s.strip() for s in args.stems.split(',') if s.strip()]
        if not stems:
            print('no stems selected (--stems)', file=sys.stderr)
            return 1
        print('splitting stems only [%s] -> %s'
              % (','.join(stems), args.output))
        produced = stem_split.prepass(files, args.output,
                                      model=args.demucs_model, stems=stems,
                                      log=print)
        # flatten out of the <output>/<model>/ subfolder
        final = []
        for p in produced:
            dst = os.path.join(args.output, os.path.basename(p))
            if os.path.abspath(p) != os.path.abspath(dst):
                shutil.move(p, dst)
            final.append(dst)
        md = os.path.join(args.output, args.demucs_model)
        if os.path.isdir(md) and not os.listdir(md):
            os.rmdir(md)
        print('%d stem file(s) written -> %s' % (len(final), args.output))
        return 0 if final else 1

    if args.demucs:
        import stem_split
        if not stem_split.is_available():
            print('Stem split needs demucs, which is not installed.\n'
                  '  Install it:  python3 -m pip install demucs "numpy<2"\n'
                  '  (or untick "Stem split" to slice without it.)\n'
                  '  detail: %s' % stem_split.unavailable_reason(),
                  file=sys.stderr)
            return 1
        stems = [s.strip() for s in args.stems.split(',') if s.strip()]
        if not stems:
            print('no stems selected (--stems)', file=sys.stderr)
            return 1
        stem_dir = args.demucs_out or os.path.join(args.output, '_stems')
        print('stem-splitting %d file(s) with demucs [%s] -> %s'
              % (len(files), args.demucs_model, ','.join(stems)))
        files = stem_split.prepass(files, stem_dir, model=args.demucs_model,
                                   stems=stems, log=print)
        if not files:
            print('no stems produced', file=sys.stderr)
            return 1
        print('slicing %d stem file(s)...' % len(files))

    bank = e2s.e2s_sample_all() if args.out_format == 'all' else None
    bank_bytes = 0
    slot = args.first_slot
    done = 0

    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            from e2s_sample_import import ImportOptions
            opts = ImportOptions()
            if args.mono:
                opts.force_mono = 1
            sample, conv_from, conv_mono = from_wav(path, opts)
        except FromWavError as e:
            print('%s: cannot import (%s)' % (name, type(e).__name__),
                  file=sys.stderr)
            continue
        except Exception as e:
            print('%s: error (%s)' % (name, e), file=sys.stderr)
            continue

        fmt = sample.get_fmt()
        sr = fmt.samplesPerSec
        x = to_mono_float(sample)
        bpm, steps, bars, src = resolve_bpm_steps(args, path, x, sr)
        starts, active = compute_slices(x, sr, args, steps, bpm)
        if len(starts) > MAX_SLICES:
            starts, active = starts[:MAX_SLICES], active[:MAX_SLICES]

        fill_esli(sample, starts, active, args, steps)
        esli = sample.get_esli()
        out_name = name + args.suffix
        esli.OSC_name = bytes(out_name[:16], 'ascii', 'ignore')

        if args.verbose:
            print('%-24s %5.1f BPM(%s) bars=%s slices=%d active=%d mode=%s'
                  % (name[:24], bpm or float('nan'), src, bars,
                     len(starts), int(np.sum(active)), args.mode))

        data_bytes = len(sample.get_data())
        if args.out_format == 'all':
            if bank_bytes + data_bytes > MAX_TOTAL_BYTES:
                print('%s: skipped - bank would exceed the %d-byte e2s memory '
                      'limit' % (out_name, MAX_TOTAL_BYTES), file=sys.stderr)
                continue
            bank_bytes += data_bytes
            esli.set_OSCNum(slot)
            slot += 1
            bank.samples.append(sample)
        else:  # esli
            if data_bytes > MAX_TOTAL_BYTES:
                print('%s: skipped - %d bytes exceeds the %d-byte e2s memory '
                      'limit' % (out_name, data_bytes, MAX_TOTAL_BYTES),
                      file=sys.stderr)
                continue
            with open(os.path.join(args.output, out_name + '.wav'), 'wb') as f:
                sample.write(f, export_smpl=True, export_cue=True)
        done += 1

    if bank is not None and bank.samples:
        bank.save(os.path.join(args.output, 'e2sSample.all'))

    print('%d/%d file(s) processed -> %s' % (done, len(files), args.output))
    return 0 if done else 1


if __name__ == '__main__':
    sys.exit(main())
