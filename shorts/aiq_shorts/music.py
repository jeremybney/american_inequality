"""Background music: a different soft, investigative-feeling instrumental for every video.

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

# The house sound is "investigative": a steady pulse with some tension and curiosity, like a
# news-investigation bed. Mysterious or suspenseful, carried by a groove or driving pulse; never
# horror, action, comic, fantasy, or bright and bouncy. No piano (the author's call).
PROFILES = {
    "investigative": {
        "need_any": {"Mysterious", "Suspenseful"},
        "pulse_any": {"Driving", "Grooving", "Suspenseful", "Intense", "Somber"},
        "avoid": {"Eerie", "Unnerving", "Aggressive", "Action", "Epic", "Humorous", "Bouncy",
                  "Mystical", "Bright", "Uplifting", "Ren Faire", "Medieval"},
        # electronica (7), soundtrack (22), cinematic (10, 24); not world (25), jazz (11), rock (19)
        "genres": {"7", "10", "22", "24"},
        "bpm": (70, 130),
    },
}
PROFILE = "investigative"
NO_INSTRUMENTS = ("piano", "organ", "choir", "vocal", "voice", "harpsichord", "celesta", "tuba",
                  "kazoo", "accordion", "bagpipe", "banjo", "harp", "flute", "clarinet", "oboe",
                  "zither", "lute", "santur", "tanpura", "ukulele", "glockenspiel", "trombone", "kora", "sitar")
NOPE = ("christmas", "holiday", "waltz", "medieval", "goblin", "horror", "zombie", "carol",
        "8bit", "8-bit", "chiptune", "dungeon", "chee zee", "video game")


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


def candidates(min_len=110, profile=None):
    p = PROFILES[profile or PROFILE]
    out = []
    for t in catalog():
        feel = {f.strip() for f in (t.get("feel") or "").split(",") if f.strip()}
        try:
            bpm = int(t.get("bpm") or 0)
        except ValueError:
            bpm = 0
        if not (feel & p["need_any"]) or not (feel & p["pulse_any"]) or feel & p["avoid"]:
            continue
        if any(s in (t.get("instruments") or "").lower() for s in NO_INSTRUMENTS):
            continue
        text = f"{t.get('title', '')} {t.get('description', '')}".lower()
        if str(t.get("genre")) not in p["genres"] or any(w in text for w in NOPE):
            continue
        if _seconds(t.get("length")) < min_len or not (p["bpm"][0] <= bpm <= p["bpm"][1]):
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
    keep = cur if (cur and not cur.get("off")) else {}
    sb["music"] = {"title": track["title"], "file": "music.mp3", "start_scene": keep.get("start_scene", 3),
                   "level_db": keep.get("level_db", -38), "feel": track.get("feel", ""),
                   "credit": credit(track)}
    sb["music_credit"] = credit(track)
    sb_path.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
    hist = used()
    hist[slug] = {"title": track["title"], "filename": track["filename"]}
    USED.write_text(json.dumps(hist, indent=2))
    return sb["music"]


def build_bed(project_dir, music, duration, out_wav, start=5.0):
    """Music bed for the whole video: silent until `start` (the start of the scene named by
    `start_scene`, the article card by default), fades in over 2.5s, sits at `level_db` LUFS
    (about 22 dB under a -16 LUFS voice at the default -38), fades out over the last 3s, and
    loops if the track is shorter than the video."""
    src = Path(project_dir) / "media" / music["file"]
    body = max(1.0, duration - start)
    tmp = Path(out_wav).with_name("music_body.wav")
    # pass 1: loop/trim, level, fades. loudnorm scrambles timestamps, so the delay that holds the
    # music back until its scene happens in a separate pass.
    af1 = (f"aloop=loop=-1:size=2147483647,atrim=0:{body:.3f},asetpts=N/SR/TB,"
           f"loudnorm=I=-30:TP=-6:LRA=7,volume={float(music.get('level_db', -38)) + 30:.1f}dB,"
           f"aresample=48000,afade=t=in:st=0:d=2.5,afade=t=out:st={max(0.0, body - 3):.3f}:d=3")
    subprocess.run([M.ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(src), "-ac", "2", "-ar", "48000",
                    "-af", af1, "-t", f"{body:.3f}", str(tmp)], check=True)
    # pass 2: silence until `start`, then the bed, padded to the video's length
    ms = int(round(start * 1000))
    subprocess.run([M.ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(tmp),
                    "-af", f"adelay={ms}|{ms},apad=whole_dur={duration:.3f}", "-t", f"{duration:.3f}",
                    str(out_wav)], check=True)
    return out_wav
