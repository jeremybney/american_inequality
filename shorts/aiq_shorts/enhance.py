"""Studio cleanup for the author's voiceover.

A voice memo recorded in a normal room sounds hollow next to the music: the walls add a
short echo after every word, and many phone recordings (especially compressed ones) carry
almost nothing above 5 kHz, so the voice is muffled and sounds far away. Plain EQ and
denoising can't fix that (the old `afftdn` pass actually removed more of the highs). So:

1. DeepFilterNet 3 (a small neural speech enhancer, ~4s per minute of audio on CPU) strips
   the room echo and background noise. It only removes sound; it never synthesizes speech,
   and its output is sample-for-sample the same length, so the caption timing holds.
2. The tone is measured per recording and corrected toward a close-mic broadcast voice:
   boom and boxiness cut, presence and air lifted, by at most a few dB per band, and nothing
   where it's already right. A recording with no highs at all also gets a harmonic exciter,
   which rebuilds crispness from the voice's own 3-5 kHz content.
3. De-ess; a gentle expander that shortens whatever echo tail is left after each word (it
   only turns the quiet parts down, never cuts them); gentle compression so every word sits
   at the same level; -14 LUFS with a peak limiter.

Without DeepFilterNet installed the tone and dynamics still run, over a light denoise.
"""
import subprocess
import sys
import types
import urllib.request
import wave
from pathlib import Path

import numpy as np

from . import media as M

RATE = 48000
MODEL_URL = "https://raw.githubusercontent.com/Rikorose/DeepFilterNet/main/models/DeepFilterNet3.zip"
MODEL_DIR = Path.home() / ".cache" / "DeepFilterNet"

# band (Hz): (filter, target dB relative to the whole voice, min gain, max gain).
# Targets are a close, clear spoken voice (a good earbud or lav mic in a quiet room).
TARGETS = {
    (60, 150): ("lowshelf=f=120", -9.5, -4.0, 1.5),
    (150, 300): ("equalizer=f=220:t=q:w=1.0", -8.0, -4.0, 0.0),
    (300, 600): ("equalizer=f=450:t=q:w=1.2", -7.0, -4.0, 0.0),
    (2500, 5000): ("equalizer=f=3500:t=q:w=0.9", -14.5, 0.0, 7.0),
    (5000, 8000): ("highshelf=f=5500", -18.0, 0.0, 9.0),
    (8000, 12000): ("highshelf=f=10000", -24.0, 0.0, 6.0),
}
DULL_DB = -28.0  # 5-8 kHz this far under the whole voice = muffled; add the exciter
SPEECH_DB = -12.0  # loud speech frames are set here before the dynamics, so thresholds mean the same thing
DYNAMICS = ("deesser=i=0.4:m=0.5:f=0.5,"
            "agate=threshold=0.025:ratio=2.5:range=0.2:attack=4:release=110:knee=3,"
            "acompressor=threshold=-18dB:ratio=2.5:attack=8:release=120:knee=4")
LUFS, PEAK = -14.0, 0.79  # TikTok loudness; limiter ceiling (-2 dBFS, so AAC encoding stays under -1 dBTP)


def _ff(*args):
    subprocess.run([M.ffmpeg_exe(), "-loglevel", "error", "-y", *args], check=True)


def read_wav(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def write_wav(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def _frame_db(x, n=480):
    fr = x[:len(x) // n * n].reshape(-1, n)
    return 10 * np.log10((fr ** 2).mean(1) + 1e-12)


def balance(x):
    """Each TARGETS band's level relative to the whole voice (dB), over the louder (speech) frames."""
    n = 960
    fr = x[:len(x) // n * n].reshape(-1, n)
    db = _frame_db(x, n)
    sp = fr[db > np.percentile(db, 60)].ravel()[:RATE * 40]
    spec = np.abs(np.fft.rfft(sp * np.hanning(len(sp)))) ** 2
    f = np.fft.rfftfreq(len(sp), 1 / RATE)
    band = lambda lo, hi: 10 * np.log10(spec[(f >= lo) & (f < hi)].sum() + 1e-12)
    total = band(60, 12000)
    return {k: band(*k) - total for k in TARGETS}


# --- 1. neural echo and noise removal -------------------------------------------------------
_df = None


def _load_df():
    """DeepFilterNet 3, or None if it isn't installed."""
    global _df
    if _df is not None:
        return _df or None
    try:
        import torchaudio
        if not hasattr(torchaudio, "backend"):  # deepfilternet 0.5 imports a module newer torchaudio dropped
            common = types.ModuleType("torchaudio.backend.common")
            common.AudioMetaData = type("AudioMetaData", (), {})
            backend = types.ModuleType("torchaudio.backend")
            backend.common = common
            sys.modules.update({"torchaudio.backend": backend, "torchaudio.backend.common": common})
        from df.enhance import enhance, init_df
    except ImportError:
        _df = False
        return None
    model_dir = MODEL_DIR / "DeepFilterNet3"
    if not (model_dir / "config.ini").exists():  # its own downloader uses a github URL some networks block
        import io
        import zipfile
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(MODEL_URL, timeout=60) as r:
            zipfile.ZipFile(io.BytesIO(r.read())).extractall(MODEL_DIR)
    model, state, _ = init_df(str(model_dir), log_level="ERROR")
    _df = (model, state, enhance)
    return _df


def dereverb(x, atten_db=40.0):
    """Remove room echo and noise. atten_db caps how far the gaps between words are pulled
    down, so they sound quiet rather than gated. Returns None if DeepFilterNet isn't installed."""
    df = _load_df()
    if not df:
        return None
    import torch
    model, state, enhance = df
    y = enhance(model, state, torch.from_numpy(x.copy())[None], atten_lim_db=atten_db).numpy()[0]
    return y[:len(x)]


# --- 2-3. tone and dynamics -----------------------------------------------------------------
def _run_chain(x, af, tmp):
    write_wav(tmp / "in.wav", x)
    _ff("-i", str(tmp / "in.wav"), "-af", f"{af},aresample={RATE}", "-ac", "1", "-ar", str(RATE),
        str(tmp / "out.wav"))
    y = read_wav(tmp / "out.wav")
    return np.pad(y, (0, max(0, len(x) - len(y))))[:len(x)]  # keep the timeline sample-exact


def tone_chain(x, tmp):
    """Measure, EQ toward TARGETS, measure again and correct what's left. Returns (filters, notes)."""
    pre = ["highpass=f=80"]
    notes = []
    if balance(x)[(5000, 8000)] < DULL_DB:
        pre.append("aexciter=amount=2.5:drive=6:blend=0:freq=3000:ceil=14000")
        notes.append("exciter (recording had almost no highs)")
    gains = {k: 0.0 for k in TARGETS}
    for _ in range(2):
        eq = [f"{TARGETS[k][0]}:g={g:.1f}" for k, g in gains.items() if abs(g) >= 0.5]
        bal = balance(_run_chain(x, ",".join(pre + eq), tmp))
        for k, (_, target, lo, hi) in TARGETS.items():
            gains[k] = round(min(hi, max(lo, gains[k] + target - bal[k])), 1)
    eq = [f"{TARGETS[k][0]}:g={g:.1f}" for k, g in gains.items() if abs(g) >= 0.5]
    notes += [f"{k[0]}-{k[1]} Hz {g:+.1f} dB" for k, g in gains.items() if abs(g) >= 0.5]
    return ",".join(pre + eq), notes


def loudness(x, tmp):
    """Integrated loudness (LUFS) of a signal."""
    import json
    write_wav(tmp / "in.wav", x)
    err = subprocess.run([M.ffmpeg_exe(), "-hide_banner", "-i", str(tmp / "in.wav"), "-af",
                          "loudnorm=print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(json.loads(err[err.rindex("{"):])["input_i"])


def decode(src, out_wav):
    """Any audio/video file -> 48 kHz mono wav (the timeline every copy of the voice shares)."""
    _ff("-i", str(src), "-vn", "-ac", "1", "-ar", str(RATE), "-c:a", "pcm_s16le", str(out_wav))
    return out_wav


def enhance(src, out_wav, neural=True):
    """Studio-clean a recording. Output has exactly as many samples as `decode(src)`.
    Returns a list of notes describing what was done."""
    out_wav = Path(out_wav)
    tmp = out_wav.parent / f".{out_wav.stem}_tmp"
    tmp.mkdir(exist_ok=True)
    try:
        x = read_wav(decode(src, tmp / "src.wav"))
        y = dereverb(x) if neural else None
        notes = ["room echo + noise removed (DeepFilterNet 3)"] if y is not None else []
        if y is None:
            if neural:
                notes.append("DeepFilterNet not installed (pip install deepfilternet): light denoise only")
            y = _run_chain(x, "afftdn=nf=-30", tmp)
        y = y * 10 ** ((SPEECH_DB - np.percentile(_frame_db(y), 95)) / 20)
        tone, tone_notes = tone_chain(y, tmp)
        z = _run_chain(y, f"{tone},{DYNAMICS}", tmp)
        # a fixed gain to the target loudness (loudnorm's dynamic mode would lift the room
        # tone back up between words), then a limiter catches the peaks
        z = z * 10 ** ((LUFS - loudness(z, tmp)) / 20)
        write_wav(out_wav, _run_chain(z, f"alimiter=limit={PEAK}:attack=3:release=60:level=disabled", tmp))
        return notes + tone_notes
    finally:
        for p in tmp.glob("*"):
            p.unlink()
        tmp.rmdir()
