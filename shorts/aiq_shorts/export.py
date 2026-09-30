"""Write the narration script, SRT captions, credits and TikTok post text."""
from pathlib import Path


def ts(t, srt=True):
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    if srt:
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"
    return f"{int(m)}:{int(s):02d}"


def write_srt(tl, path):
    out = []
    for k, c in enumerate(tl.cues, 1):
        out += [str(k), f"{ts(c['start'])} --> {ts(c['end'])}", c["text"], ""]
    Path(path).write_text("\n".join(out))


def describe(spec):
    """One-line description of what's on screen, for the shot list."""
    t = spec["type"]
    if t in ("photo", "hook", "video"):
        bits = [f"{'Video' if t == 'video' else 'Photo'}: {spec.get('media', '?')}"]
        if spec.get("headline"):
            h = spec["headline"]
            bits.append(f"headline \"{h if isinstance(h, str) else h.get('text', '')}\"")
        for ov in spec.get("overlays", []):
            bits.append(f"{ov.get('kind')} {ov.get('text') or ov.get('value', '')}")
        return "; ".join(bits)
    if t == "article_card":
        return "Article card" + (f" + chips {', '.join(spec.get('chips', []))}" if spec.get("chips") else "")
    if t in ("figure", "map"):
        return f"Article chart: {spec.get('source') or spec.get('media', '')}"
    if t == "outro":
        return "End card: wordmark + URL"
    title = spec.get("title") or spec.get("kicker") or spec.get("text", "")
    return f"{t.replace('_', ' ').title()}: {title}"


def write_script(tl, path):
    sb = tl.storyboard
    art = tl.ctx.article
    words = sum(len(c["text"].split()) for c in tl.cues)
    lines = [
        f"# {sb.get('title', art.get('title', 'Short'))}",
        "",
        f"**Source article:** {art.get('title', '')} — {art.get('url', '')}  ",
        f"**Runtime:** {tl.duration:.0f}s · **Words:** {words} · **Pace:** {tl.wpm} wpm",
        "",
        "Read the voiceover at a brisk, conversational pace. Each line below is one on-screen",
        "caption; the video is timed so each line starts at the time shown. If you read faster or",
        "slower, nudge clips in your editor or re-render with a different `wpm` in storyboard.json.",
        "",
        "## Voiceover (read straight through)",
        "",
    ]
    para = []
    for i, _ in enumerate(tl.scenes):
        scene_lines = [c["text"] for c in tl.cues if c["scene"] == i]
        if scene_lines:
            para.append(" ".join(scene_lines))
    lines += ["\n\n".join(para), "", "## Timed shot list", "",
              "| # | Time | On screen | Say |", "|---|------|-----------|-----|"]
    for i, spec in enumerate(sb["scenes"]):
        a, b = tl.spans[i]
        say = " / ".join(c["text"] for c in tl.cues if c["scene"] == i) or "—"
        lines.append(f"| {i + 1} | {ts(a, False)}–{ts(b, False)} | {describe(spec)} | {say} |")
    lines += ["", "## Line-by-line cues", ""]
    for c in tl.cues:
        lines.append(f"- `{ts(c['start'], False)}` {c['text']}")
    notes = sb.get("notes")
    if notes:
        lines += ["", "## Notes for the edit", ""] + [f"- {n}" for n in notes]
    Path(path).write_text("\n".join(lines) + "\n")


def write_credits(tl, path):
    seen, out = set(), []
    for s in tl.scenes:
        src = s.source_line()
        if src and src not in seen:
            seen.add(src)
            out.append(f"- {src}")
    music = tl.storyboard.get("music_credit")
    if music:
        out.append(f"- {music}")
    Path(path).write_text("# On-screen sources & credits\n\n" + "\n".join(out) + "\n")


def post_parts(tl):
    post = tl.storyboard.get("post", {})
    art = tl.ctx.article
    headline = post.get("headline") or art.get("title", "")
    caption = post.get("caption") or art.get("subtitle", "")
    cta = post.get("cta", "Full story at the link in bio.")
    tags = " ".join("#" + h.lstrip("#") for h in post.get("hashtags", []))
    return {"headline": headline, "caption": caption, "cta": cta, "hashtags": tags, "url": art.get("url", "")}


def write_post(tl, path):
    """TikTok post: a headline (title / first line / cover text) and the caption to paste."""
    p = post_parts(tl)
    paste = "\n\n".join(x for x in [p["headline"], p["caption"], p["cta"], p["hashtags"]] if x)
    md = [f"# TikTok post: {tl.ctx.article.get('title', '')}", "",
          "## Headline", "(TikTok title, cover text, and the first line people see)", "", p["headline"], "",
          "## Caption", "", p["caption"], "", p["cta"], "",
          "## Hashtags", "", p["hashtags"], "",
          "## Everything to paste", "", "```", paste, "```", "",
          f"Article: {p['url']}", ""]
    Path(path).with_suffix(".md").write_text("\n".join(md))
    Path(path).write_text(paste + "\n")


def queue_payload(tl):
    """What the Shorts Queue page shows for a finished video: script lines (editable) and the post."""
    lines = []
    for i, spec in enumerate(tl.storyboard["scenes"]):
        say = spec.get("say", [])
        for j, text in enumerate([say] if isinstance(say, str) else say):
            lines.append({"scene": i, "line": j, "text": text, "shot": describe(spec)[:80]})
    return {"runtime": round(tl.duration, 1), "script": lines, "post": post_parts(tl)}
