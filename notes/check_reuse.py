"""Block any visual that was already used in the last 6 months.

Rule (from Jeremy): never reuse a map or chart within 6 months of first posting it,
whether it first appeared in a note or in an article.

How: every image gets a perceptual fingerprint (difference hash), so a chart counts as
"the same" even after resizing or re-encoding. Compared against:
  1. images in Jeremy's own notes and articles from the last 183 days (cached in
     data/visual_index.json, refreshed incrementally from Substack's public API)
  2. every other note in notes/calendar/*.json scheduled within 183 days of it

Usage:  python3 check_reuse.py            # check all upcoming notes, exit 1 on any repeat
        python3 check_reuse.py --refresh  # also re-scan Substack for newly published images
"""
import argparse
import io
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "data" / "visual_index.json"
CONFIG = json.loads((ROOT / "config.json").read_text())
WINDOW = timedelta(days=183)
THRESHOLD = 10          # bits different out of 256; lower = stricter "same image"
UA = {"User-Agent": "Mozilla/5.0"}


def dhash(img: Image.Image, size=16) -> int:
    g = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(g.get_flattened_data()) if hasattr(g, "get_flattened_data") else list(g.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (px[r * (size + 1) + c] > px[r * (size + 1) + c + 1])
    return bits


def hamming(a, b):
    return bin(a ^ b).count("1")


def hash_url(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    return dhash(Image.open(io.BytesIO(r.content)))


def refresh_index():
    idx = json.loads(INDEX.read_text()) if INDEX.exists() else {}
    cutoff = datetime.now(timezone.utc) - WINDOW
    s = requests.Session()
    s.headers.update(UA)
    # notes
    cur, uid = None, CONFIG["substack_user_id"]
    for _ in range(40):
        r = s.get(f"https://substack.com/api/v1/reader/feed/profile/{uid}" + (f"?cursor={cur}" if cur else ""), timeout=60)
        if r.status_code != 200:
            break
        j = r.json()
        stop = False
        for it in j.get("items", []):
            c = it.get("comment") or {}
            if it.get("type") != "comment" or c.get("user_id") != uid:
                continue
            d = c["date"]
            if datetime.fromisoformat(d.replace("Z", "+00:00")) < cutoff:
                stop = True
                continue
            for a in c.get("attachments") or []:
                u = a.get("imageUrl")
                if a.get("type") == "image" and u and u not in idx:
                    try:
                        idx[u] = {"date": d, "where": f"note c-{c['id']}", "hash": hash_url(u)}
                    except Exception:
                        pass
        cur = j.get("nextCursor")
        if stop or not cur:
            break
        time.sleep(1.2)
    # articles
    pub = CONFIG["publication"]
    cur = None
    for _ in range(10):
        r = s.get(f"https://{pub}.substack.com/api/v1/archive" + (f"?cursor={cur}" if cur else ""), timeout=60)
        if r.status_code != 200:
            break
        j = r.json()
        posts = j.get("posts", [])
        old = False
        for p in posts:
            if datetime.fromisoformat(p["post_date"].replace("Z", "+00:00")) < cutoff:
                old = True
                continue
            body = s.get(f"https://{pub}.substack.com/api/v1/posts/{p['slug']}", timeout=60).json().get("body_html") or ""
            for u in dict.fromkeys(re.findall(r'<img[^>]+src="([^"]+)"', body)):
                if u not in idx:
                    try:
                        idx[u] = {"date": p["post_date"], "where": f"article {p['slug']}", "hash": hash_url(u)}
                    except Exception:
                        pass
            time.sleep(0.8)
        cur = j.get("nextCursor")
        if old or not cur:
            break
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(idx, indent=1))
    return idx


def calendar_entries():
    out = []
    for f in sorted((ROOT / "calendar").glob("*.json")):
        if f.name == "backlog.json":
            continue
        for n in json.loads(f.read_text()):
            if n.get("replaced_by") or (n.get("status") or "").lower() in ("skip", "replaced"):
                continue
            out.append(n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--include-past", action="store_true", help="also check notes already past")
    a = ap.parse_args()
    idx = refresh_index() if a.refresh or not INDEX.exists() else json.loads(INDEX.read_text())
    now = datetime.now(timezone.utc)
    notes = calendar_entries()
    for n in notes:
        p = ROOT / n["chart"]
        n["_hash"] = dhash(Image.open(p)) if p.exists() else None
        n["_t"] = datetime.fromisoformat(n["scheduled_et"])
    problems = []
    for n in notes:
        if n["_hash"] is None:
            problems.append(f"{n['id']}: chart file missing ({n['chart']})")
            continue
        if n["_t"] < now and not a.include_past:
            continue
        for u, v in idx.items():
            t = datetime.fromisoformat(v["date"].replace("Z", "+00:00"))
            if timedelta(0) <= n["_t"] - t <= WINDOW and hamming(n["_hash"], v["hash"]) <= THRESHOLD:
                problems.append(f"{n['id']} ({n['chart']}) repeats an image from {v['where']} on {v['date'][:10]}")
        for m in notes:
            if m is n or m["_hash"] is None or m["_t"] >= n["_t"]:
                continue
            if n["_t"] - m["_t"] <= WINDOW and (m["chart"] == n["chart"] or hamming(n["_hash"], m["_hash"]) <= THRESHOLD):
                problems.append(f"{n['id']} ({n['chart']}) repeats {m['id']} scheduled {m['scheduled_et'][:10]}")
    for p in problems:
        print("REUSE:", p)
    print(f"checked {sum(1 for n in notes if a.include_past or n['_t'] >= now)} notes against {len(idx)} published images: "
          f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
