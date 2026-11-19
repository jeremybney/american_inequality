"""Cross-post the calendar to other platforms at each note's scheduled time (X and Bluesky; Threads next).

Runs every 15 minutes from GitHub Actions (these APIs work from cloud servers, unlike Substack).
Reads the same calendar as the Substack poster, including Jeremy's Google Sheet edits:
  - Status Scheduled/Approved posts; Hold/Skip/Replaced never does
  - "X text" column (or x_text in the repo calendar) is used on X; otherwise the note text if it
    fits in 280 characters; otherwise the note is skipped on X with an Error so nothing gets cut off
  - Substack mentions @[Name](id) become X handles from config.json "x_handles", or plain names
  - Bluesky (300-character limit): the note with plain names if it fits, otherwise the X version
    with X handles turned back into names, otherwise skipped with an Error
Posts at most one note per platform per run, only within 3 hours of its time, and logs every outcome
to state/social.json so nothing posts twice.

Usage:
  python social.py --post-due          # what the scheduled job runs
  python social.py --dry-run           # show what would post on X now and next
  python social.py --verify x          # check keys + chart upload; publishes nothing
  python social.py --test-post x       # publish ONE test post (only when asked)
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

ET = ZoneInfo("America/New_York")
STATE = ROOT / "state" / "social.json"
CONFIG = json.loads((ROOT / "config.json").read_text())
GRACE = timedelta(hours=3)
POSTABLE = {"scheduled", "approved"}
X_LIMIT = 280
BSKY_LIMIT = 300
TEST_CHART = ROOT / "charts" / "2026-11-30" / "real_wages_1973.png"
MENTION = re.compile(r"@\[([^\]]+)\]\((\d+)\)")


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(st):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1, sort_keys=True))


def x_text(n):
    """Text for X, or (None, reason) if it can't be posted without cutting it off."""
    if n.get("x_text"):
        t = n["x_text"]
    else:
        handles = CONFIG.get("x_handles", {})
        t = MENTION.sub(lambda m: f"@{handles[m.group(2)]}" if m.group(2) in handles else m.group(1), n["text"])
    if len(t) > X_LIMIT:
        return None, f"{len(t)} characters; add a shorter version in the Sheet's X text column"
    return t, None


def bsky_text(n):
    """Text for Bluesky, or (None, reason)."""
    t = MENTION.sub(lambda m: m.group(1), n["text"])
    if len(t) <= BSKY_LIMIT:
        return t, None
    if n.get("x_text"):
        rev = {h: nm for nm, h in ((m.group(1), CONFIG["x_handles"].get(m.group(2)))
                                   for m in MENTION.finditer(n["text"])) if h}
        t2 = n["x_text"]
        for h, nm in rev.items():
            t2 = t2.replace(f"@{h}", nm)
        if len(t2) <= BSKY_LIMIT:
            return t2, None
    return None, f"{len(t)} characters; add a shorter version in the Sheet's X text column"


def alt_text(n):
    first = re.sub(MENTION, lambda m: m.group(1), n["text"]).split("\n")[0]
    return f"Chart: {first}"[:1000]


def calendar():
    import post_due
    return post_due.merged_calendar()


def due(notes, done, now):
    out = []
    for n in notes.values():
        if n["id"] in done or (n.get("status") or "").lower() not in POSTABLE:
            continue
        if not n.get("text") or not n.get("scheduled_et"):
            continue
        t = datetime.fromisoformat(n["scheduled_et"])
        if t <= now <= t + GRACE:
            out.append((t, n))
        elif now > t + GRACE and t > now - timedelta(days=2):
            done[n["id"]] = {"status": "Missed", "at": now.isoformat()}
    return [n for _, n in sorted(out, key=lambda x: x[0])]


def chart_path(n):
    c = n.get("chart")
    return None if not c else (c if c.startswith("http") else str(ROOT / c))


def _poster(platform):
    if platform == "x":
        from aiq_notes import xpost
        return x_text, xpost.post
    from aiq_notes import bskypost
    return bsky_text, bskypost.post


def post_one(platform, n, done, now):
    pick, send = _poster(platform)
    text, why = pick(n)
    if not text:
        done[n["id"]] = {"status": "Error", "at": now.isoformat(), "error": why}
        print(f"{platform} skip {n['id']}: {why}")
        return
    try:
        res = send(text, chart_path(n), alt_text(n))
        done[n["id"]] = {"status": "Posted", "at": now.isoformat(), **res}
        print(f"{platform} posted {n['id']}: {res}")
    except Exception as e:
        done[n["id"]] = {"status": "Error", "at": now.isoformat(), "error": str(e)[:500]}
        print(f"{platform} ERROR {n['id']}: {e}")


PLATFORMS = {"x": "X_API_KEY", "bsky": "BLUESKY_APP_PASSWORD"}   # a platform runs only if its secret is present


def post_due(dry=False):
    import os
    if CONFIG.get("paused"):
        print("paused in config.json")
        return
    now = datetime.now(ET)
    st = load_state()
    notes = calendar()
    for platform, secret in PLATFORMS.items():
        if CONFIG.get(f"{platform}_paused") or not os.environ.get(secret) and not dry:
            print(f"{platform}: skipped (paused or no credentials)")
            continue
        done = st.setdefault(platform, {})
        queue = due(notes, done, now)
        pick = x_text if platform == "x" else bsky_text
        if dry:
            nxt = sorted((n for n in notes.values() if n["id"] not in done
                          and (n.get("status") or "").lower() in POSTABLE
                          and n.get("scheduled_et", "") >= now.isoformat()), key=lambda n: n["scheduled_et"])[:5]
            print(f"{platform} due now:", [n["id"] for n in queue])
            for n in nxt:
                t, why = pick(n)
                print(f"{platform} next:", n["id"], n["scheduled_et"], f"{len(t)} chars" if t else f"BLOCKED ({why})")
            continue
        if queue:
            post_one(platform, queue[0], done, now)
        else:
            print(f"{platform}: nothing due")
    if not dry:
        save_state(st)


def verify_x():
    from aiq_notes import xpost
    me = xpost.whoami()
    print(f"OK: keys work for @{me['username']} ({me['name']}, id {me['id']})")
    mid = xpost.upload_image(str(TEST_CHART), alt="Line chart of real hourly wages for rank-and-file workers since 1964.")
    print(f"OK: chart upload works (media id {mid}). Nothing was posted.")


def verify_bsky():
    from aiq_notes import bskypost
    s = bskypost.session()
    print(f"OK: app password works for @{s['handle']} ({s['did']})")
    blob, size = bskypost.upload_image(s, str(TEST_CHART))
    print(f"OK: chart upload works ({size[0]}x{size[1]}). Nothing was posted.")


def test_post_bsky():
    from aiq_notes import bskypost
    print("posted:", bskypost.post("Testing a new charts feed. This post will be deleted shortly.", str(TEST_CHART),
                                   "Line chart of real hourly wages for rank-and-file workers since 1964."))


def test_post_x():
    from aiq_notes import xpost
    res = xpost.post("Testing a new charts feed. This post will be deleted shortly.", str(TEST_CHART),
                     alt="Line chart of real hourly wages for rank-and-file workers since 1964.")
    print("posted:", res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post-due", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", choices=["x", "bsky"])
    ap.add_argument("--test-post", choices=["x", "bsky"])
    a = ap.parse_args()
    try:
        if a.post_due or a.dry_run:
            post_due(dry=a.dry_run)
        elif a.verify == "x":
            verify_x()
        elif a.verify == "bsky":
            verify_bsky()
        elif a.test_post == "x":
            test_post_x()
        elif a.test_post == "bsky":
            test_post_bsky()
        else:
            ap.print_help()
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
