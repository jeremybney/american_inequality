"""The voiceover from the author's ElevenLabs voice (the default for every video).

Each script line is spoken by the author's own ElevenLabs voice (a clone they made from their
recordings) through the text-to-speech "with-timestamps" endpoint, which returns the audio and
the time of every character. Lines are joined with a short pause into one track, and the cue
for each line comes straight from those timestamps, so captions and reveals land exactly with
no speech recognition. The result is stored in storyboard["voiceover"] in the same shape a
synced recording uses, so the engine treats both alike; an uploaded recording (voice.sync)
still overrides it while it matches the script.

Lines are cached by their text and settings in media/tts/, so after a script edit only the
changed lines are regenerated (and billed).

Credentials: ELEVENLABS_API_KEY from the environment. When the key is held as a network
secret instead, the proxy adds it to requests for api.elevenlabs.io, so no header is sent here.
"""
import base64
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from . import media as M

API = "https://api.elevenlabs.io/v1"
CONFIG = Path(__file__).resolve().parent.parent / "assets" / "voice.json"
DEFAULTS = {
    "voice_id": None,
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.5, "similarity_boost": 0.85, "style": 0.15, "use_speaker_boost": True,
                       "speed": 1.0},
    "gap": 0.42,            # pause between lines, seconds (a recording is tightened to 0.5s)
    "lufs": -14.0,          # same loudness as the studio-cleaned recordings
    "pronounce": {},        # spoken form for words the voice misreads: {"MS": "Mississippi"}
}


def config(sb=None):
    """House voice settings (assets/voice.json) with any per-video `tts` overrides."""
    cfg = json.loads(json.dumps(DEFAULTS))
    if CONFIG.exists():
        _merge(cfg, json.loads(CONFIG.read_text()))
    if sb and isinstance(sb.get("tts"), dict):
        _merge(cfg, sb["tts"])
    return cfg


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _merge(a[k], v)
        else:
            a[k] = v


def available():
    """True when a key is in the environment (a network-secret key can't be seen from here,
    so `tts` is still worth trying without one; this only decides the automatic default)."""
    return bool(os.environ.get("ELEVENLABS_API_KEY"))


def _post(path, body):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if os.environ.get("ELEVENLABS_API_KEY"):
        headers["xi-api-key"] = os.environ["ELEVENLABS_API_KEY"]
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        if e.code == 401:
            raise SystemExit("ElevenLabs refused the request (401): no API key reached it. Add "
                             "ELEVENLABS_API_KEY in the environment settings and start a new session.")
        raise SystemExit(f"ElevenLabs error {e.code}: {detail}")


def spoken(text, cfg):
    """The text as the voice should read it (captions keep the original)."""
    import re
    for word, say in cfg.get("pronounce", {}).items():
        text = re.sub(rf"(?<![\w.]){re.escape(word)}(?![\w])", say, text)
    return text


def _ff(*args):
    subprocess.run([M.ffmpeg_exe(), "-y", "-loglevel", "error", *args], check=True)


def line_audio(text, prev, nxt, cfg, cache_dir):
    """(wav path, speech start, speech end) for one line, from cache or ElevenLabs."""
    body = {"text": spoken(text, cfg), "model_id": cfg["model_id"], "voice_settings": cfg["voice_settings"]}
    if prev:
        body["previous_text"] = spoken(prev, cfg)
    if nxt:
        body["next_text"] = spoken(nxt, cfg)
    key = hashlib.sha1(json.dumps([cfg["voice_id"], body], sort_keys=True).encode()).hexdigest()[:16]
    wav, meta = cache_dir / f"{key}.wav", cache_dir / f"{key}.json"
    if not (wav.exists() and meta.exists()):
        r = _post(f"/text-to-speech/{cfg['voice_id']}/with-timestamps?output_format=mp3_44100_128", body)
        mp3 = cache_dir / f"{key}.mp3"
        mp3.write_bytes(base64.b64decode(r["audio_base64"]))
        _ff("-i", str(mp3), "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(wav))
        mp3.unlink()
        al = r.get("alignment") or r.get("normalized_alignment") or {}
        starts = al.get("character_start_times_seconds") or [0.0]
        ends = al.get("character_end_times_seconds") or [_dur(wav)]
        chars = al.get("characters") or []
        # first and last spoken (non-space) character
        idx = [k for k, c in enumerate(chars) if c.strip()] or [0]
        meta.write_text(json.dumps({"start": starts[idx[0]], "end": ends[idx[-1]], "text": text}))
        fresh = True
    else:
        fresh = False
    m = json.loads(meta.read_text())
    return wav, m["start"], m["end"], fresh


def _dur(wav):
    import wave
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def generate(project_dir, voice_id=None, progress=True):
    """Speak every `say` line with the house voice and store the cues in the storyboard."""
    import wave
    project_dir = Path(project_dir)
    sb_path = project_dir / "storyboard.json"
    sb = json.loads(sb_path.read_text())
    cfg = config(sb)
    if voice_id:
        cfg["voice_id"] = voice_id
    if not cfg["voice_id"]:
        raise SystemExit(f"No ElevenLabs voice set: put {{\"voice_id\": \"…\"}} in {CONFIG}")
    media_dir = project_dir / "media"
    cache_dir = media_dir / "tts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    lines, keys = [], []
    for i, spec in enumerate(sb["scenes"]):
        say = spec.get("say", [])
        for j, text in enumerate([say] if isinstance(say, str) else say):
            lines.append(text)
            keys.append((i, j))
    rate, gap = 48000, cfg["gap"]
    pieces, cues, t, made = [], [], 0.15, 0
    for n, text in enumerate(lines):
        wav, s, e, fresh = line_audio(text, lines[n - 1] if n else None,
                                      lines[n + 1] if n + 1 < len(lines) else None, cfg, cache_dir)
        made += fresh
        with wave.open(str(wav)) as w:
            frames = w.readframes(w.getnframes())
        # keep the spoken part plus a breath either side, so the pause between lines is `gap`
        a = max(0, int((s - 0.05) * rate)) * 2
        b = min(len(frames), int((e + 0.12) * rate) * 2)
        seg = frames[a:b]
        cues.append({"start": round(t + (s - a / 2 / rate), 3), "end": round(t + (e - a / 2 / rate), 3),
                     "matched": 1.0})
        pieces.append(seg)
        t += len(seg) / 2 / rate + gap
        pieces.append(b"\x00\x00" * int(gap * rate))
        if progress:
            print(f"  {'new ' if fresh else 'kept'}  {cues[-1]['start']:6.1f}s  {text[:70]}", flush=True)
    raw = media_dir / "voiceover_tts_raw.wav"
    with wave.open(str(raw), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(0.15 * rate) + b"".join(pieces))
    out = media_dir / "voiceover_tts.wav"
    # level it like the studio-cleaned recordings; a linear gain keeps the timing exact
    _ff("-i", str(raw), "-af", f"loudnorm=I={cfg['lufs']}:TP=-1.5:LRA=11:linear=true",
        "-ar", str(rate), "-ac", "1", "-c:a", "pcm_s16le", str(out))
    raw.unlink()
    # drop cached lines no longer in the script
    live = set()
    for n, text in enumerate(lines):
        body = {"text": spoken(text, cfg), "model_id": cfg["model_id"], "voice_settings": cfg["voice_settings"]}
        if n:
            body["previous_text"] = spoken(lines[n - 1], cfg)
        if n + 1 < len(lines):
            body["next_text"] = spoken(lines[n + 1], cfg)
        live.add(hashlib.sha1(json.dumps([cfg["voice_id"], body], sort_keys=True).encode()).hexdigest()[:16])
    for f in cache_dir.iterdir():
        if f.stem not in live:
            f.unlink()
    sb["voiceover"] = {
        "source": "elevenlabs", "voice_id": cfg["voice_id"], "model_id": cfg["model_id"],
        "file": out.name, "clean": out.name, "mix": out.name, "duration": round(_dur(out), 2),
        "cues": [{"scene": i, "line": j, "text": tx, **c} for (i, j), tx, c in zip(keys, lines, cues)],
        "lines_generated": made,
    }
    sb_path.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
    return sb["voiceover"]


def stale(sb):
    """True when the storyboard has no voiceover, or one that no longer matches its script."""
    vo = sb.get("voiceover")
    if not vo or not vo.get("cues"):
        return True
    current = [(i, j, tx) for i, s in enumerate(sb["scenes"])
               for j, tx in enumerate([s.get("say", [])] if isinstance(s.get("say", []), str) else s.get("say", []))]
    return current != [(c["scene"], c["line"], c["text"]) for c in vo["cues"]]
