"""Post any Substack Notes that are due.

Runs every ~15 minutes from GitHub Actions. Source of truth for each note:
  1. the Google Sheet content calendar (your edits win), if config.sheet_id is set
  2. otherwise calendar/*.json in this repo

Rules:
  - Status must be Scheduled or Approved. Hold / Skip / anything else = never posts.
  - Posts only inside a 3-hour grace window after the scheduled time
    (GitHub cron can run late; a note that's very stale is skipped, not dumped).
  - At most one note per run, so a backlog can never burst out at once.
  - Every outcome is written to state/posted.json; a note is never posted twice.
  - config.json "paused": true stops everything.

Usage:
  python3 post_due.py              # post what's due
  python3 post_due.py --ahead 48   # also queue the next 48h in Substack's scheduler (Mac default)
  python3 post_due.py --dry-run    # show what would post
  python3 post_due.py --verify     # check the Substack login only
  python3 post_due.py --now ID     # post one note immediately (manual test)
  python3 post_due.py --test-upload  # upload a chart without publishing anything
"""
import argparse
import csv
import io
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from aiq_notes.substack import Client, SubstackError  # noqa: E402

ET = ZoneInfo("America/New_York")
STATE = ROOT / "state" / "posted.json"
CONFIG = json.loads((ROOT / "config.json").read_text())
GRACE = timedelta(hours=3)
POSTABLE = {"scheduled", "approved"}


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(st):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1, sort_keys=True))


def repo_calendar():
    notes = {}
    for f in sorted((ROOT / "calendar").glob("*.json")):
        for n in json.loads(f.read_text()):
            notes[n["id"]] = n
    return notes


def sheet_rows():
    sid = CONFIG.get("sheet_id")
    if not sid:
        return []
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={CONFIG.get('sheet_gid', 0)}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    if r.text.lstrip().startswith("<"):
        raise RuntimeError("Sheet is not readable by link. Share it as 'Anyone with the link: Viewer'.")
    return list(csv.DictReader(io.StringIO(r.text)))


def parse_time(v):
    """Accepts what Sheets exports after a human edits the cell."""
    v = v.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
                "%m/%d/%Y %I:%M %p", "%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d %I:%M %p"):
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=ET)
        except ValueError:
            pass
    raise ValueError(f"can't read time {v!r}; use 2026-11-16 07:04")


def merged_calendar():
    """Repo calendar with Sheet edits applied on top (text, time, status, chart)."""
    notes = repo_calendar()
    for row in sheet_rows():
        nid = (row.get("ID") or "").strip()
        if not nid:
            continue
        n = notes.setdefault(nid, {"id": nid})
        if row.get("Post at (ET)"):
            n["scheduled_et"] = parse_time(row["Post at (ET)"]).isoformat()
        if row.get("Status"):
            n["status"] = row["Status"].strip()
        if row.get("Note text"):
            n["text"] = row["Note text"].replace("\r\n", "\n").strip()
        if row.get("Chart file"):
            n["chart"] = row["Chart file"].strip()
        n["_from_sheet"] = True
    return notes


def due(notes, state, now):
    out = []
    for n in notes.values():
        if n["id"] in state or (n.get("status") or "").lower() not in POSTABLE:
            continue
        if not n.get("text") or not n.get("scheduled_et"):
            continue
        t = datetime.fromisoformat(n["scheduled_et"])
        if t <= now <= t + GRACE:
            out.append((t, n))
        elif now > t + GRACE:
            state[n["id"]] = {"status": "Missed", "at": now.isoformat(), "scheduled": n["scheduled_et"]}
    return [n for _, n in sorted(out, key=lambda x: x[0])]


def chart_path(n):
    c = n.get("chart")
    if not c:
        return None
    return c if c.startswith("http") else str(ROOT / c)


def post(n, state, now):
    try:
        res = Client().post_note(n["text"], chart_path(n))
        state[n["id"]] = {"status": "Posted", "at": now.isoformat(), "scheduled": n["scheduled_et"], **res}
        print(f"posted {n['id']}: {res}")
    except (SubstackError, OSError, requests.RequestException) as e:
        state[n["id"]] = {"status": "Error", "at": now.isoformat(), "error": str(e)[:500]}
        print(f"ERROR {n['id']}: {e}")


def schedule_ahead(notes, state, now, hours):
    """Queue upcoming notes in Substack's native scheduler, so they publish on time
    even when this computer is asleep. Notes due within 15 minutes are left to the
    post-now path. Sheet edits made after a note is queued must be made in Substack."""
    soon, horizon = now + timedelta(minutes=15), now + timedelta(hours=hours)
    queued = 0
    for n in sorted(notes.values(), key=lambda n: n.get("scheduled_et", "")):
        if n["id"] in state or (n.get("status") or "").lower() not in POSTABLE:
            continue
        if not n.get("text") or not n.get("scheduled_et"):
            continue
        t = datetime.fromisoformat(n["scheduled_et"])
        if not (soon < t <= horizon):
            continue
        try:
            res = Client().schedule_note(n["text"], chart_path(n), t)
            state[n["id"]] = {"status": "Queued in Substack", "at": now.isoformat(), "scheduled": n["scheduled_et"], **res}
            print(f"queued {n['id']} for {n['scheduled_et']}: {res}")
            queued += 1
        except (SubstackError, OSError, requests.RequestException) as e:
            state[n["id"]] = {"status": "Error", "at": now.isoformat(), "error": str(e)[:500]}
            print(f"ERROR queueing {n['id']}: {e}")
        save_state(state)                      # save after each so a crash can't double-queue
    return queued


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--now", metavar="ID")
    ap.add_argument("--ahead", type=float, metavar="HOURS",
                    help="also queue notes due in the next HOURS in Substack's own scheduler")
    ap.add_argument("--test-upload", action="store_true",
                    help="upload one chart and create an attachment, without publishing a note")
    a = ap.parse_args()

    if a.verify:
        print(Client().whoami())
        return
    if a.test_upload:
        c = Client()
        url = c.upload_image(str(ROOT / "charts" / "2026-11-16" / "labor_share.png"))
        print("image uploaded:", url)
        print("attachment id:", c.attach_image(url))
        print("nothing was published")
        return
    if CONFIG.get("paused"):
        print("paused in config.json")
        return

    now = datetime.now(ET)
    state = load_state()
    notes = merged_calendar()

    if a.now:
        post(notes[a.now], state, now)
        save_state(state)
        return

    queue = due(notes, state, now)
    if a.dry_run:
        upcoming = sorted((n for n in notes.values() if n["id"] not in state),
                          key=lambda n: n.get("scheduled_et", ""))[:5]
        print("due now:", [n["id"] for n in queue])
        print("next up:", [(n["id"], n.get("scheduled_et"), n.get("status")) for n in upcoming])
        return
    if queue:
        post(queue[0], state, now)
    if a.ahead:
        schedule_ahead(notes, state, now, a.ahead)
    elif not queue:
        print("nothing due")
    save_state(state)


if __name__ == "__main__":
    main()
