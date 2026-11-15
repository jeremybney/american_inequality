"""Daily radar: what changed in the world since the last scan that deserves a note.

Three sources, written to data/radar/YYYY-MM-DD.md for the daily content session:
  1. Data releases: tracked FRED series (BLS, BEA, Census, Fed, EIA) with a new observation
     since the last scan, with the latest value and whether it's a record.
  2. News: Google News RSS for agency releases and inequality topics in the last 24 hours.
  3. Charts taking off: recent image notes from watched writers, ranked by engagement per hour.

State lives in data/radar/seen.json so each release is flagged once.
"""
import json
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from aiq_notes.fred import series  # noqa: E402
from aiq_notes import peers  # noqa: E402

OUT = ROOT / "data" / "radar"
SEEN = OUT / "seen.json"

TRACKED = {
    "UNRATE": "Unemployment rate", "LNS14000006": "Black unemployment", "PAYEMS": "Payroll jobs",
    "CPIAUCSL": "CPI", "CUSR0000SAF11": "Food at home CPI", "CUSR0000SEHA": "Rent CPI",
    "CUSR0000SEHF01": "Electricity CPI", "PPIFIS": "PPI final demand", "CES0500000003": "Avg hourly earnings",
    "PRS85006173": "Labor share", "CP": "Corporate profits", "PSAVERT": "Saving rate",
    "WFRBST01134": "Top 1% wealth share", "WFRBSB50215": "Bottom 50% wealth share",
    "MORTGAGE30US": "30-yr mortgage rate", "MSPUS": "Median new home price", "GASREGW": "Gas price",
    "CCLACBW027SBOG": "Credit card balances", "DRCCLACBS": "Credit card delinquency",
    "RRVRUSQ156N": "Rental vacancy", "RHORUSQ156N": "Homeownership rate", "ICSA": "Jobless claims",
}
# Series that trend up almost every month in nominal terms; "record high" there is noise.
NO_RECORD_FLAG = {"PAYEMS", "CPIAUCSL", "CUSR0000SAF11", "CUSR0000SEHA", "CUSR0000SEHF01", "PPIFIS", "CES0500000003"}
NEWS = [
    "Census Bureau releases", "Bureau of Labor Statistics report", "HUD report", "Federal Reserve report households",
    "CBO report households", "USDA report food insecurity", "inequality new data", "billionaires wealth new report",
    "rent prices new data", "health insurance uninsured new data", "child poverty new data", "minimum wage",
]


def data_releases(seen):
    rows = []
    for sid, name in TRACKED.items():
        try:
            s = series(sid, refresh=True)
        except Exception as e:                       # one bad series shouldn't stop the scan
            rows.append(f"- {name} ({sid}): fetch failed ({str(e)[:60]})")
            continue
        last = s.index[-1].date().isoformat()
        if seen.get(sid) == last:
            continue
        seen[sid] = last
        prev = s.iloc[-2] if len(s) > 1 else float("nan")
        tags = []
        if sid not in NO_RECORD_FLAG and s.iloc[-1] >= s.max():
            tags.append("RECORD HIGH")
        if s.iloc[-1] <= s.min():
            tags.append("RECORD LOW")
        rows.append(f"- **{name}** ({sid}) new value for {last}: {s.iloc[-1]:,.2f} (prior {prev:,.2f}) {' '.join(tags)}")
    return rows


def news():
    out = []
    for q in NEWS:
        u = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:1d")
             + "&hl=en-US&gl=US&ceid=US:en")
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            items = list(ET.fromstring(r.content).iter("item"))[:5]
        except Exception:
            continue
        if items:
            out.append(f"\n**{q}**")
            out += [f"- {i.findtext('title')}" for i in items]
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {}
    first_run = not seen
    rel = data_releases(seen)
    charts = peers.scan(hours=36)[:10]
    lines = [f"# Radar {datetime.now():%Y-%m-%d %H:%M}", "", "## New data releases since last scan", ""]
    lines += (["(first run: baseline recorded, everything listed)"] if first_run else []) + (rel or ["- none"])
    lines += ["", "## Charts taking off (last 36h, engagement per hour)", ""]
    lines += [f"- {c['per_hour']}/h ({c['likes']}L/{c['restacks']}R) **{c['author']}** (id {c['author_id']}): "
              f"{c['body'][:160]!r} {c['url']}" for c in charts] or ["- none"]
    lines += ["", "## News (last 24h)"] + news()
    path = OUT / f"{datetime.now():%Y-%m-%d}.md"
    path.write_text("\n".join(lines) + "\n")
    SEEN.write_text(json.dumps(seen, indent=1))
    print(path)


if __name__ == "__main__":
    main()
