"""Posting-time model.

Slots come from data/timing_model.json, which `learn.py` rewrites from real
engagement on Jeremy's notes. Each slot is a window (ET) plus a weight; the
picker draws a random minute inside the window so no two days look alike and
nothing lands on a round :00 / :30 like a cron job would.
"""
import json
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MODEL = Path(__file__).resolve().parent.parent / "data" / "timing_model.json"

DEFAULT = {
    "updated": None,
    "note": "Windows in ET. Weights = relative median engagement from note history.",
    "weekday": {
        "morning": {"start": "06:35", "end": "08:05", "weight": 1.6},
        "midday": {"start": "11:50", "end": "13:45", "weight": 1.2},
        "afternoon": {"start": "16:20", "end": "17:55", "weight": 1.9},
    },
    "weekend": {
        "morning": {"start": "08:25", "end": "10:20", "weight": 1.3},
        "midday": {"start": "12:40", "end": "14:50", "weight": 1.3},
        "evening": {"start": "17:05", "end": "20:50", "weight": 1.2},
    },
}


def load():
    if MODEL.exists():
        return json.loads(MODEL.read_text())
    return DEFAULT


def _hm(s):
    h, m = s.split(":")
    return time(int(h), int(m))


def pick_time(day: date, block: str, rng: random.Random, model=None):
    model = model or load()
    kind = "weekend" if day.weekday() >= 5 else "weekday"
    slots = model[kind]
    if block not in slots:                       # map weekday/weekend block names
        block = {"afternoon": "evening", "evening": "afternoon"}.get(block, block)
    w = slots[block]
    a = datetime.combine(day, _hm(w["start"]), ET)
    b = datetime.combine(day, _hm(w["end"]), ET)
    for _ in range(20):
        t = a + timedelta(minutes=rng.randint(0, int((b - a).total_seconds() // 60)))
        if t.minute not in (0, 15, 30, 45):      # avoid robotic-looking times
            return t
    return t


def blocks_for(day: date):
    return ["morning", "midday", "evening"] if day.weekday() >= 5 else ["morning", "midday", "afternoon"]
