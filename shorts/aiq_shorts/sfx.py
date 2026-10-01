"""Soft transition sounds: a quiet air whoosh on every scene cut.

Silent visuals under a voice feel like a voiceover laid on in post; a whoosh that swells into
each cut ties the sound to what's on screen. The whoosh is plain filtered noise made here (no
samples, nothing to credit), kept well under the voice. Storyboard control:
"sfx": {"off": true} or {"level_db": -36} (peak dBFS, default -28).
"""
import wave

import numpy as np

SR = 48000


def _whoosh(dur=0.42, seed=7):
    """Noise swelling into the cut and dying after it, brightening as it rises, panned L to R."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    noise = rng.standard_normal(n)
    peak = 0.7  # the loudest point, where the cut lands
    env = np.where(t < peak, (t / peak) ** 2.2, np.exp(-(t - peak) / 0.07))
    # one-pole low-pass whose cutoff sweeps 400 Hz -> 3.5 kHz -> 800 Hz with the envelope
    fc = 400 + 3100 * env
    a = np.exp(-2 * np.pi * fc / SR)
    out = np.empty(n)
    y = 0.0
    for i in range(n):
        y = (1 - a[i]) * noise[i] + a[i] * y
        out[i] = y
    out -= np.convolve(out, np.ones(64) / 64, mode="same")  # drop the rumble
    out *= env
    out /= np.abs(out).max() + 1e-9
    pan = 0.25 + 0.5 * t  # drifts left to right
    return np.stack([out * np.cos(pan * np.pi / 2), out * np.sin(pan * np.pi / 2)], axis=1)


def build_track(cut_times, duration, out_wav, level_db=-28.0):
    """A stereo track for the whole video with a whoosh peaking on each cut time."""
    w = _whoosh()
    lead = int(0.7 * len(w))  # samples before the peak
    buf = np.zeros((int(duration * SR) + len(w), 2))
    gain = 10 ** (level_db / 20)
    for k, t in enumerate(cut_times):
        s = int(t * SR) - lead
        if s < 0:
            continue
        g = gain * (0.85 if k % 2 else 1.0)  # small variation so it doesn't feel mechanical
        buf[s:s + len(w)] += w * g
    buf = np.clip(buf[:int(duration * SR)], -1, 1)
    with wave.open(str(out_wav), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((buf * 32767).astype("<i2").tobytes())
    return out_wav
