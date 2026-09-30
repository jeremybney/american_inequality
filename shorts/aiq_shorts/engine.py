"""Timeline, captions, and encoding.

A storyboard is a list of scenes; each scene lists the lines the narrator will
`say`. Scene length is derived from those lines at the narration pace (wpm), so
the finished video is already timed to the script you'll record.
"""
import json
import multiprocessing as mp
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

from . import gfx as G
from . import media as M
from . import theme as T
from .scenes import SCENES


class Context:
    def __init__(self, project_dir, storyboard):
        self.project_dir = Path(project_dir)
        self.storyboard = storyboard
        self.media_dir = self.project_dir / "media"
        self.cache_dir = self.project_dir / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        art_path = self.project_dir / "article.json"
        article = json.loads(art_path.read_text()) if art_path.exists() else {}
        article.update(storyboard.get("article", {}))
        article.setdefault("publication", T.BRAND)
        self.article = article
        self.credits = M.load_credits(self.media_dir)
        td = storyboard.get("today")
        self.today = date.fromisoformat(td) if td else date.today()
        self.warnings = []
        self.quiet = False

    def media_path(self, name):
        if not name:
            return None
        p = Path(name)
        return p if p.is_absolute() else self.media_dir / p

    def credit_for(self, name):
        entry = self.credits.get(Path(name).name) if name else None
        return entry.get("credit") if isinstance(entry, dict) else entry

    def warn(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)
            if not self.quiet:
                print(f"  ! {msg}", file=sys.stderr)


def say_lines(spec):
    lines = spec.get("say", [])
    return [lines] if isinstance(lines, str) else list(lines)


def line_seconds(text, wpm):
    words = len(text.split())
    return max(1.1, words * 60.0 / wpm + 0.25)


class Timeline:
    def __init__(self, project_dir, captions=True, quiet=False):
        self.project_dir = Path(project_dir)
        self.storyboard = json.loads((self.project_dir / "storyboard.json").read_text())
        self.ctx = Context(project_dir, self.storyboard)
        self.ctx.quiet = quiet
        self.captions = captions
        self.wpm = self.storyboard.get("wpm", T.DEFAULT_WPM)
        self.draft = self.storyboard.get("draft", False)
        self.scenes, self.spans, self.cues = [], [], []
        t = 0.0
        for i, spec in enumerate(self.storyboard["scenes"]):
            cls = SCENES.get(spec["type"])
            if not cls:
                raise SystemExit(f"Scene {i}: unknown type {spec['type']!r}. Options: {sorted(SCENES)}")
            lines = say_lines(spec)
            natural = [line_seconds(l, self.wpm) for l in lines]
            dur = sum(natural) + spec.get("hold", 0.35)
            dur = max(dur, spec.get("min_duration", 2.0))
            if "duration" in spec:
                dur = float(spec["duration"])
            ct = t + spec.get("lead", 0.15)
            for line, nd in zip(lines, natural):
                self.cues.append({"scene": i, "start": ct, "end": min(ct + nd, t + dur), "text": line})
                ct += nd
            scene = cls(spec, self.ctx)
            scene.prepare(dur)
            self.scenes.append(scene)
            self.spans.append((t, t + dur))
            t += dur
        # captions stay up until the next one starts (no flicker between lines)
        for a, b in zip(self.cues, self.cues[1:]):
            if a["scene"] == b["scene"]:
                a["end"] = b["start"]
            else:
                a["end"] = self.spans[a["scene"]][1]
        if self.cues:
            self.cues[-1]["end"] = self.spans[self.cues[-1]["scene"]][1]
        self.duration = t
        self._cap_cache = {}

    # -- frame rendering ------------------------------------------------------
    def scene_at(self, t):
        for i, (a, b) in enumerate(self.spans):
            if a <= t < b:
                return i
        return len(self.spans) - 1

    def frame(self, t):
        i = self.scene_at(t)
        a, _ = self.spans[i]
        local = t - a
        img = self.scenes[i].render(local)
        fade = self.storyboard["scenes"][i].get("crossfade", T.CROSSFADE)
        if i > 0 and local < fade:
            prev = self.scenes[i - 1]
            prev_img = prev.render(prev.dur + local)
            img = Image.blend(prev_img, img, G.ease_in_out(local / fade))
        self.overlay(img, t, i)
        return img

    def caption_layer(self, text, dark):
        key = (text, dark)
        if key not in self._cap_cache:
            f = G.font("sans", T.CAPTION_SIZE)
            lines = G.balanced(G.wrap, text, f, T.CAPTION_WIDTH)
            self._cap_cache[key] = G.shadowed_text_layer(
                lines, f, T.TITLE, T.CAPTION_SIZE * 1.25, T.CAPTION_WIDTH,
                shadow=T.INK, shadow_alpha=0.9 if dark else 0.45, blur=12 if dark else 8)
        return self._cap_cache[key]

    def overlay(self, img, t, i):
        scene = self.scenes[i]
        dark = scene.dark
        d = ImageDraw.Draw(img, "RGBA")
        if self.captions:
            cue = next((c for c in self.cues if c["start"] <= t < c["end"]), None)
            if cue:
                a = G.ease_out(G.prog(t, cue["start"], T.CAPTION_FADE))
                lay = self.caption_layer(cue["text"], dark)
                G.paste_rgba(img, lay, ((T.W - lay.width) / 2, T.CAPTION_TOP - 30), a)
        src = scene.source_line()
        if src:
            f = G.font("mono_med", 21)
            col = G.rgba(T.TITLE, 0.62) if dark else G.rgba(T.NAVY, 0.85)
            y = T.SOURCE_Y
            for line in G.wrap(src, f, T.W - 160)[:3]:
                G.draw_centered(d, T.W / 2, y, line, f, col)
                y += 28
        if self.draft:
            f = G.font("mono", 30)
            msg = self.storyboard.get("draft_label", "DRAFT · VERIFY NUMBERS")
            w = f.getlength(msg)
            d.rounded_rectangle((T.W / 2 - w / 2 - 18, 120, T.W / 2 + w / 2 + 18, 172), 8,
                                fill=G.rgba(T.YELLOW, 0.92))
            d.text((T.W / 2 - w / 2, 128), msg, font=f, fill=G.rgba(T.NAVY))


# -- parallel encode ------------------------------------------------------------

_TL = None


def _init_worker(project_dir, captions):
    global _TL
    _TL = Timeline(project_dir, captions, quiet=True)


def _render_frame(n):
    return _TL.frame(n / T.FPS).tobytes()


def render_video(project_dir, out_path, captions=True, workers=None, crf=18, start=0.0, end=None):
    tl = Timeline(project_dir, captions)  # also pre-extracts any video frames
    end = tl.duration if end is None else min(end, tl.duration)
    frames = range(int(start * T.FPS), int(end * T.FPS))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [M.ffmpeg_exe(), "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{T.W}x{T.H}", "-r", str(T.FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
           "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "128k", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    workers = workers or max(1, (os.cpu_count() or 2))
    total = len(frames)
    with mp.get_context("fork").Pool(workers, _init_worker, (str(project_dir), captions)) as pool:
        for k, buf in enumerate(pool.imap(_render_frame, frames, chunksize=6)):
            proc.stdin.write(buf)
            if k % (T.FPS * 5) == 0:
                print(f"  frame {k}/{total}  ({k / T.FPS:.0f}s of {total / T.FPS:.0f}s)", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    return tl


def render_stills(project_dir, out_path, captions=True, per_scene=2):
    """Contact sheet of key frames from every scene, for fast visual QA."""
    tl = Timeline(project_dir, captions)
    shots = []
    for i, (a, b) in enumerate(tl.spans):
        fracs = [0.9] if per_scene == 1 else [0.35, 0.92]
        for fr in fracs:
            t = a + (b - a) * fr
            shots.append((i, t, tl.frame(t)))
    tw, th = 270, 480
    cols = 8
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 34)), (15, 15, 15))
    d = ImageDraw.Draw(sheet)
    f = G.font("mono", 20)
    for k, (i, t, im) in enumerate(shots):
        x, y = (k % cols) * tw, (k // cols) * (th + 34)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y))
        d.text((x + 6, y + th + 6), f"#{i} {tl.storyboard['scenes'][i]['type']} {t:.1f}s", font=f, fill=T.YELLOW)
    sheet.save(out_path)
    return tl


def render_frame_png(project_dir, t, out_path, captions=True):
    tl = Timeline(project_dir, captions)
    tl.frame(t).save(out_path)
    return tl
