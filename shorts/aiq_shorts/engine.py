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


TIMING_KEYS = {"at", "chips_at", "badge_at", "fill_at", "note_at", "zoom_at", "annotation_at", "play_at",
               "big_at", "draw_at", "stagger"}


def scale_timing(spec, k):
    """Copy of a scene spec with its reveal times (`at`, `*_at`, `stagger`) scaled by k."""
    if abs(k - 1) < 0.03:
        return spec
    def walk(v):
        if isinstance(v, dict):
            return {key: (val * k if key in TIMING_KEYS and isinstance(val, (int, float)) and val >= 0 else walk(val))
                    for key, val in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v
    return walk(spec)


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
        specs = self.storyboard["scenes"]
        # 1) estimated timing from the text (narration pace)
        est_spans, est_cues, t = [], [], 0.0
        for i, spec in enumerate(specs):
            if spec["type"] not in SCENES:
                raise SystemExit(f"Scene {i}: unknown type {spec['type']!r}. Options: {sorted(SCENES)}")
            lines = say_lines(spec)
            natural = [line_seconds(l, self.wpm) for l in lines]
            dur = sum(natural) + spec.get("hold", self.storyboard.get("hold", 0.35))
            dur = max(dur, spec.get("min_duration", 2.0))
            if "duration" in spec:
                dur = float(spec["duration"])
            ct = t + spec.get("lead", 0.15)
            for line, nd in zip(lines, natural):
                est_cues.append({"scene": i, "start": ct, "end": min(ct + nd, t + dur), "text": line})
                ct += nd
            est_spans.append((t, t + dur))
            t += dur
        # 2) a synced voiceover replaces the estimate with the author's real delivery
        self.voice = self._voice_timing(specs)
        if self.voice:
            spans, cues = self.voice["spans"], self.voice["cues"]
        else:
            spans, cues = est_spans, est_cues
        for i, spec in enumerate(specs):
            dur = spans[i][1] - spans[i][0]
            est = est_spans[i][1] - est_spans[i][0]
            if self.voice and est > 0:  # move each scene's reveals in proportion to the real pace
                spec = scale_timing(spec, max(0.6, min(1.8, dur / est)))
            scene = SCENES[spec["type"]](spec, self.ctx)
            scene.prepare(dur)
            self.scenes.append(scene)
        self.spans, self.cues = list(spans), [dict(c) for c in cues]
        t = self.spans[-1][1] if self.spans else 0.0
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

    def _voice_timing(self, specs):
        """Scene spans and caption cues from a synced voiceover, if one matches this script."""
        vo = self.storyboard.get("voiceover")
        if not vo or not vo.get("cues"):
            return None
        current = [(i, j, text) for i, s in enumerate(specs) for j, text in enumerate(say_lines(s))]
        recorded = [(c["scene"], c["line"], c["text"]) for c in vo["cues"]]
        if current != recorded:
            self.ctx.warn("the script changed since the voiceover was synced; re-record or re-run `voice` "
                          "(using estimated timing for now)")
            return None
        if not (self.ctx.media_dir / vo["clean"]).exists():
            self.ctx.warn(f"voiceover audio {vo['clean']} is missing; using estimated timing")
            return None
        first = {}
        for c in vo["cues"]:
            first.setdefault(c["scene"], c["start"])
        starts = []
        for i in range(len(specs)):
            if i == 0:
                starts.append(0.0)
            elif i in first:
                starts.append(max(starts[-1] + 0.6, first[i] - 0.12))
            else:  # a silent scene borrows a short slot (keep these rare with a voiceover)
                starts.append(starts[-1] + float(specs[i].get("duration", 1.5)))
        end = max(vo["cues"][-1]["end"] + 1.2, float(vo.get("duration", 0)) + 0.4)
        spans = [(s, starts[k + 1] if k + 1 < len(starts) else end) for k, s in enumerate(starts)]
        cues = [{"scene": c["scene"], "start": c["start"], "end": c["end"], "text": c["text"]} for c in vo["cues"]]
        return {"spans": spans, "cues": cues, "audio": self.ctx.media_dir / vo["clean"]}

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
            # long lines step the size down so the caption stays within three lines
            for size in (T.CAPTION_SIZE, T.CAPTION_SIZE - 4, T.CAPTION_SIZE - 8):
                f = G.font("sans", size)
                lines = G.balanced(G.wrap, text, f, T.CAPTION_WIDTH)
                if len(lines) <= 3:
                    break
            self._cap_cache[key] = G.shadowed_text_layer(
                lines, f, T.TITLE, size * 1.25, T.CAPTION_WIDTH,
                shadow=T.INK, shadow_alpha=0.9 if dark else 0.45, blur=12 if dark else 8)
        return self._cap_cache[key]

    def overlay(self, img, t, i):
        scene = self.scenes[i]
        dark = scene.dark
        d = ImageDraw.Draw(img, "RGBA")
        cap_bottom = 0
        if self.captions:
            cue = next((c for c in self.cues if c["start"] <= t < c["end"]), None)
            if cue:
                a = G.ease_out(G.prog(t, cue["start"], T.CAPTION_FADE))
                lay = self.caption_layer(cue["text"], dark)
                G.paste_rgba(img, lay, ((T.W - lay.width) / 2, T.CAPTION_TOP - 30), a)
                cap_bottom = T.CAPTION_TOP - 30 + lay.height - 18
        src = scene.source_line()
        if src:
            f = G.font("mono_med", 21)
            col = G.rgba(T.TITLE, 0.62) if dark else G.rgba(T.NAVY, 0.85)
            y = max(T.SOURCE_Y, cap_bottom + 12)  # never under the caption
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
    # --- audio: the author's voice (if synced) over a soft music bed (if chosen) ---
    music = tl.storyboard.get("music")
    bed = None
    if music and music.get("off"):
        music = None
    if music and (tl.ctx.media_dir / music.get("file", "")).exists():
        from . import music as MU
        k = int(music.get("start_scene", 3)) - 1  # music comes in on this scene (1-based)
        start_t = tl.spans[min(max(k, 0), len(tl.spans) - 1)][0] if "start" not in music else float(music["start"])
        bed = MU.build_bed(project_dir, music, tl.duration, tl.ctx.cache_dir / "music_bed.wav", start=start_t)
    elif music:
        tl.ctx.warn(f"music file {music.get('file')} is missing; run `music <slug>` (rendering without music)")
    voice_in = (["-i", str(tl.voice["audio"])] if tl.voice
                else ["-f", "lavfi", "-t", f"{tl.duration:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"])
    audio_in, graph = list(voice_in), []
    if bed:
        audio_in += ["-i", str(bed)]
        if tl.voice:
            # the voice ducks the music a little more while it speaks; music returns in the gaps
            graph = ["-filter_complex",
                     "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,apad,asplit=2[v1][v2];"
                     "[2:a][v2]sidechaincompress=threshold=0.04:ratio=4:attack=40:release=600[m];"
                     "[v1][m]amix=inputs=2:duration=longest:normalize=0[a]", "-map", "0:v", "-map", "[a]"]
        else:
            graph = ["-map", "0:v", "-map", "2:a"]
    else:
        graph = ["-af", "apad,aformat=channel_layouts=stereo", "-map", "0:v", "-map", "1:a"]
    if start:  # partial renders: start every audio input at the same point as the video
        shifted = []
        for k, tok in enumerate(audio_in):
            if tok == "-i" and audio_in[k - 1:k] != ["lavfi"]:
                shifted += ["-ss", f"{start:.3f}"]
            shifted.append(tok)
        audio_in = shifted
    cmd = [M.ffmpeg_exe(), "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{T.W}x{T.H}", "-r", str(T.FPS), "-i", "-",
           *audio_in, *graph, "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "192k", str(out_path)]
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
