"""Find charts other data writers posted recently that are taking off on Substack.

Reads public profile feeds (no login). Ranks each image note by engagement per hour
since posting, so a chart that's spreading right now beats an older one with more total likes.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

WATCH = {   # Substack user id -> name (extend freely)
    1658881: "Steve Rattner", 157561: "Derek Thompson", 2432780: "Aziz Sunderji",
    499432171: "Our World in Data", 273628738: "Max Roser", 10269516: "Hannah Ritchie",
    26817325: "Paul Krugman",
}
OUT = Path(__file__).resolve().parent.parent / "data" / "peers"


def recent_charts(uid, name, hours=96, pages=3):
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    items, cur = [], None
    for _ in range(pages):
        r = s.get(f"https://substack.com/api/v1/reader/feed/profile/{uid}" + (f"?cursor={cur}" if cur else ""), timeout=60)
        if r.status_code != 200:
            break
        j = r.json()
        items += j.get("items", [])
        cur = j.get("nextCursor")
        if not cur:
            break
        time.sleep(1.2)
    now = datetime.now(timezone.utc)
    out = []
    for i in items:
        c = i.get("comment") or {}
        if i.get("type") != "comment" or c.get("user_id") != uid or c.get("ancestor_path"):
            continue
        imgs = [a.get("imageUrl") for a in c.get("attachments") or [] if a.get("type") == "image" and a.get("imageUrl")]
        if not imgs:
            continue
        d = datetime.fromisoformat(c["date"].replace("Z", "+00:00"))
        age = max((now - d).total_seconds() / 3600, 1)
        if age > hours:
            continue
        score = (c.get("reaction_count") or 0) + 3 * (c.get("restacks") or 0) + 2 * (c.get("children_count") or 0)
        out.append(dict(author=name, author_id=uid, note_id=c["id"], date=c["date"], age_h=round(age, 1),
                        score=score, per_hour=round(score / age, 1), likes=c.get("reaction_count"),
                        restacks=c.get("restacks"), body=c.get("body"), images=imgs,
                        url=f"https://substack.com/@{c.get('handle')}/note/c-{c['id']}"))
    return out


def scan(hours=96):
    rows = []
    for uid, name in WATCH.items():
        try:
            rows += recent_charts(uid, name, hours)
        except requests.RequestException as e:
            print("skip", name, e)
        time.sleep(2)
    rows.sort(key=lambda r: -r["per_hour"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"scan_{datetime.now():%Y%m%d_%H%M}.json").write_text(json.dumps(rows, indent=1))
    return rows


if __name__ == "__main__":
    for r in scan()[:25]:
        print(f"{r['per_hour']:>7}/h {r['score']:>6} {r['age_h']:>5}h  {r['author']:<18} {r['body'][:110]!r}")
