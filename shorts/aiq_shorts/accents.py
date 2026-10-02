"""Musical hits on the big moments: a deep impact when a big number or a key visual lands.

Data-explainer videos (the author's reference videos) punctuate their biggest numbers with a
low "boom" in the music: the "$70M" callout lands on a sub-bass hit, the cut to a new chapter
lands on one, and the opening frame starts on one. This module finds those moments in the
storyboard (the times the numbers actually appear, after voice timing is applied) and builds a
track of impacts to mix over the music bed. No whooshes or risers: just a short, deep, tonal
hit with a soft tail, so it reads as part of the score.

Storyboard control: "accents": {"off": true} or {"level_db": -12} (peak dBFS, default -10).
Per scene: "accent": false skips that scene's hit, "accent": true adds one on the scene's cut,
and "accent_at": 1.2 puts it at a chosen second within the scene.
"""
import wave

import numpy as np

SR = 48000
MIN_GAP = 3.5      # seconds between hits, so they stay special
MAX_HITS = 9


def _impact(strength=1.0, seed=3):
    """A deep tonal boom: a pitch-dropping sub (90 -> 42 Hz), a short low thump for the attack,
    and a dark tail, about 1.8s long."""
    n = int(1.8 * SR)
    t = np.arange(n) / SR
    f = 42 + 48 * np.exp(-t / 0.09)                       # pitch drop
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.55)
    rng = np.random.default_rng(seed)
    thump = rng.standard_normal(n) * np.exp(-t / 0.035)
    for _ in range(3):                                     # crude low-pass: keep the thud, lose the hiss
        thump = np.convolve(thump, np.ones(24) / 24, mode="same")
    tail = rng.standard_normal(n)
    for _ in range(4):
        tail = np.convolve(tail, np.ones(48) / 48, mode="same")
    tail *= np.exp(-t / 0.7) * (1 - np.exp(-t / 0.05))
    x = sub + 0.9 * thump / (np.abs(thump).max() + 1e-9) + 0.25 * tail / (np.abs(tail).max() + 1e-9)
    x[: int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))  # no click
    x /= np.abs(x).max() + 1e-9
    return x * strength


def moments(tl):
    """(time, strength) of the big moments, in video seconds."""
    out = []
    for i, scene in enumerate(tl.scenes):
        spec, (a, _b) = scene.spec, tl.spans[i]
        if spec.get("accent") is False:
            continue
        if "accent_at" in spec:
            out.append((a + float(spec["accent_at"]), 1.0, True))
            continue
        hits = []
        t = spec["type"]
        if i == 0:
            hits.append((0.0, 1.0))                        # the opening lands on a hit
        if t == "big_number":
            hits += [(float(s.get("at", 0.5)), 1.0) for s in spec.get("stats", [])]
        if t in ("photo", "video", "hook"):
            hits += [(float(o.get("at", 0.5)), 1.0) for o in spec.get("overlays", []) if o.get("kind") == "stat"]
        if t in ("vbars", "hbars") and spec.get("annotation"):
            hits.append((float(spec["annotation"].get("at", 2.0)), 0.85))
        if t == "waffle" and spec.get("big"):
            hits.append((float(spec["big"].get("at", 2.0)), 0.9))
        if t == "news":
            items = spec.get("items") or [{}]
            hits.append((float(items[0].get("at", 0.1)), 0.8))
        if t == "article_card":
            hits.append((0.0, 0.7))
        if spec.get("accent") is True and not hits:
            hits.append((0.0, 0.9))
        out += [(a + h, s, spec.get("accent") is True) for h, s in hits]
    # keep them special: no two within MIN_GAP, stronger first, at most MAX_HITS
    out.sort(key=lambda m: (-m[2], -m[1], m[0]))
    keep = []
    for t, s, forced in out:
        if forced or all(abs(t - k) >= MIN_GAP for k, _ in keep):
            keep.append((t, s))
        if len(keep) >= MAX_HITS:
            break
    return sorted(keep)


def build_track(tl, out_wav, level_db=-10.0):
    """A stereo track for the whole video with an impact on each big moment. Returns the moments."""
    hits = moments(tl)
    n = int(tl.duration * SR)
    buf = np.zeros(n + 2 * SR)
    gain = 10 ** (level_db / 20)
    for k, (t, s) in enumerate(hits):
        start = int(max(0.0, t - 0.01) * SR)
        x = _impact(s, seed=3 + k % 3)
        buf[start:start + len(x)] += x * gain
    buf = np.clip(buf[:n], -1, 1)
    st = np.stack([buf, buf], axis=1)
    with wave.open(str(out_wav), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((st * 32767).astype("<i2").tobytes())
    return hits
