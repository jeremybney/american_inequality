"""House rules every short must pass before it renders.

Length and structure rules come from the author; the voice rules catch the
"AI narrator" habits the author doesn't use (colons, question-then-answer
setups, dramatic reveals). Errors block `render`; warnings are printed.
"""
import re

MAX_SECONDS = 89
MIN_SECONDS = 45
FIRST_SCENE_MAX = 4.5    # the opening shot has to move fast
SCENE_MAX = 8.0          # after that, a new visual at least every ~8s

# Phrases that sound like a narrator performing, not the author explaining.
BANNED = [
    r"here'?s the (catch|thing|kicker|twist|problem)", r"\bbut here'?s\b", r"\bthe catch\b",
    r"\bturns out\b", r"\bthe truth is\b", r"\bthe answer\b", r"\bplot twist\b",
    r"\blet'?s (dive|break|talk)\b", r"\byou won'?t believe\b", r"\bbuckle up\b",
    r"\bspoiler\b", r"\bin other words\b", r"\bthink about that\b", r"\bread that again\b",
    r"\bwait\b", r"\bguess what\b", r"\bhere'?s why\b", r"\bhere'?s how\b", r"\bthe kicker\b",
    r"\binsane\b", r"\bwild\b", r"\bmind-?blowing\b",
]


OUTLETS = ["The Washington Post", "Washington Post", "New York Times", "NYT", "Wall Street Journal", "WSJ",
           "Bloomberg", "Reuters", "Associated Press", "CNBC", "CNN", "NPR", "Fox News", "MSNBC", "ABC News",
           "CBS News", "NBC News", "The Atlantic", "Axios", "Politico", "Yahoo Finance", "Fortune", "Forbes",
           "Business Insider", "The Guardian", "Vox", "USA Today", "The Economist", "Financial Times",
           "MarketWatch", "Urban Institute", "Brookings", "Pew Research", "YouTube"]


def _say_lines(spec):
    lines = spec.get("say", [])
    return [lines] if isinstance(lines, str) else list(lines)


def voice_issues(text):
    """Return a list of reasons a spoken line doesn't sound like the author."""
    out = []
    if ":" in text:
        out.append("uses a colon (say it as one sentence instead)")
    if "—" in text or " - " in text or "–" in text:
        out.append("uses a dash aside (split into two plain sentences)")
    # rhetorical question answered by the narrator ("Millennials? They hold…", "In the seventies? Just…")
    if re.search(r"\?\s*\S", text):
        out.append("question followed by its own answer (state it plainly)")
    if re.match(r"^\s*(\w+\s*){1,3}\?\s*$", text):
        out.append("one-word dramatic question")
    for pat in BANNED:
        if re.search(pat, text, re.I):
            out.append(f"narrator phrase /{pat}/")
    return out


def check(tl):
    """Return (errors, warnings) for a built Timeline."""
    errors, warnings = [], []
    scenes = tl.storyboard["scenes"]
    types = [s["type"] for s in scenes]

    # --- length & pacing
    # the author can allow a longer video for one story with storyboard "max_seconds"
    cap = float(tl.storyboard.get("max_seconds", MAX_SECONDS))
    if tl.duration > cap:
        errors.append(f"runtime {tl.duration:.0f}s is over the {cap:.0f}s cap; cut words, not beats")
    elif tl.duration < MIN_SECONDS:
        warnings.append(f"runtime {tl.duration:.0f}s is under {MIN_SECONDS}s; there may be room for one more beat")
    if tl.spans:
        a, b = tl.spans[0]
        if b - a > FIRST_SCENE_MAX and tl.voice:
            warnings.append(f"first scene runs {b - a:.1f}s with the voiceover; a shorter first line keeps the opening quick")
        elif b - a > FIRST_SCENE_MAX:
            errors.append(f"first scene lasts {b - a:.1f}s; keep the opening shot under {FIRST_SCENE_MAX}s "
                          "(give it one short line and cut to the next visual)")
    for i, (a, b) in enumerate(tl.spans[1:], 1):
        if b - a > SCENE_MAX and scenes[i]["type"] not in ("figure",):
            warnings.append(f"scene {i + 1} ({scenes[i]['type']}) holds {b - a:.1f}s; split it or trim its lines")

    # every scene should move: a lone small number ("2x") on plain orange is static and low-impact
    for i, s in enumerate(scenes):
        stats = s.get("stats", [])
        if s["type"] == "big_number" and len(stats) == 1 and abs(float(stats[0].get("value", 0))) < 10:
            warnings.append(f"scene {i + 1} (big_number) is a single small number ({stats[0].get('value')}"
                            f"{stats[0].get('suffix', '')}) with little motion; show it as a chart that moves instead "
                            "(bars growing side by side, a line rising, or the article's own chart)")

    # --- required pieces
    if "article_card" not in types:
        errors.append("missing the article_card scene (the clipped article card is always shown)")
    # the author's article card comes first and early; other outlets only near the end
    card_i = types.index("article_card") if "article_card" in types else None
    if card_i is not None and card_i > 3:
        errors.append(f"the article card is scene {card_i + 1}; it belongs early, ideally scene 3")
    elif card_i is not None and card_i != 2:
        warnings.append(f"the article card is scene {card_i + 1}; scene 3 is the usual spot")
    news_i = [i for i, t in enumerate(types) if t == "news"]
    if len(news_i) > 1:
        errors.append(f"{len(news_i)} news scenes; use at most one, near the end")
    for i in news_i:
        if card_i is not None and i < card_i:
            errors.append(f"news clipping in scene {i + 1} comes before the article card; the author's article always comes first")
        if tl.spans and tl.spans[i][0] < 0.6 * tl.duration:
            errors.append(f"news clipping in scene {i + 1} starts at {tl.spans[i][0]:.0f}s; keep clippings in the last 40% "
                          f"(after {0.6 * tl.duration:.0f}s)")
    if not news_i:
        warnings.append("no `news` scene; a clipping near the end shows the story is current")
    # the narration tells the article's story; clippings are silent proof points
    outlets = set(OUTLETS)
    for s in scenes:
        for it in s.get("items", []) if s["type"] == "news" else []:
            if it.get("outlet"):
                outlets.add(it["outlet"])
    for i, spec in enumerate(scenes):
        for line in _say_lines(spec):
            hit = next((o for o in outlets if o and re.search(r"\b" + re.escape(o) + r"\b", line, re.I)), None)
            if hit:
                errors.append(f"scene {i + 1} names {hit} in the narration; let the clipping be the proof "
                              "and keep the narration on the article's ideas")
    if not types or types[-1] != "outro":
        errors.append("the last scene must be the outro end card")
    article_imgs = [s for s in scenes if s["type"] in ("figure", "map")
                    or str(s.get("media", "")).startswith("article_")]
    has_article_images = any(tl.ctx.media_dir.glob("article_*"))
    if has_article_images and not article_imgs:
        errors.append("use at least one chart or map from the article (a `figure` scene with media/article_NN.*)")
    used = {str(s.get("media", "")) for s in scenes}
    for idx, im in enumerate(tl.ctx.article.get("images", []), 1):
        cap = f"{im.get('caption', '')} {im.get('alt', '')}"
        if re.search(r"\bmaps?\b|count(y|ies)|by state|zip code", cap, re.I) and \
                not any(u.startswith(f"article_{idx:02d}") for u in used):
            warnings.append(f"article_{idx:02d} looks like a map ({cap.strip()[:50]}); maps are usually the best chart to reuse")

    # --- voice
    for i, spec in enumerate(scenes):
        for line in _say_lines(spec):
            for why in voice_issues(line):
                errors.append(f"scene {i + 1} voice: \"{line}\": {why}")
    return errors, warnings


def report(tl, strict=True):
    errors, warnings = check(tl)
    for w in warnings:
        print(f"  ~ {w}")
    for e in errors:
        print(f"  ✗ {e}")
    if not errors and not warnings:
        print(f"  ✓ house rules pass ({tl.duration:.0f}s)")
    return errors
