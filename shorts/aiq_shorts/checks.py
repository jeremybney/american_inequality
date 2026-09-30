"""House rules every short must pass before it renders.

Length and structure rules come from the author; the voice rules catch the
"AI narrator" habits the author doesn't use (colons, question-then-answer
setups, dramatic reveals). Errors block `render`; warnings are printed.
"""
import re

MAX_SECONDS = 75
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
    if tl.duration > MAX_SECONDS:
        errors.append(f"runtime {tl.duration:.0f}s is over the {MAX_SECONDS}s cap; cut words, not beats")
    elif tl.duration < MIN_SECONDS:
        warnings.append(f"runtime {tl.duration:.0f}s is under {MIN_SECONDS}s; there may be room for one more beat")
    if tl.spans:
        a, b = tl.spans[0]
        if b - a > FIRST_SCENE_MAX:
            errors.append(f"first scene lasts {b - a:.1f}s; keep the opening shot under {FIRST_SCENE_MAX}s "
                          "(give it one short line and cut to the next visual)")
    for i, (a, b) in enumerate(tl.spans[1:], 1):
        if b - a > SCENE_MAX and scenes[i]["type"] not in ("figure",):
            warnings.append(f"scene {i + 1} ({scenes[i]['type']}) holds {b - a:.1f}s; split it or trim its lines")

    # --- required pieces
    if "article_card" not in types:
        errors.append("missing the article_card scene (the clipped article card is always shown)")
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
