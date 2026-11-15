"""Weekly learning loop: re-read engagement, retune posting windows, report.

1. Pulls Jeremy's public notes feed (no login needed).
2. Scores every top-level note: likes + 3x restacks + 2x replies (restacks
   are what spread a note, so they count most).
3. Picks the best three non-overlapping posting windows for weekdays and
   weekends from the last 150 days, shrinking small samples toward the
   overall median so one viral note can't hijack the schedule.
4. Writes data/timing_model.json (used for all future batches) and
   data/performance.md (what worked, including the notes this tool posted).
"""
import json
import statistics as st
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
CONFIG = json.loads((ROOT / "config.json").read_text())
ET = ZoneInfo("America/New_York")
UID = CONFIG["substack_user_id"]

WINDOWS = {   # candidate windows (ET); learn.py chooses three per day type
    "weekday": [("06:30", "07:50"), ("07:50", "09:10"), ("09:10", "10:50"), ("11:40", "13:10"),
                ("13:10", "14:50"), ("15:00", "16:20"), ("16:20", "17:55"), ("18:00", "19:40"), ("19:40", "21:30")],
    "weekend": [("07:30", "09:00"), ("09:00", "10:40"), ("10:40", "12:30"), ("12:40", "14:50"),
                ("14:50", "16:50"), ("17:05", "19:00"), ("19:00", "21:00")],
}
NAMES = {"weekday": ["morning", "midday", "afternoon"], "weekend": ["morning", "midday", "evening"]}


def fetch_notes(pages=30):
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    items, cur = [], None
    for _ in range(pages):
        url = f"https://substack.com/api/v1/reader/feed/profile/{UID}" + (f"?cursor={cur}" if cur else "")
        r = s.get(url, timeout=60)
        if r.status_code != 200:
            break
        j = r.json()
        items += j.get("items", [])
        cur = j.get("nextCursor")
        if not cur:
            break
        time.sleep(1.5)
    rows = []
    for i in items:
        c = i.get("comment") or {}
        if i.get("type") != "comment" or i["context"]["type"] != "note" or c.get("user_id") != UID or c.get("ancestor_path"):
            continue
        d = datetime.fromisoformat(c["date"].replace("Z", "+00:00")).astimezone(ET)
        rows.append(dict(id=c["id"], date=d, likes=c.get("reaction_count") or 0, restacks=c.get("restacks") or 0,
                         replies=c.get("children_count") or 0, body=(c.get("body") or "")[:140],
                         image=any(a.get("type") == "image" for a in c.get("attachments") or [])))
    for r in rows:
        r["score"] = r["likes"] + 3 * r["restacks"] + 2 * r["replies"]
    return rows


def _mins(hm):
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def tune(rows):
    cutoff = datetime.now(ET) - timedelta(days=150)
    recent = [r for r in rows if r["date"] >= cutoff and r["date"] <= datetime.now(ET) - timedelta(days=2)]
    allscores = sorted(r["score"] for r in recent) or [1]
    cap = allscores[int(0.9 * (len(allscores) - 1))]          # winsorize: one viral note can't move a window
    for r in recent:
        r["capped"] = min(r["score"], cap)
    overall = st.median([r["capped"] for r in recent]) if recent else 1
    model = {"updated": datetime.now(ET).isoformat(timespec="minutes"),
             "note": f"Tuned on {len(recent)} notes from the last 150 days. Weight = shrunk median score / overall median."}
    for kind, wins in WINDOWS.items():
        scored = []
        for a, b in wins:
            xs = [r["capped"] for r in recent if (r["date"].weekday() >= 5) == (kind == "weekend")
                  and _mins(a) <= r["date"].hour * 60 + r["date"].minute < _mins(b)]
            k = 10                                   # shrinkage strength
            med = st.median(xs) if xs else overall
            shrunk = (len(xs) * med + k * overall) / (len(xs) + k)
            scored.append((shrunk / overall if overall else 1, a, b, len(xs)))
        chosen = []
        for w in sorted(scored, reverse=True):       # best first, no overlap, spread >= 2.5h apart
            if all(abs(_mins(w[1]) - _mins(c[1])) >= 150 for c in chosen):
                chosen.append(w)
            if len(chosen) == 3:
                break
        chosen.sort(key=lambda w: _mins(w[1]))
        model[kind] = {NAMES[kind][i]: {"start": a, "end": b, "weight": round(wt, 2), "n": n}
                       for i, (wt, a, b, n) in enumerate(chosen)}
    return model


def report(rows, model):
    posted = json.loads((ROOT / "state" / "posted.json").read_text()) if (ROOT / "state" / "posted.json").exists() else {}
    ours = {str(v.get("note_id")): k for k, v in posted.items() if v.get("status") == "Posted"}
    lines = [f"# Notes performance ({datetime.now(ET):%b %-d, %Y})", "",
             "## Posting windows now in use (ET)", ""]
    for kind in ("weekday", "weekend"):
        for name, w in model[kind].items():
            lines.append(f"- {kind} {name}: {w['start']}-{w['end']} (weight {w['weight']}, n={w['n']})")
    mine = [r for r in rows if str(r["id"]) in ours]
    if mine:
        lines += ["", "## Notes posted by this tool", "", "| Calendar ID | Posted | Likes | Restacks | Replies | Score |", "|---|---|---|---|---|---|"]
        for r in sorted(mine, key=lambda r: r["date"]):
            lines.append(f"| {ours[str(r['id'])]} | {r['date']:%a %b %-d %-I:%M%p} | {r['likes']} | {r['restacks']} | {r['replies']} | {r['score']} |")
    lines += ["", "## Top 10 notes, last 30 days", ""]
    last30 = [r for r in rows if r["date"] >= datetime.now(ET) - timedelta(days=30)]
    for r in sorted(last30, key=lambda r: -r["score"])[:10]:
        lines.append(f"- **{r['score']}** ({r['likes']}L/{r['restacks']}R/{r['replies']}C, {r['date']:%a %-I:%M%p}) {r['body']!r}")
    (ROOT / "data" / "performance.md").write_text("\n".join(lines) + "\n")


def main():
    rows = fetch_notes()
    if len(rows) < 30:
        print(f"only {len(rows)} notes fetched; keeping existing model")
        return
    model = tune(rows)
    (ROOT / "data" / "timing_model.json").write_text(json.dumps(model, indent=1))
    report(rows, model)
    print(json.dumps(model, indent=1))


if __name__ == "__main__":
    main()
