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

# Earlier house sounds, kept for reference: "investigative" (mysterious or suspenseful over a
# pulse, no piano) and "pulse" (the same mood with a steadier groove). The author retired both
# as too ominous; see "reporting" below.
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
# The house sound since Oct 2026, modeled on the author's reference videos: the same
# investigative mood but carried by a steady groove (94-125 BPM, electronic or cinematic
# percussion), loud enough to feel (about 10 dB under the voice) and starting on frame one.
PROFILES["pulse"] = {
    "need_any": {"Mysterious", "Suspenseful", "Intense", "Dark"},
    "pulse_any": {"Driving", "Grooving"},
    "avoid": PROFILES["investigative"]["avoid"] | {"Calming"},
    "genres": {"7", "10", "22", "24"},
    "bpm": (90, 130),
}
# The house sound since Oct 4, 2026: "reporting". The author found the pulse and investigative
# beds too ominous and pointed to informational explainers (Zohran Mamdani's and Emma Camp's
# grocery-store videos) as the model: a light, steady groove under a voice that's explaining,
# bright or calm rather than dark, with electric piano, plucks, light drums or strings.
# Piano and strings are allowed here; party funk, dance and rave tracks are not.
PROFILES["reporting"] = {
    "need_any": {"Bright", "Uplifting", "Calming", "Relaxed"},
    "pulse_any": {"Grooving", "Driving", "Uplifting", "Bright"},
    "avoid": {"Dark", "Eerie", "Unnerving", "Mysterious", "Suspenseful", "Somber", "Aggressive", "Epic",
              "Action", "Humorous", "Mystical", "Bouncy", "Intense", "Ren Faire", "Medieval"},
    # contemporary (5), electronica (7), soundtrack (22), funk (8, filtered by title below)
    "genres": {"5", "7", "8", "22"},
    "bpm": (90, 130),
    "allow_instruments": ("piano", "harp"),        # strings and (electric) piano are fine
    "nope": ("funk", "dance", "rave", "raving", "party", "disco", "elevator", "miami"),
}
PROFILE = "reporting"
START_SCENE = 1      # the music starts on the first frame
LEVEL_DB = -21.0     # LUFS; the author asked twice for louder music (voice about 4-5 dB over it)
NO_INSTRUMENTS = ("piano", "organ", "choir", "vocal", "voice", "harpsichord", "celesta", "tuba",
                  "kazoo", "accordion", "bagpipe", "banjo", "harp", "flute", "clarinet", "oboe",
                  "zither", "lute", "santur", "tanpura", "ukulele", "glockenspiel", "trombone", "kora", "sitar",
                  "erhu", "pipa", "yangqin", "koto", "shamisen", "didgeridoo")
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


def candidates(min_len=90, profile=None):
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
        banned = [x for x in NO_INSTRUMENTS if x not in p.get("allow_instruments", ())]
        if any(x in (t.get("instruments") or "").lower() for x in banned):
            continue
        text = f"{t.get('title', '')} {t.get('description', '')}".lower()
        if str(t.get("genre")) not in p["genres"] or any(w in text for w in NOPE + p.get("nope", ())):
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
    sb["music"] = {"title": track["title"], "file": "music.mp3", "start_scene": keep.get("start_scene", START_SCENE),
                   "level_db": keep.get("level_db", LEVEL_DB), "feel": track.get("feel", ""),
                   "credit": credit(track)}
    sb["music_credit"] = credit(track)
    sb_path.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
    hist = used()
    hist[slug] = {"title": track["title"], "filename": track["filename"]}
    USED.write_text(json.dumps(hist, indent=2))
    return sb["music"]


def build_bed(project_dir, music, duration, out_wav, start=0.0):
    """Music bed for the whole video: starts at `start` (the first frame by default; a later
    `start_scene` delays it), sits at `level_db` LUFS (about 12 dB under a -14 LUFS voice at the
    default -26), fades out over the last 3s, and loops if the track is shorter than the video.
    From frame one it comes in at full level after a 0.3s fade; a delayed start fades over 2.5s."""
    src = Path(project_dir) / "media" / music["file"]
    body = max(1.0, duration - start)
    tmp = Path(out_wav).with_name("music_body.wav")
    # pass 1: loop/trim, level, fades. loudnorm scrambles timestamps, so the delay that holds the
    # music back until its scene happens in a separate pass.
    af1 = (f"aloop=loop=-1:size=2147483647,atrim=0:{body:.3f},asetpts=N/SR/TB,"
           f"loudnorm=I={float(music.get('level_db', LEVEL_DB)):.1f}:TP=-2:LRA=7,"
           f"aresample=48000,afade=t=in:st=0:d={0.3 if start < 0.5 else 2.5},"
           f"afade=t=out:st={max(0.0, body - 3):.3f}:d=3")
    subprocess.run([M.ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(src), "-ac", "2", "-ar", "48000",
                    "-af", af1, "-t", f"{body:.3f}", str(tmp)], check=True)
    # pass 2: silence until `start`, then the bed, padded to the video's length
    ms = int(round(start * 1000))
    subprocess.run([M.ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(tmp),
                    "-af", f"adelay={ms}|{ms},apad=whole_dur={duration:.3f}", "-t", f"{duration:.3f}",
                    str(out_wav)], check=True)
    return out_wav
