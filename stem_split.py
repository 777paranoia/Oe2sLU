# -*- coding: utf-8 -*-
"""
stem_split.py - optional demucs stem-separation pre-pass for the e2s loop tools.

Splits each input WAV into stems (drums / bass / other / vocals) before the
slicer runs, so you can slice an isolated drum track instead of a full mix.

Runs demucs through its in-process model API (get_model + apply_model) and reads
/ writes the audio with our own WAV helpers. This deliberately avoids
torchaudio's load/save path, which on recent versions requires the separate
'torchcodec' package - so stem splitting keeps working across torch versions and
inside the bundled app.
"""

import os

import numpy as np

DEFAULT_MODEL = "htdemucs"
ALL_STEMS = ("drums", "bass", "other", "vocals")


# --------------------------------------------------------------- availability

def is_available():
    try:
        import torch  # noqa: F401
        import demucs.pretrained  # noqa: F401
        import demucs.apply  # noqa: F401
        return True
    except Exception:
        return False


def unavailable_reason():
    if is_available():
        return None
    try:
        import demucs.pretrained  # noqa: F401
        import torch  # noqa: F401
    except Exception as e:
        return "%s: %s" % (type(e).__name__, e)
    return "demucs not found"


# ------------------------------------------------------------------- audio I/O

def _load_audio(path):
    """Return (channels, samples) float32 in [-1,1] and the sample rate.
    Prefers soundfile (many formats); falls back to the stdlib wave reader for
    plain PCM so we never depend on torchaudio/torchcodec for input."""
    try:
        import soundfile as sf
        data, sr = sf.read(path, dtype="float32", always_2d=True)  # (n, ch)
        return data.T.copy(), int(sr)
    except Exception:
        pass
    import wave
    w = wave.open(path, "rb")
    ch, sw, sr, n = (w.getnchannels(), w.getsampwidth(),
                     w.getframerate(), w.getnframes())
    raw = w.readframes(n)
    w.close()
    if sw == 2:
        a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 1:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    elif sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        a = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        a = np.where(a >= 2 ** 23, a - 2 ** 24, a).astype(np.float32) / 2 ** 23
    elif sw == 4:
        a = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2 ** 31
    else:
        raise ValueError("unsupported sample width %d" % sw)
    return a.reshape(-1, ch).T.copy(), int(sr)


def _write_wav16(path, arr, sr):
    """Write (channels, samples) float array as 16-bit PCM WAV."""
    import wave
    a = np.clip(arr, -1.0, 1.0)
    ai = (a * 32767.0).astype("<i2")            # (ch, n)
    interleaved = ai.T.reshape(-1)              # (n*ch,)
    w = wave.open(path, "wb")
    w.setnchannels(int(arr.shape[0]))
    w.setsampwidth(2)
    w.setframerate(int(sr))
    w.writeframes(interleaved.tobytes())
    w.close()


# ------------------------------------------------------------------- splitting

def split(input_wav, out_dir, model=DEFAULT_MODEL, stems=None, log=print):
    """
    Separate input_wav into stems under <out_dir>/<model>/<track>__<stem>.wav.
    Returns {stem_name: wav_path} for the requested stems.
    """
    import torch
    from demucs.pretrained import get_model
    from demucs.apply import apply_model

    track = os.path.splitext(os.path.basename(input_wav))[0]
    model_dir = os.path.join(out_dir, model)
    os.makedirs(model_dir, exist_ok=True)

    log("  demucs: loading model %s" % model)
    m = get_model(model)
    m.eval()
    ac = getattr(m, "audio_channels", 2)
    msr = int(getattr(m, "samplerate", 44100))

    audio, sr = _load_audio(input_wav)          # (ch, n)
    if audio.shape[0] == 1 and ac == 2:
        audio = np.repeat(audio, 2, axis=0)
    elif audio.shape[0] > ac:
        audio = audio[:ac]

    if sr != msr:
        try:
            import julius
            audio = julius.resample_frac(
                torch.from_numpy(audio), sr, msr).numpy()
        except Exception:
            # linear-interp fallback
            n_out = int(round(audio.shape[1] * msr / float(sr)))
            xp = np.linspace(0, 1, audio.shape[1], endpoint=False)
            xq = np.linspace(0, 1, n_out, endpoint=False)
            audio = np.stack([np.interp(xq, xp, ch) for ch in audio])
        sr = msr

    wav = torch.from_numpy(audio).float()
    ref = wav.mean(0)
    std = float(ref.std()) or 1.0
    wav = (wav - float(ref.mean())) / std

    log("  demucs: separating %s" % track)
    with torch.no_grad():
        out = apply_model(m, wav[None], device="cpu", progress=False,
                          split=True, overlap=0.25)[0]
    out = out * std + float(ref.mean())

    names = list(getattr(m, "sources", ALL_STEMS))
    wanted = tuple(stems) if stems else ALL_STEMS
    found = {}
    for i, nm in enumerate(names):
        if nm not in wanted:
            continue
        p = os.path.join(model_dir, "%s__%s.wav" % (track, nm))
        _write_wav16(p, out[i].cpu().numpy(), msr)
        found[nm] = p
    for st in wanted:
        if st not in found:
            log("  demucs: stem '%s' not produced for %s" % (st, track))
    return found


def prepass(files, out_dir, model=DEFAULT_MODEL, stems=None, log=print):
    """Run split() over many files. Returns a flat list of stem wav paths,
    named '<track>__<stem>.wav' so the slicer's naming stays sensible."""
    out = []
    wanted = tuple(stems) if stems else ALL_STEMS
    for f in files:
        try:
            found = split(f, out_dir, model=model, stems=wanted, log=log)
        except Exception as e:
            log("  demucs FAILED on %s (%s)" % (os.path.basename(f), e))
            continue
        for st in wanted:
            if st in found:
                out.append(found[st])
    return out
