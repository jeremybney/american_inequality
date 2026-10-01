"""Background music: a different soft, upbeat-ambient instrumental for every video.

Tracks come from Kevin MacLeod's Incompetech library (the same composer the reference
videos use), licensed CC BY 4.0. The credit line is added to the end card, credits.md and
the TikTok caption automatically. A history file keeps any track from repeating across videos.
"""
import hashlib
import json
import random
import subprocess
import urllib.parse
from pathlib import Path

from . import media as M

CATALOG_URL = "https://incompetech.com/music/royalty-free/pieces.json"
FILE_URL = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/{}"
HERE = Path(__file__).resolve().parent.parent
USED = HERE / "assets" / "music_used.json"      # committed: which video used which track
CACHE = HERE / "assets" / ".music_catalog.json"  # not committed

WANT = {"Bright", "Relaxed", "Calming", "Uplifting"}          # the reference videos' feel
AVOID = {"Dark", "Unnerving", "Eerie", "Intense", "Humorous", "Epic", "Mysterious", "Somber",
         "Aggressive", "Action", "Suspenseful", "Mystical", "Driving"}
# Incompetech genre ids: keep contemporary (5), electronica (7), ambient/game (13), pop (16),
# acoustic (12) and soundtrack-ish (22); leave out classical (4), holiday (9), jazz (11),
# oldies rock (19) and period/world (24, 25), which pull attention from the voice.
GENRES = {"5", "7", "12", "13", "16", "22"}
NOPE = ("christmas", "holiday", "waltz", "drinking", "medieval", "carol", "sock hop", "canon in d",
        "round the mountain")
# Tal Roded's signature tracks: leave them to him so these videos have their own sound
RESERVED = {"Life of Riley", "Inspired"}
SILLY = ("Tuba", "Kazoo", "Accordion", "Bagpipe", "Banjo", "Trombone", "Harmonica", "Theremin",
         "Bassoon", "Vocals", "Voice", "Choir", "Organ")


def credit(track):
    return (f"Music: “{track['title']}” Kevin MacLeod (incompetech.com), "
            "licensed under CC BY 4.0")


def _seconds(length):
    try:
        h, m, s = (int(x) for x in str(length).split(":"))
        return h * 3600 + m * 60 + s
    except ValueError:
        return 0


def catalog():
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    data = M.http_json(CATALOG_URL)
    CACHE.write_text(json.dumps(data))
    return data


def candidates(min_len=110):
    out = []
    for t in catalog():
        feel = {f.strip() for f in (t.get("feel") or "").split(",") if f.strip()}
        try:
            bpm = int(t.get("bpm") or 0)
        except ValueError:
            bpm = 0
        if len(feel & WANT) < 2 or feel & AVOID:
            continue
        if any(s.lower() in (t.get("instruments") or "").lower() for s in SILLY):
            continue
        text = f"{t.get('title', '')} {t.get('description', '')}".lower()
        if str(t.get("genre")) not in GENRES or any(w in text for w in NOPE) or t["title"] in RESERVED:
            continue
        if _seconds(t.get("length")) < min_len or not (78 <= bpm <= 128):
            continue
        out.append(t)
    return out


def used():
    return json.loads(USED.read_text()) if USED.exists() else {}


def choose(slug, title=None):
    """Pick a track for this video: a fresh one (not used by any other video), stable per slug."""
    hist = used()
    pool = candidates()
    if title:
        match = [t for t in catalog() if t["title"].lower() == title.lower()]
        if not match:
            raise SystemExit(f"No Incompetech track titled {title!r}")
        return match[0]
    taken = {v["title"] for k, v in hist.items() if k != slug}
    fresh = [t for t in pool if t["title"] not in taken] or pool
    rng = random.Random(int(hashlib.sha1(slug.encode()).hexdigest(), 16))
    return rng.choice(sorted(fresh, key=lambda t: t["title"]))


def assign(project_dir, title=None, reroll=False):
    """Store the chosen track in the storyboard, download it, and log it as used."""
    project_dir = Path(project_dir)
    slug = project_dir.name
    sb_path = project_dir / "storyboard.json"
    sb = json.loads(sb_path.read_text())
    cur = sb.get("music")
    if cur and not title and not reroll:
        track = next((t for t in catalog() if t["title"] == cur["title"]), None) or cur
    else:
        if reroll and cur and not title:  # skip the current one too
            hist = used()
            hist.setdefault(f"{slug}~skipped~{cur['title']}", {"title": cur["title"]})
            USED.write_text(json.dumps(hist, indent=2))
        track = choose(slug, title)
    dest = project_dir / "media" / "music.mp3"
    if not dest.exists() or not cur or cur.get("title") != track["title"]:
        M.download(FILE_URL.format(urllib.parse.quote(track["filename"])), dest)
    sb["music"] = {"title": track["title"], "file": "music.mp3", "start": (cur or {}).get("start", 5.0),
                   "level_db": (cur or {}).get("level_db", -30), "feel": track.get("feel", ""),
                   "credit": credit(track)}
    sb["music_credit"] = credit(track)
    sb_path.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
    hist = used()
    hist[slug] = {"title": track["title"], "filename": track["filename"]}
    USED.write_text(json.dumps(hist, indent=2))
    return sb["music"]


def build_bed(project_dir, music, duration, out_wav):
    """Music bed for the whole video: silent until `start`, fades in over 2.5s, sits at
    `level_db` LUFS (well under a -14 to -16 LUFS voice), fades out over the last 3s,
    and loops if the track is shorter than the video."""
    src = Path(project_dir) / "media" / music["file"]
    start = float(music.get("start", 5.0))
    body = max(1.0, duration - start)
    af = (f"aloop=loop=-1:size=2147483647,atrim=0:{body:.3f},asetpts=N/SR/TB,"
          f"loudnorm=I={music.get('level_db', -30)}:TP=-6:LRA=7,"
          f"afade=t=in:st=0:d=2.5,afade=t=out:st={max(0.0, body - 3):.3f}:d=3,"
          f"adelay={int(start * 1000)}|{int(start * 1000)},apad,atrim=0:{duration:.3f}")
    subprocess.run([M.ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(src), "-ac", "2", "-ar", "48000",
                    "-af", af, str(out_wav)], check=True)
    return out_wav
