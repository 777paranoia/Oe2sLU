# -*- coding: utf-8 -*-
"""
slice_engine.py - DSP core for batch auto-slicing of loop samples.

Part of the Oe2sSLE loop-tools effort. Pure numpy, no audio I/O here:
callers pass mono float arrays in, get slice positions (sample frames) out.

Modes:
  grid      - N equal divisions of the loop
  transient - onset detection (spectral-flux-style energy novelty)
  hybrid    - equal grid, each point snapped to the strongest nearby onset;
              silent steps reported so they can be deactivated
"""

import math
import re

import numpy as np

# ---------------------------------------------------------------- envelope

def _frame_rms(x, hop, win):
    """RMS envelope, one value per hop."""
    n = max(1, (len(x) - win) // hop + 1)
    out = np.empty(n)
    for i in range(n):
        seg = x[i * hop:i * hop + win]
        out[i] = math.sqrt(float(np.mean(seg * seg))) if len(seg) else 0.0
    return out


def onset_strength(x, sr, hop=None, win=1024):
    """Spectral-flux onset novelty. Returns (novelty, hop).

    Spectral flux = sum of the positive frame-to-frame change in the magnitude
    spectrum. Unlike a plain energy/RMS envelope (which only reacts to volume),
    this fires on spectral change - new notes, snares, hats, percussive attacks
    - so it tracks actual beats rather than just dynamics. A logarithmic
    (dB) magnitude is used so quieter hits still register.
    """
    if hop is None:
        hop = max(64, sr // 200)          # ~5 ms resolution
    if len(x) < win:
        return np.zeros(1), hop
    nfr = 1 + (len(x) - win) // hop
    window = np.hanning(win).astype(np.float32)
    # frame the signal (nfr x win) and window it
    idx = np.arange(win)[None, :] + hop * np.arange(nfr)[:, None]
    frames = x[idx] * window
    mag = np.abs(np.fft.rfft(frames, axis=1))
    logmag = np.log1p(mag)                 # compress dynamics so soft hits count
    diff = np.diff(logmag, axis=0)
    diff[diff < 0] = 0.0                   # half-wave rectify: onsets only
    flux = diff.sum(axis=1)
    nov = np.concatenate(([0.0], flux))    # length nfr, aligned to frame starts
    return nov.astype(np.float64), hop


def detect_onsets(x, sr, sensitivity=8.0, min_sep_s=0.030):
    """Peak-pick the novelty curve. Returns onset positions in frames.

    `sensitivity` follows the electribe firmware's Sample Edit scale of 1..15:
    1 keeps only the strongest hits, 15 catches the quietest ones.
    """
    nov, hop = onset_strength(x, sr)
    if not len(nov) or float(np.max(nov)) <= 0.0:
        return np.array([], dtype=int)
    med = float(np.median(nov))
    mad = float(np.median(np.abs(nov - med))) + 1e-9
    maxn = float(np.max(nov))
    # Map the 1..15 device scale to peak-relative gates. Higher sensitivity =>
    # smaller fraction of the peak required => more (quieter) onsets caught.
    s = min(15.0, max(1.0, float(sensitivity)))
    t = (s - 1.0) / 14.0
    nov_frac = 0.35 * (1.0 - t) + 0.02
    amp_frac = 0.50 * (1.0 - t) + 0.01
    thresh = max(med + 2.5 * mad, nov_frac * maxn)
    min_sep = max(1, int(min_sep_s * sr / hop))

    peaks = []
    i = 1
    while i < len(nov) - 1:
        if nov[i] >= thresh and nov[i] >= nov[i - 1] and nov[i] >= nov[i + 1]:
            if peaks and i - peaks[-1] < min_sep:
                if nov[i] > nov[peaks[-1]]:
                    peaks[-1] = i
            else:
                peaks.append(i)
        i += 1

    frames = np.array(peaks, dtype=int) * hop
    # Refine: the forward-looking RMS window makes the novelty peak fire
    # up to ~2 hops *before* the actual attack, so search forward from the
    # estimate and take the first sample reaching 25% of the local peak.
    refined = []
    for f in frames:
        a = int(f)
        b = min(len(x), f + 3 * hop)
        seg = np.abs(x[a:b])
        if len(seg):
            peak = float(np.max(seg))
            idx = int(np.argmax(seg >= 0.25 * peak))
            refined.append(a + idx)
        else:
            refined.append(int(f))
    refined = np.unique(np.array(refined, dtype=int))

    # Amplitude gate: log-energy novelty fires on any onset regardless of how
    # loud it is, so sensitivity must filter by actual hit strength. Keep only
    # onsets whose local peak is at least a sensitivity-scaled fraction of the
    # loudest hit. Higher sensitivity -> smaller fraction -> more (quieter)
    # hits kept; lower -> only the strongest survive.
    if len(refined):
        win = max(1, int(0.03 * sr))
        amps = np.array([float(np.max(np.abs(x[f:f + win]), initial=0.0))
                         for f in refined])
        gmax = float(amps.max()) or 1.0
        refined = refined[amps >= amp_frac * gmax]
    return refined

# --------------------------------------------------------------------- BPM

_BPM_RE = re.compile(r'(?:^|[^0-9])(\d{2,3}(?:\.\d+)?)\s*bpm', re.IGNORECASE)
_BPM_RE2 = re.compile(r'bpm\s*[_\- ]?(\d{2,3}(?:\.\d+)?)', re.IGNORECASE)


def bpm_from_name(name):
    """Parse '..._140bpm_...' or 'bpm140...' style hints. None if absent."""
    for rx in (_BPM_RE, _BPM_RE2):
        m = rx.search(name)
        if m:
            bpm = float(m.group(1))
            if 40 <= bpm <= 300:
                return bpm
    return None


def bpm_from_length(num_frames, sr, lo=68.0, hi=190.0):
    """
    Assume the file is a whole number of 4/4 bars and find the bars count
    whose implied BPM lands in [lo, hi). Returns (bpm, bars) or (None, None).
    """
    dur = num_frames / float(sr)
    best = None
    for bars in (1, 2, 4, 8, 16, 32, 3, 6, 12, 24):
        bpm = 240.0 * bars / dur
        if lo <= bpm < hi:
            # prefer near-integer BPM, then fewer bars
            score = (abs(bpm - round(bpm)), bars)
            if best is None or score < best[0]:
                best = (score, bpm, bars)
    if best:
        return best[1], best[2]
    return None, None


def tempo_from_audio(x, sr, lo=70.0, hi=180.0):
    """
    Estimate tempo (BPM) from the audio by autocorrelating the onset-strength
    envelope and picking the strongest periodicity in [lo, hi). Returns a float
    BPM or None. This is an estimate; reconcile it with the loop length for an
    exact, bar-aligned value.
    """
    nov, hop = onset_strength(x, sr)
    if len(nov) < 8:
        return None
    nov = nov - float(np.mean(nov))
    ac = np.correlate(nov, nov, mode='full')[len(nov) - 1:]
    if len(ac) < 4 or ac[0] <= 0:
        return None
    min_lag = max(1, int(round((60.0 / hi) * sr / hop)))
    max_lag = min(len(ac) - 1, int(round((60.0 / lo) * sr / hop)))
    if max_lag <= min_lag:
        return None
    lag = min_lag + int(np.argmax(ac[min_lag:max_lag + 1]))
    period_s = lag * hop / float(sr)
    if period_s <= 0:
        return None
    return 60.0 / period_s


def bpm_from_audio(num_frames, sr, x, lo=68.0, hi=190.0):
    """
    Detect BPM by testing every bar-count's exact (loop-length-derived) BPM and
    scoring how well that tempo's beat grid lines up with the onset envelope.
    Because the candidates come from the loop length, the winner always tiles
    the loop in whole bars. Returns (bpm, bars) or (None, None).

    Caveat: tempo octave (e.g. 87 vs 174) is musically ambiguous from beats
    alone; both give a valid grid. For fast genres set BPM manually if needed.
    """
    nov, hop = onset_strength(x, sr)
    if len(nov) < 8:
        return None, None
    nov = nov - float(np.mean(nov))
    ac = np.correlate(nov, nov, mode='full')[len(nov) - 1:]
    if len(ac) < 4 or ac[0] <= 0:
        return None, None
    ac = ac / ac[0]
    dur = num_frames / float(sr)
    center, sigma = 120.0, 0.85   # perceptual tempo prior (favours ~120 BPM)

    def acv(lag):
        i = int(round(lag))
        return ac[i] if 0 < i < len(ac) else 0.0

    best = None
    for bars in range(1, 65):
        bpm = 240.0 * bars / dur
        if not (lo <= bpm < hi):
            continue
        beat_lag = (60.0 / bpm) * sr / hop          # one beat in hops
        # how periodic the onsets are at this candidate's beat period, weighted
        # by a log-Gaussian tempo preference to resolve octave ambiguity
        w = math.exp(-0.5 * (math.log2(bpm / center) / sigma) ** 2)
        score = acv(beat_lag) * w
        if best is None or score > best[0]:
            best = (score, bpm, bars)
    if best:
        return best[1], best[2]
    return None, None

# ------------------------------------------------------------------ slicing

def grid_slices(num_frames, steps):
    """Equal divisions. Returns int array of slice starts (frames)."""
    return np.floor(np.arange(steps) * num_frames / float(steps)).astype(int)


def hybrid_slices(x, sr, steps, tolerance=0.35, sensitivity=8.0):
    """
    Equal grid snapped to onsets.

    Each grid point moves to the strongest detected onset within
    +/- tolerance * step_length; if none, it stays on the grid.
    Returns (starts, active) where active[i] is False for steps whose
    slice audio is essentially silent.
    """
    num_frames = len(x)
    step_len = num_frames / float(steps)
    tol = int(step_len * tolerance)
    onsets = detect_onsets(x, sr, sensitivity=sensitivity)
    grid = grid_slices(num_frames, steps)

    starts = grid.copy()
    for i, g in enumerate(grid):
        if not len(onsets):
            break
        d = np.abs(onsets - g)
        j = int(np.argmin(d))
        if d[j] <= tol:
            starts[i] = onsets[j]
    # enforce monotonicity after snapping
    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            starts[i] = min(num_frames - 1, starts[i - 1] + 1)

    active = slice_activity(x, starts)
    return starts, active


def transient_slices(x, sr, sensitivity=8.0, max_slices=64):
    """Slices at detected onsets only. Always includes frame 0."""
    onsets = detect_onsets(x, sr, sensitivity=sensitivity)
    starts = np.unique(np.concatenate(([0], onsets)))
    if len(starts) > max_slices:
        # keep the strongest: re-rank by local peak amplitude
        peaks = [float(np.max(np.abs(x[s:s + int(0.05 * sr)]) if len(x[s:s + int(0.05 * sr)]) else 0))
                 for s in starts]
        order = np.argsort(peaks)[::-1][:max_slices]
        starts = np.sort(starts[order])
        if starts[0] != 0:
            starts[0] = 0
    return starts.astype(int)


def slice_activity(x, starts, silence_db=-48.0):
    """Boolean per slice: does it contain audible audio?"""
    thresh = 10.0 ** (silence_db / 20.0)
    bounds = list(starts) + [len(x)]
    return np.array([
        float(np.max(np.abs(x[bounds[i]:bounds[i + 1]]), initial=0.0)) > thresh
        for i in range(len(starts))
    ])

# --------------------------------------------------- per-slice esli metadata

def slice_metrics(x, starts, sr):
    """
    For each slice: (peak_q16, attack_frames).

    peak_q16: slice peak in Q16 (65536 == full scale) - matches the
              0..65536 range Oe2sSLE's editor allows for 'amplitude'.
    attack_frames: frames from slice start to the envelope peak,
              capped at the slice length - plausible reconstruction of
              the firmware's transient-extent measurement.
    """
    bounds = list(starts) + [len(x)]
    out = []
    for i in range(len(starts)):
        seg = np.abs(x[bounds[i]:bounds[i + 1]])
        if not len(seg):
            out.append((0, 0))
            continue
        peak = float(np.max(seg))
        peak_q16 = int(round(min(peak, 1.0) * 65536))
        # smooth then find envelope peak position
        w = max(1, sr // 1000)
        if len(seg) > w:
            k = np.ones(w) / w
            env = np.convolve(seg, k, mode='same')
        else:
            env = seg
        attack = int(np.argmax(env))
        out.append((peak_q16, attack))
    return out
