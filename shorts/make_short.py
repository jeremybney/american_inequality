#!/usr/bin/env python3
"""Turn an American Inequality Substack post into a vertical TikTok/Reels/Shorts video.

Workflow (see README.md):
  1. new     <substack-url>                  fetch article text, cover, charts -> projects/<slug>/
  2. (write projects/<slug>/storyboard.json — Claude does this from the article)
  3. search  <slug> "<query>" [--pixabay|--pexels] [--video]   find real photos/footage, writes a contact sheet
     pick    <slug> <n> --as <name>          download candidate #n as media/<name>.<ext>
  4. stills  <slug>                          key-frame contact sheet for review
  5. render  <slug>                          final MP4 + script.md + captions.srt + credits + post text
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from aiq_shorts import checks, engine, export, media, substack, visuals  # noqa: E402


def _load_dotenv(path=HERE / ".env"):
    """Local, git-ignored KEY=value file (e.g. PIXABAY_API_KEY) for keys not set in the environment."""
    import os
    if path.exists():
        for line in path.read_text().splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and k and not k.startswith("#"):
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

PROJECTS = HERE / "projects"


def project(slug):
    p = PROJECTS / slug
    if not p.exists():
        raise SystemExit(f"No project {slug!r} in {PROJECTS}")
    return p


def cmd_doctor(a):
    """Check network access and API keys needed by each step."""
    import os
    import urllib.request
    checks = [("Substack article", "https://americaninequality.substack.com/api/v1/posts?limit=1"),
              ("Substack images", "https://substack-post-media.s3.amazonaws.com/"),
              ("Wikimedia search", "https://commons.wikimedia.org/w/api.php?action=query&format=json&meta=siteinfo"),
              ("Wikimedia thumbnails", "https://upload.wikimedia.org/wikipedia/commons/thumb/"),
              ("Pixabay API", "https://pixabay.com/api/"),
              ("Pixabay files", "https://cdn.pixabay.com/")]
    for name, url in checks:
        try:
            urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": media.UA}), timeout=15)
            status = "ok"
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            # any HTTP answer from the site itself means the network path is open
            status = f"ok (site answered {code})" if code else f"BLOCKED ({getattr(e, 'reason', e)})"
        print(f"  {name:<22} {status}")
    for var, what in [("PIXABAY_API_KEY", "stock video/photos"), ("PEXELS_API_KEY", "stock video (optional)")]:
        print(f"  {var:<22} {'set' if os.environ.get(var) else 'not set'}  ({what})")
    if os.environ.get("PIXABAY_API_KEY"):
        try:
            n = len(media.search_pixabay("city street", n=3, video=True))
            print(f"  Pixabay key test       ok ({n} clips)")
        except Exception as e:  # noqa: BLE001
            print(f"  Pixabay key test       FAILED: {e}")


def cmd_new(a):
    slug = substack.slug_from_url(a.url) if "/p/" in a.url else a.url
    pdir = PROJECTS / slug
    pdir.mkdir(parents=True, exist_ok=True)
    if a.manual:
        art = substack.from_manual(pdir, a.title or slug, a.subtitle or "", a.authors or [], a.date,
                                   a.url if a.url.startswith("http") else "", a.text)
    else:
        art = substack.fetch(a.url, pdir)
    print(f"Project: {pdir}")
    print(f"  {art['title']} — {', '.join(art.get('authors', []))} ({art.get('date_label', '')})")
    print(f"  {len(art.get('images', []))} inline images saved to media/")
    print("Next: write storyboard.json (see storyboard_reference.md), then `stills`.")


def cmd_search(a):
    pdir = project(a.slug)
    source = "pexels" if a.pexels else "pixabay" if a.pixabay else \
        (media.default_video_source() if a.video else "wikimedia")
    cands = media.search(a.query, source, a.n, a.video)
    cdir = pdir / ".cache" / "candidates"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "last.json").write_text(json.dumps(cands, indent=2))
    thumbs = cdir / "thumbs"
    if thumbs.exists():
        for f in thumbs.glob("*"):
            f.unlink()
    thumbs.mkdir(exist_ok=True)
    sheet = media.contact_sheet(cands, thumbs, cdir / "contact_sheet.jpg")
    for i, c in enumerate(cands):
        print(f"#{i:<2} {c['width']}x{c['height']}  {c['title'][:70]}\n     {c['credit']}")
    print(f"Contact sheet: {sheet}")


def cmd_pick(a):
    pdir = project(a.slug)
    cands = json.loads((pdir / ".cache" / "candidates" / "last.json").read_text())
    c = cands[a.n]
    ext = ".mp4" if c.get("video") else (Path(c["url"].split("?")[0]).suffix.lower() or ".jpg")
    name = f"{a.as_name}{ext}"
    headers = media._pexels_headers() if c["source"] == "pexels" else None
    media.download(c["url"], pdir / "media" / name, headers)
    media.save_credit(pdir / "media", name, {"credit": c["credit"], "url": c.get("page")})
    print(f"Saved media/{name}  ({c['credit']})")


def cmd_plan(a):
    pdir = project(a.slug)
    visuals.plan(pdir, top=a.top, per=a.per, fetch=not a.no_fetch,
                 only=set(a.only.split(",")) if a.only else None)
    print(f"Visual plan: {pdir / 'visual_plan.md'}")
    print(f"Sheets:      {pdir / '.cache' / 'plan'}/*.jpg  (article_images.jpg = the article's own images)")


def cmd_use(a):
    pdir = project(a.slug)
    name, c = visuals.use_candidate(pdir, a.key, a.n, a.as_name)
    print(f"Saved media/{name}  ({c['credit']})")


def cmd_autofill(a):
    """For every photo scene whose media file is missing, search its `query` and
    save a contact sheet + the top candidate, so a link alone yields a full draft."""
    pdir = project(a.slug)
    sb = json.loads((pdir / "storyboard.json").read_text())
    for i, sc in enumerate(sb["scenes"]):
        name, q = sc.get("media"), sc.get("query")
        if sc["type"] not in ("photo", "hook", "video") or not name or not q:
            continue
        if (pdir / "media" / name).exists() and not a.force:
            continue
        video = sc["type"] == "video" or Path(name).suffix.lower() in media.VIDEO_EXT
        source = sc.get("query_source") or (media.default_video_source() if video else "wikimedia")
        try:
            cands = media.search(q, source, 8, video)
        except Exception as e:  # noqa: BLE001
            print(f"  scene {i}: search failed for {q!r}: {e}")
            continue
        if not cands:
            print(f"  scene {i}: no results for {q!r}")
            continue
        cdir = pdir / ".cache" / "candidates" / Path(name).stem
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "candidates.json").write_text(json.dumps(cands, indent=2))
        media.contact_sheet(cands, cdir, cdir / "contact_sheet.jpg")
        c = cands[0]
        headers = media._pexels_headers() if c["source"] == "pexels" else None
        media.download(c["url"], pdir / "media" / name, headers)
        media.save_credit(pdir / "media", name, {"credit": c["credit"], "url": c.get("page")})
        print(f"  scene {i}: {name} <- {c['title'][:60]}  (sheet: {cdir / 'contact_sheet.jpg'})")


def cmd_grab(a):
    """Pull an 'in the news' item into media/: a YouTube video (thumbnail + title), a report
    PDF (kept as PDF; the news scene renders its first page), an image URL, or a local file
    such as a screenshot the user sent."""
    import re
    import shutil
    import urllib.parse
    pdir = project(a.slug)
    mdir = pdir / "media"
    src = a.source
    info = {}
    if Path(src).exists():
        ext = Path(src).suffix.lower() or ".png"
        dest = mdir / f"{a.as_name}{ext}"
        shutil.copy(src, dest)
    elif re.search(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts/)", src):
        vid = (re.search(r"[?&]v=([\w-]{11})", src) or re.search(r"(?:youtu\.be/|shorts/)([\w-]{11})", src)).group(1)
        meta = media.http_json("https://www.youtube.com/oembed?format=json&url=" +
                               urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}"))
        dest = mdir / f"{a.as_name}.jpg"
        for size in ("maxresdefault", "sddefault", "hqdefault"):
            try:
                media.download(f"https://i.ytimg.com/vi/{vid}/{size}.jpg", dest)
                break
            except Exception:  # noqa: BLE001
                continue
        info = {"kind": "video", "title": meta.get("title", ""), "outlet": meta.get("author_name", "")}
    else:
        path = urllib.parse.urlparse(src).path
        ext = Path(path).suffix.lower() or ".jpg"
        dest = mdir / f"{a.as_name}{ext}"
        media.download(src, dest)
        if ext == ".pdf":
            info = {"kind": "report"}
    credit = a.credit or info.get("outlet") or urllib.parse.urlparse(src).netloc or "Provided screenshot"
    media.save_credit(mdir, dest.name, {"credit": credit, "url": src if "://" in src else None, **info})
    item = {"media": dest.name, "outlet": a.outlet or info.get("outlet", ""), "date": a.date or ""}
    if info.get("kind") == "video":
        item.update({"kind": "video", "title": info.get("title", "")})
    print(f"Saved media/{dest.name}")
    print("News item for the storyboard:\n  " + json.dumps(item))


def cmd_clip(a):
    """Find-and-clip: screenshot a news article's headline into media/ (or build a quoted
    headline card when the site blocks automated visitors)."""
    from aiq_shorts import clip as clipper
    pdir = project(a.slug)
    out = pdir / "media" / f"{a.as_name}.png"
    meta = clipper.clip(a.url, out)
    outlet = a.outlet or meta.get("outlet", "")
    date = a.date or meta.get("date_label", "")
    if meta.get("method") == "screenshot":
        media.save_credit(pdir / "media", out.name, {"credit": f"Screenshot: {outlet}", "url": a.url,
                                                     "headline": meta.get("title", "")})
        item = {"media": out.name, "outlet": outlet, "date": date}
        if meta.get("highlight"):
            item["highlight"] = meta["highlight"]
        print(f"Clipped the headline from {outlet or a.url} -> media/{out.name}")
    else:
        headline = a.headline or meta.get("title")
        if not headline:
            raise SystemExit(f"Couldn't clip ({meta.get('reason')}). Re-run with --headline/--outlet/--date "
                             "from the search result to make a quoted headline card.")
        item = {"headline": headline, "outlet": outlet, "date": date}
        if a.dek:
            item["dek"] = a.dek
        print(f"No screenshot ({meta.get('reason')}); use a quoted headline card instead.")
    print("News item for the storyboard:\n  " + json.dumps(item, ensure_ascii=False))


def cmd_voice(a):
    """Sync the author's recorded voiceover: clean it, find each line, time the video to it."""
    import re
    from aiq_shorts import voice
    pdir = project(a.slug)
    if a.off:
        sb_path = pdir / "storyboard.json"
        sb = json.loads(sb_path.read_text())
        sb.pop("voiceover", None)
        sb_path.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
        print("Voiceover removed; timing falls back to the script estimate.")
        return
    src = Path(a.audio)
    head = src.read_bytes()[:64]
    if src.suffix == ".txt" or re.fullmatch(rb"[A-Za-z0-9+/=\s]+", head or b"x"):
        # recordings uploaded through the Shorts Queue page are stored as base64 text
        import base64
        decoded = pdir / "media" / f"voiceover_upload.{(a.ext or 'm4a').lstrip('.')}"
        decoded.write_bytes(base64.b64decode(src.read_bytes()))
        src = decoded
    vo = voice.sync(pdir, src, max_gap=a.max_gap)
    if vo.get("pauses_trimmed_s"):
        print(f"Tightened pauses between lines to {a.max_gap}s (removed {vo['pauses_trimmed_s']}s of silence; words untouched)")
    print(f"Voiceover: {vo['duration']:.1f}s of audio, {len(vo['cues'])} lines")
    for c in vo["cues"]:
        flag = "" if c["matched"] >= 0.6 else "   <- couldn't hear most of this line (skipped or reworded?)"
        print(f"  {c['start']:6.1f}–{c['end']:5.1f}s  {c['text'][:70]}{flag}")
    tl = engine.Timeline(pdir, quiet=True)
    checks.report(tl)
    print("Next: `stills` to review, then `render` (the voice is mixed in automatically).")


def cmd_music(a):
    """Choose (or change) the background track for a video."""
    from aiq_shorts import music
    pdir = project(a.slug)
    if a.list:
        hist = music.used()
        for t in music.candidates():
            who = [k for k, v in hist.items() if v.get("title") == t["title"] and "~" not in k]
            print(f"  {t['title']:<30} {t['bpm']:>4} bpm  {t['feel']:<40} {'(used: ' + ', '.join(who) + ')' if who else ''}")
        return
    if a.off:
        sb_path = pdir / "storyboard.json"
        sb = json.loads(sb_path.read_text())
        sb["music"] = {"off": True}
        sb.pop("music_credit", None)
        sb_path.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
        print("Music turned off for this video.")
        return
    m = music.assign(pdir, title=a.title, reroll=a.reroll)
    if a.start is not None or a.level is not None:
        sb_path = pdir / "storyboard.json"
        sb = json.loads(sb_path.read_text())
        if a.start is not None:
            sb["music"]["start"] = a.start
        if a.level is not None:
            sb["music"]["level_db"] = a.level
        sb_path.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
        m = sb["music"]
    print(f"Music: {m['title']} ({m['feel']}), starts at {m['start']}s, bed level {m['level_db']} LUFS")
    print(f"Credit: {m['credit']}")


def cmd_stills(a):
    pdir = project(a.slug)
    out = pdir / "output" / "stills.png"
    out.parent.mkdir(exist_ok=True)
    tl = engine.render_stills(pdir, out, captions=not a.no_captions)
    checks.report(tl)
    print(f"{len(tl.scenes)} scenes, {tl.duration:.1f}s -> {out}")


def cmd_frame(a):
    pdir = project(a.slug)
    out = pdir / "output" / f"frame_{a.t:.1f}.png"
    out.parent.mkdir(exist_ok=True)
    engine.render_frame_png(pdir, a.t, out)
    print(out)


def cmd_render(a):
    pdir = project(a.slug)
    out_dir = pdir / "output"
    out_dir.mkdir(exist_ok=True)
    name = a.slug + ("_nocaptions" if a.no_captions else "")
    sbm = json.loads((pdir / "storyboard.json").read_text()).get("music")
    if not sbm:  # every video gets its own track unless music was turned off
        from aiq_shorts import music
        m = music.assign(pdir)
        print(f"Music: {m['title']} ({m['feel']})")
    if checks.report(engine.Timeline(pdir, quiet=True)) and not a.force:
        raise SystemExit("Fix the ✗ items above (or pass --force) before rendering.")
    video = out_dir / f"{name}.mp4"
    tl = engine.render_video(pdir, video, captions=not a.no_captions, workers=a.workers, crf=a.crf,
                             start=a.start, end=a.end)
    if video.stat().st_size > 28 * 1024 * 1024:  # chat attachments cap at 30MB; TikTok re-encodes anyway
        import subprocess
        share = out_dir / f"{name}_share.mp4"
        subprocess.run([media.ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(video), "-c:v", "libx264",
                        "-preset", "slow", "-crf", "24", "-maxrate", "2.4M", "-bufsize", "4.8M",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "copy", str(share)], check=True)
        print(f"      {share}  (smaller copy for sending)")
    export.write_script(tl, out_dir / "script.md")
    export.write_srt(tl, out_dir / "captions.srt")
    export.write_credits(tl, out_dir / "credits.md")
    export.write_post(tl, out_dir / "tiktok_post.txt")
    (out_dir / "queue_payload.json").write_text(json.dumps(export.queue_payload(tl), indent=2))
    print(f"Done: {video}  ({tl.duration:.1f}s)")
    print(f"      {out_dir / 'script.md'}")
    if tl.ctx.warnings:
        print("Warnings:\n  " + "\n  ".join(tl.ctx.warnings))


def cmd_apply_edits(a):
    """Apply script edits (from the Shorts Queue page) to storyboard `say` lines."""
    pdir = project(a.slug)
    edits = json.loads(Path(a.edits).read_text())
    edits = edits.get("script_edits", edits) if isinstance(edits, dict) else edits
    sb_path = pdir / "storyboard.json"
    sb = json.loads(sb_path.read_text())
    changed = 0
    for e in edits:
        spec = sb["scenes"][int(e["scene"])]
        say = spec.get("say", [])
        say = [say] if isinstance(say, str) else list(say)
        j, text = int(e.get("line", 0)), str(e["text"]).strip()
        if j < len(say) and say[j] != text:
            print(f"  scene {e['scene'] + 1}: {say[j]!r}\n        -> {text!r}")
            say[j] = text
            changed += 1
        spec["say"] = [s for s in say if s]
    sb_path.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
    print(f"{changed} line(s) changed. Check timing and voice with `script`, then `render`.")


def cmd_script(a):
    pdir = project(a.slug)
    out_dir = pdir / "output"
    out_dir.mkdir(exist_ok=True)
    tl = engine.Timeline(pdir)
    checks.report(tl)
    export.write_script(tl, out_dir / "script.md")
    export.write_srt(tl, out_dir / "captions.srt")
    export.write_post(tl, out_dir / "tiktok_post.txt")
    (out_dir / "queue_payload.json").write_text(json.dumps(export.queue_payload(tl), indent=2))
    print(f"{tl.duration:.1f}s, {len(tl.cues)} lines -> {out_dir / 'script.md'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor", help="check network access and API keys")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("new", help="create a project from a Substack URL")
    p.add_argument("url")
    p.add_argument("--manual", action="store_true", help="skip fetching; build article.json from flags")
    p.add_argument("--title")
    p.add_argument("--subtitle")
    p.add_argument("--authors", nargs="*")
    p.add_argument("--date", help="ISO date, e.g. 2026-03-18")
    p.add_argument("--text", help="path to pasted article text (markdown)")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("search", help="search for real photos / footage")
    p.add_argument("slug")
    p.add_argument("query")
    p.add_argument("--pixabay", action="store_true", help="search Pixabay (needs PIXABAY_API_KEY)")
    p.add_argument("--pexels", action="store_true", help="search Pexels (needs PEXELS_API_KEY)")
    p.add_argument("--video", action="store_true", help="search video clips (Pexels)")
    p.add_argument("-n", type=int, default=12)
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("pick", help="download a candidate from the last search")
    p.add_argument("slug")
    p.add_argument("n", type=int)
    p.add_argument("--as", dest="as_name", required=True)
    p.set_defaults(fn=cmd_pick)

    p = sub.add_parser("plan", help="rank the photos this story needs + fetch candidates")
    p.add_argument("slug")
    p.add_argument("--top", type=int, default=12, help="number of photo subjects")
    p.add_argument("--per", type=int, default=6, help="candidates per subject")
    p.add_argument("--no-fetch", action="store_true", help="rank subjects only, no image search")
    p.add_argument("--only", help="comma-separated subject keys to (re)fetch, e.g. congress,housing")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("use", help="save candidate n of a visual-plan subject into media/")
    p.add_argument("slug")
    p.add_argument("key", help="subject key from visual_plan.md, e.g. congress, place_los_angeles")
    p.add_argument("n", type=int)
    p.add_argument("--as", dest="as_name", required=True)
    p.set_defaults(fn=cmd_use)

    p = sub.add_parser("autofill", help="fetch photos for every scene that has a `query` but no file")
    p.add_argument("slug")
    p.add_argument("--force", action="store_true", help="re-fetch even if the file exists")
    p.set_defaults(fn=cmd_autofill)

    p = sub.add_parser("grab", help="save an 'in the news' item: YouTube link, report PDF, image URL or screenshot")
    p.add_argument("slug")
    p.add_argument("source", help="URL or local file")
    p.add_argument("--as", dest="as_name", required=True)
    p.add_argument("--outlet", help="e.g. 'The Washington Post'")
    p.add_argument("--date", help="as shown on screen, e.g. 'Jul 8, 2026'")
    p.add_argument("--credit", help="credit line override")
    p.set_defaults(fn=cmd_grab)

    p = sub.add_parser("clip", help="screenshot a news article's headline (or make a quoted headline card)")
    p.add_argument("slug")
    p.add_argument("url")
    p.add_argument("--as", dest="as_name", required=True)
    p.add_argument("--outlet", help="override the outlet name (e.g. the original publisher of a syndicated story)")
    p.add_argument("--date", help="override the date shown")
    p.add_argument("--headline", help="headline for a quoted card when the site can't be clipped")
    p.add_argument("--dek", help="subhead for a quoted card")
    p.set_defaults(fn=cmd_clip)

    p = sub.add_parser("voice", help="sync a recorded voiceover to the video (or --off to remove it)")
    p.add_argument("slug")
    p.add_argument("audio", nargs="?", help="the recording (.m4a, .mp3, .wav, .mp4, .webm)")
    p.add_argument("--off", action="store_true")
    p.add_argument("--max-gap", type=float, default=0.5, help="longest pause kept between lines in seconds (0 = keep all)")
    p.add_argument("--ext", help="original file extension for a base64 upload from the queue page (e.g. m4a)")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("music", help="pick or change the background music (a fresh track per video)")
    p.add_argument("slug")
    p.add_argument("--title", help="use a specific Incompetech track")
    p.add_argument("--reroll", action="store_true", help="pick a different track")
    p.add_argument("--start", type=float, help="seconds before the music comes in (default 5)")
    p.add_argument("--level", type=float, help="music bed loudness in LUFS (default -30; higher = louder)")
    p.add_argument("--list", action="store_true", help="show the eligible tracks and where they've been used")
    p.add_argument("--off", action="store_true", help="no music for this video")
    p.set_defaults(fn=cmd_music)

    p = sub.add_parser("stills", help="render a key-frame contact sheet")
    p.add_argument("slug")
    p.add_argument("--no-captions", action="store_true")
    p.set_defaults(fn=cmd_stills)

    p = sub.add_parser("frame", help="render a single frame at time t")
    p.add_argument("slug")
    p.add_argument("t", type=float)
    p.set_defaults(fn=cmd_frame)

    p = sub.add_parser("script", help="write script.md / captions.srt without rendering video")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_script)

    p = sub.add_parser("apply-edits", help="apply script edits (JSON from the Shorts Queue) to the storyboard")
    p.add_argument("slug")
    p.add_argument("edits", help="JSON file: [{scene, line, text}] or a queue document with script_edits")
    p.set_defaults(fn=cmd_apply_edits)

    p = sub.add_parser("render", help="render the final video + script")
    p.add_argument("slug")
    p.add_argument("--no-captions", action="store_true", help="omit burned-in captions")
    p.add_argument("--force", action="store_true", help="render even if house rules fail")
    p.add_argument("--workers", type=int)
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--end", type=float)
    p.set_defaults(fn=cmd_render)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
