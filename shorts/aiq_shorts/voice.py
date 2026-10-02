"""Sync a real voiceover to the storyboard.

The author reads script.md; this module cleans the recording, finds when each script
line is spoken (speech recognition with word timestamps, aligned to the script), and
stores the cue times in storyboard["voiceover"] so the engine times every scene, caption
and animation to the actual delivery and mixes the voice into the video.

Two copies of the voice share one timeline: a plainly denoised one that speech recognition
and onset snapping read, and a studio-cleaned one (enhance.py: echo removal, tone, dynamics)
that goes into the video. Every cut is applied to both.
"""
import difflib
import json
import re
import subprocess
from pathlib import Path

from . import enhance as EN
from . import media as M

ASR_MODEL = "base.en"  # small, fast on CPU, accurate enough for timing a known script


def _ff(*args):
    subprocess.run([M.ffmpeg_exe(), "-loglevel", "error", "-y", *args], check=True)


def clean(src, out_wav):
    """The copy speech recognition reads: cut rumble, light denoise, level to ~-14 LUFS.
    Same length as the source, so it lines up with the studio copy."""
    _ff("-i", str(src), "-vn", "-ac", "1", "-ar", "48000", "-af",
        "highpass=f=70,afftdn=nf=-28,loudnorm=I=-14:TP=-1.5:LRA=11", str(out_wav))
    return out_wav


def _align_to(wav, ref):
    """Shift and pad/trim `wav` so it lines up sample for sample with `ref` (the denoiser in
    `clean` delays its copy by ~25ms; the cue times are measured on that copy)."""
    import wave
    import numpy as np
    def load(p):
        with wave.open(str(p)) as w:
            return w.getparams(), np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    params, x = load(wav)
    _, r = load(ref)
    env = lambda a: np.sqrt((a[:len(a) // 48 * 48].astype(np.float32).reshape(-1, 48) ** 2).mean(1))  # 1ms
    ex, er = env(x), env(r)
    n = min(len(ex), len(er)) - 200
    lag = max(range(-100, 101), key=lambda k: float(np.dot(er[100:n], ex[100 - k:n - k])))  # ms
    shift = lag * 48
    x = np.concatenate([np.zeros(shift, np.int16), x]) if shift > 0 else x[-shift:]
    with wave.open(str(wav), "wb") as w:
        w.setparams(params)
        w.writeframes(np.pad(x, (0, max(0, len(r) - len(x))))[:len(r)].tobytes())


def duration(path):
    out = subprocess.run([M.ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def transcribe(wav, prompt=""):
    """Word-level timestamps: [(start, end, word), ...]."""
    from faster_whisper import WhisperModel
    model = WhisperModel(ASR_MODEL, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(wav), language="en", word_timestamps=True, vad_filter=True,
                                   initial_prompt=prompt[:800] or None, beam_size=5,
                                   # deterministic: no random-temperature retries, and each
                                   # segment decoded fresh so one mishearing can't loop on
                                   temperature=0.0, condition_on_previous_text=False)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append((float(w.start), float(w.end), w.word.strip()))
    return words


_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen " \
        "sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _num_words(n):
    """Small number-to-words so '76' in the transcript matches 'seventy-six' in the script."""
    if n < 20:
        return [_ONES[n]]
    if n < 100:
        return [_TENS[n // 10]] + ([_ONES[n % 10]] if n % 10 else [])
    if n < 1000:
        return [_ONES[n // 100], "hundred"] + (_num_words(n % 100) if n % 100 else [])
    if 1900 <= n <= 2099:  # years read as "nineteen forty-six", "twenty twenty-two"
        hi, lo = divmod(n, 100)
        return _num_words(hi) + (["hundred"] if lo == 0 else (["oh"] + _num_words(lo) if lo < 10 else _num_words(lo)))
    if n < 1_000_000:
        return _num_words(n // 1000) + ["thousand"] + (_num_words(n % 1000) if n % 1000 else [])
    return [str(n)]


def tokens(text):
    out = []
    for raw in re.findall(r"[A-Za-z]+|\d[\d,]*(?:\.\d+)?%?", text.replace("-", " ")):
        t = raw.lower().replace(",", "")
        pct = t.endswith("%")
        t = t.rstrip("%")
        if re.fullmatch(r"\d+", t):
            out += _num_words(int(t))
        elif t:
            out.append(t)
        if pct:
            out.append("percent")
    return out


def align(lines, words):
    """Map each script line to (start, end) seconds in the recording.

    Script tokens are matched to transcript tokens with difflib; matched tokens become
    time anchors, and unmatched ones are interpolated between neighbours by position.
    Returns [{start, end, matched}] per line, where matched is the share of that line's
    words found in the recording (low = probably skipped or ad-libbed).
    """
    script_toks, owner = [], []
    for li, text in enumerate(lines):
        for t in tokens(text):
            script_toks.append(t)
            owner.append(li)
    asr_toks, asr_time = [], []
    for s, e, w in words:
        for t in tokens(w):
            asr_toks.append(t)
            asr_time.append((s, e))
    n = len(script_toks)
    times = [None] * n
    sm = difflib.SequenceMatcher(a=script_toks, b=asr_toks, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            times[a + k] = asr_time[b + k]
    matched_flags = [t is not None for t in times]
    anchors = [i for i, t in enumerate(times) if t is not None]
    if not anchors:
        raise SystemExit("Couldn't match the recording to the script. Is it the right script?")
    total_end = words[-1][1] if words else 0.0
    for i in range(n):
        if times[i] is not None:
            continue
        prev = max((a for a in anchors if a < i), default=None)
        nxt = min((a for a in anchors if a > i), default=None)
        if prev is None:
            t = times[nxt][0] * (i + 1) / (nxt + 1)
        elif nxt is None:
            t = times[prev][1] + (total_end - times[prev][1]) * (i - prev) / max(1, n - prev)
        else:
            f = (i - prev) / (nxt - prev)
            t = times[prev][1] + (times[nxt][0] - times[prev][1]) * f
        times[i] = (t, t)
    out = []
    for li in range(len(lines)):
        idx = [i for i, o in enumerate(owner) if o == li]
        if not idx:
            out.append({"start": out[-1]["end"] if out else 0.0, "end": out[-1]["end"] if out else 0.0, "matched": 0.0})
            continue
        out.append({"start": round(times[idx[0]][0], 3), "end": round(times[idx[-1]][1], 3),
                    "matched": round(sum(matched_flags[i] for i in idx) / len(idx), 2),
                    "heard_first": matched_flags[idx[0]]})
    # keep cues monotonic
    for k in range(1, len(out)):
        out[k]["start"] = max(out[k]["start"], out[k - 1]["start"] + 0.05)
        out[k]["end"] = max(out[k]["end"], out[k]["start"] + 0.3)
    return out


def _energy_db(wav):
    """10 ms frame loudness in dB relative to the loudest frame."""
    import wave
    import numpy as np
    with wave.open(str(wav)) as w:
        rate, n = w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32)
    hop = rate // 100
    frames = x[: len(x) // hop * hop].reshape(-1, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-9)
    return 20 * np.log10(rms / rms.max()), 0.01


def refine_starts(cues, wav, floor_db=-32.0):
    """Snap each line's start to where speech actually begins.

    Speech recognition can put a line's first word inside the pause before it, or (when it
    mishears a word) well after it. A reader pauses between sentences, so among the speech
    onsets near the detected start we pick the one after the longest pause, with a small
    penalty for distance from the detected time. When the line's first word was heard
    clearly it can still start early (stretched back into the pause) but not much late, so the
    search reaches only 0.4s earlier (a pause inside the previous line can be as long as the
    one before this line)."""
    db, step = _energy_db(wav)
    loud = db > floor_db
    n = len(loud)
    prev_start = -1.0
    for c in cues:
        reach = (0.4, 1.2) if c.pop("heard_first", False) else (1.5, 1.2)
        lo = max(prev_start + 0.8, c["start"] - reach[0], 0.0)
        hi = min(c["start"] + reach[1], c["end"] - 0.2)
        best, best_score = None, None
        quiet = 0
        for i in range(max(0, int(lo / step) - 200), min(n - 5, int(hi / step))):
            if not loud[i]:
                quiet += 1
                continue
            if i * step >= lo and quiet >= 12 and loud[i:i + 5].all():
                score = quiet * step - 0.35 * abs(i * step - c["start"])
                if best_score is None or score > best_score:
                    best, best_score = i, score
            quiet = 0
        if best is not None:
            c["start"] = round(best * step, 3)
        prev_start = c["start"]
    for k in range(1, len(cues)):
        cues[k]["start"] = max(cues[k]["start"], cues[k - 1]["start"] + 0.05)
        cues[k - 1]["end"] = min(cues[k - 1]["end"], cues[k]["start"])
    return cues


def tighten(wav, cues, max_gap=0.5, also=()):
    """Shorten long pauses BETWEEN lines to max_gap (editor-style tightening for short-form
    pacing). Words are untouched and nothing is sped up; only silence inside the gaps is cut,
    with a short crossfade at each cut. Rewrites the wav (and the same spans of each wav in
    `also`) and shifts cue times. Returns seconds removed."""
    db, step = _energy_db(wav)
    cuts = []  # (start_s, end_s) of audio to remove
    for a, b in zip(cues, cues[1:]):
        g0, g1 = a["end"], b["start"]
        if g1 - g0 <= max_gap:
            continue
        # only cut where it's actually quiet: the longest quiet run inside the gap
        i0, i1 = int(g0 / step), int(g1 / step)
        best, run_start = (0, 0), None
        for i in range(i0, i1 + 1):
            quiet = i < i1 and db[i] <= -32
            if quiet and run_start is None:
                run_start = i
            if (not quiet) and run_start is not None:
                if i - run_start > best[1] - best[0]:
                    best = (run_start, i)
                run_start = None
        q0, q1 = best[0] * step, best[1] * step
        excess = (g1 - g0) - max_gap
        removable = (q1 - q0) - 0.2  # keep a little air on each side of the cut
        cut = min(excess, removable)
        if cut > 0.05:
            mid = (q0 + q1) / 2
            cuts.append((mid - cut / 2, mid + cut / 2))
    if not cuts:
        return 0.0
    for path in (wav, *also):
        _cut(path, cuts)
    for c in cues:
        for key in ("start", "end"):
            t = c[key]
            c[key] = round(t - sum(min(c1, t) - c0 for c0, c1 in cuts if t > c0), 3)
    return round(sum(c1 - c0 for c0, c1 in cuts), 2)


def _cut(wav, cuts, fade=0.012):
    """Remove the (start_s, end_s) spans from a wav, with a short crossfade at each cut."""
    import wave
    import numpy as np
    with wave.open(str(wav)) as w:
        rate, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    n_fade = int(fade * rate)
    pieces, pos = [], 0
    for c0, c1 in cuts:
        s0, s1 = int(c0 * rate), int(c1 * rate)
        seg = x[pos:s0].copy()
        if len(seg) > n_fade:
            seg[-n_fade:] *= np.linspace(1, 0, n_fade)
        pieces.append(seg)
        pos = s1
        nxt = x[pos:pos + n_fade]
        if len(nxt) == n_fade:
            x[pos:pos + n_fade] = nxt * np.linspace(0, 1, n_fade)
    pieces.append(x[pos:])
    y = np.clip(np.concatenate(pieces), -32768, 32767).astype(np.int16)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(sw); w.setframerate(rate); w.writeframes(y.tobytes())


def trim_head(wav, cues, keep=0.15, also=()):
    """Cut dead air before the first line down to `keep` seconds, from `wav` and each wav in
    `also`. Shifts the cues."""
    import wave
    lead = cues[0]["start"] - keep if cues else 0.0
    if lead <= 0.05:
        return 0.0
    for path in (wav, *also):
        with wave.open(str(path)) as w:
            params, data = w.getparams(), w.readframes(w.getnframes())
        cut = int(lead * params.framerate) * params.sampwidth * params.nchannels
        with wave.open(str(path), "wb") as w:
            w.setparams(params)
            w.writeframes(data[cut:])
    for c in cues:
        c["start"], c["end"] = round(c["start"] - lead, 3), round(c["end"] - lead, 3)
    return round(lead, 2)


def sync(project_dir, audio_path, max_gap=0.5, polish=True):
    """Clean, transcribe and align a recording; store the result in the storyboard.
    polish=False mixes the plainly denoised voice instead of the studio-cleaned one."""
    project_dir = Path(project_dir)
    sb_path = project_dir / "storyboard.json"
    sb = json.loads(sb_path.read_text())
    media_dir = project_dir / "media"
    src = Path(audio_path)
    dest = media_dir / f"voiceover{src.suffix.lower() or '.m4a'}"
    if src.resolve() != dest.resolve():
        dest.write_bytes(src.read_bytes())
    # leading dead air off first, once, so both copies share the timeline (speech recognition
    # also misses the last sentence when it's left on: its 30s windows shift)
    head_wav = media_dir / "voiceover_src.wav"
    _ff("-i", str(dest), "-vn", "-ac", "1", "-ar", "48000", "-af",
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15", "-c:a", "pcm_s16le", str(head_wav))
    clean_wav = media_dir / "voiceover_clean.wav"
    clean(head_wav, clean_wav)
    mix_wav, eq = media_dir / "voiceover_studio.wav", []
    if polish:
        eq = EN.enhance(head_wav, mix_wav)
        _align_to(mix_wav, clean_wav)
    also = (mix_wav,) if polish else ()
    lines, keys = [], []
    for i, spec in enumerate(sb["scenes"]):
        say = spec.get("say", [])
        for j, text in enumerate([say] if isinstance(say, str) else say):
            lines.append(text)
            keys.append((i, j))
    words = transcribe(clean_wav, prompt=" ".join(lines))
    cues = refine_starts(align(lines, words), clean_wav)
    removed = tighten(clean_wav, cues, max_gap, also) if max_gap else 0.0
    removed += trim_head(clean_wav, cues, also=also)
    sb["voiceover"] = {
        "file": dest.name, "clean": clean_wav.name, "duration": round(duration(clean_wav), 2),
        **({"mix": mix_wav.name, "studio": eq} if polish else {}),
        "cues": [{"scene": i, "line": j, "text": t, **c} for (i, j), t, c in zip(keys, lines, cues)],
        "transcript": " ".join(w for _, _, w in words),
        "pauses_trimmed_s": removed, "max_gap": max_gap,
    }
    sb_path.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
    return sb["voiceover"]
