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
import json
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
        # per-file manual override (from the Set-BPM window) wins over auto
        # detection - keyed by the file's stem (name without extension).
        ov = getattr(args, 'bpm_overrides', None)
        if ov:
            stem = os.path.splitext(os.path.basename(filename))[0]
            if stem in ov and ov[stem]:
                bpm = float(ov[stem])
                source = 'override'
    if bpm is None:
        bpm = se.bpm_from_name(os.path.basename(filename))
        source = 'filename'
    if bpm is None:
        # PRIMARY: a loop is almost always a whole/half number of bars, so its
        # length pins the bar count exactly -> exact, bar-locked BPM. No tempo
        # guessing needed; this is what keeps the 16th grid tiling perfectly.
        bpm, bars = se.bpm_from_length(num_frames, sr)
        source = 'length'
    if bpm is None:
        # fallback only: onset-autocorrelation estimate, used when the length is
        # ambiguous (no bar count lands in range).
        bpm, bars = se.bpm_from_audio(num_frames, sr, x)
        source = 'audio'
    if bpm is not None and bars is None:
        bars = max(1, int(round(num_frames / sr * bpm / 240.0)))

    spb = BEAT_STEPS_PER_BAR.get(args.beat, 16)
    steps = args.steps
    if steps is None:
        if bars is not None:
            # bars may be fractional (e.g. 0.5 for a half-bar loop); the grid is
            # always a whole number of 16th steps.
            steps = int(round(bars * spb))
        else:
            steps = spb
    steps = max(1, min(MAX_SLICES, int(steps)))
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
    """Returns (starts, active, eff_steps) in frames.

    eff_steps is the number of grid steps the slices were actually cut on -
    the device's step map MUST use this same value so every slice begins on a
    step boundary and no slice is shorter than one step. For grid/hybrid this
    equals `steps`; for transient it is the (clamped) 16th-note cell count.
    """
    if args.mode == 'grid':
        starts = se.grid_slices(len(x), steps)
        active = se.slice_activity(x, starts)
        eff_steps = steps
    elif args.mode == 'transient':
        # Grid-locked transient slicing:
        #   1. BPM (resolved by the caller) defines one grid unit (a 16th at
        #      the Beat setting's resolution).
        #   2. The unit count is clamped to the TOTAL length - the loop is
        #      divided into `total` equal cells so the grid always tiles the
        #      file exactly, bar-exact or not.
        #   3. Every detected onset is quantized to the grid line of the cell
        #      it falls in. Slice starts therefore sit ON the grid and every
        #      slice length is a whole number of 16ths. A note that plays
        #      off-grid keeps its real position *inside* its slice, so the
        #      step map can never trigger it before it actually occurs.
        unit = grid_unit_frames(args, bpm, x, steps, sr)
        total = max(1, int(round(len(x) / unit)))
        # The device has only MAX_SLICES steps. If the 16th-note grid would have
        # more cells than that, coarsen the grid (fewer, larger cells) so it
        # still tiles the whole loop. This is what guarantees the slice grid and
        # the step grid are identical - without it, slices get cut finer than a
        # step and several collide into one step in the map.
        total = max(1, min(total, MAX_SLICES))
        cell = len(x) / float(total)
        onsets = se.detect_onsets(x, sr, sensitivity=args.sensitivity)
        cells = {0}
        for o in onsets:
            # snap each transient to the NEAREST grid line (16th step). Onset
            # detection can fire a hair early or late, so nearest-rounding keeps
            # the boundary on the intended step instead of slipping a cell.
            cells.add(min(total - 1, max(0, int(round(o / cell)))))
        # at most one slice per cell, and never more than the grid has
        cap = max(1, min(MAX_SLICES, total))
        if len(cells) > cap:
            # over the slice budget: keep the strongest hits (cell 0 always)
            win = max(1, int(0.05 * sr))
            def _peak(c):
                a = int(c * cell)
                return float(np.max(np.abs(x[a:a + win]), initial=0.0))
            keep = sorted((c for c in cells if c), key=_peak,
                          reverse=True)[:cap - 1]
            cells = {0} | set(keep)
        starts = np.array([int(math.floor(c * cell)) for c in sorted(cells)],
                          dtype=int)
        active = se.slice_activity(x, starts)
        eff_steps = total
    else:  # hybrid
        starts, active = se.hybrid_slices(
            x, sr, steps, tolerance=args.tolerance,
            sensitivity=args.sensitivity)
        eff_steps = steps
    if not args.drop_silent:
        active = np.ones(len(starts), dtype=bool)
    return starts.astype(int), active, eff_steps


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
    steps = max(1, min(MAX_SLICES, int(steps)))
    step_frames = num_frames / float(steps)
    for idx, start in enumerate(starts):
        if not active[idx]:
            continue
        step = int(round(start / step_frames))
        step = max(0, min(steps - 1, step))
        # Two slices must never land on the same step - that would mean a slice
        # shorter than one step division. If it happens (e.g. rounding at the
        # grid edge), push this slice to the next free step so it is never
        # dropped, keeping one slice per step.
        while step < steps and esli.sliceSteps[step] != -1:
            step += 1
        if step >= steps:
            break
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
    ap.add_argument('--bpm-map', default=None, dest='bpm_map',
                    help='path to a JSON file of {"filestem": bpm} per-file BPM '
                         'overrides (used by the Set-BPM window)')
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


def _load_bpm_map(path):
    """Read a {stem: bpm} JSON override file. Returns {} on any problem so a
    bad/missing map never blocks slicing."""
    if not path:
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {str(k): float(v) for k, v in raw.items() if v}
    except Exception:
        return {}


def detect_bpms(argv=None):
    """Detect BPM/bars/steps for each input WITHOUT slicing (pre-flight check).
    Returns a list of (name, bpm, bars, steps, source, duration_seconds, path),
    using the exact same detection the slicer would use for the given options.
    `path` is the actual (possibly format-converted) WAV, for audio preview."""
    args = build_parser().parse_args(argv)
    args.bpm_overrides = _load_bpm_map(getattr(args, 'bpm_map', None))
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
            out.append((name, bpm, bars, steps, src, len(x) / float(sr), p))
        except Exception as e:
            out.append((name, None, None, None, 'error: %s' % e, 0.0, p))
    return out


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.bpm_overrides = _load_bpm_map(getattr(args, 'bpm_map', None))
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
        starts, active, eff_steps = compute_slices(x, sr, args, steps, bpm)
        if len(starts) > MAX_SLICES:
            starts, active = starts[:MAX_SLICES], active[:MAX_SLICES]

        # use the grid the slices were actually cut on for the step map
        fill_esli(sample, starts, active, args, eff_steps)
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
