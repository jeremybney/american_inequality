"""The author on camera: their recording, background removed, composited into the video.

The author films themselves reading the script (phone, vertical, head and hands in frame).
`matte()` removes the background with Robust Video Matting (a person-matting model built for
video: it keeps hair and moving hands and stays steady frame to frame) and caches the cut-out as
JPEG colour + PNG alpha per frame. `Presenter.layer(t)` returns the cut-out for video time t,
and the engine pastes it between the scene and the captions, so captions always sit on top of
the person and never behind them.

Storyboard:
  "presenter": {"file": "presenter.mp4", "position": "right", "height": 0.62, "x": 0.98}
Per scene:
  "presenter": false                      hide the person for this scene (a chart that needs the room)
  "presenter": {"position": "left"}       override placement for this scene
  "presenter": {"size": "full"}           the person large and centred (a hook or a direct-to-camera line);
                                          the top of the frame stays clear for the headline
Charts, maps and the article card hide the person by default (the data needs the whole frame);
give such a scene "presenter": {...} to show them anyway.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from . import media as M
from . import theme as T

MODEL_URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.torchscript"
MODEL = Path(__file__).resolve().parent.parent / "assets" / ".rvm_mobilenetv3.torchscript"  # not committed
WORK_W, WORK_H = 540, 960          # matting runs at half of 1080x1920; the matte is upscaled
STORE_H = 1400                     # cached cut-out height (enough for "full" without visible softness)


def _model():
    import torch
    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        MODEL.write_bytes(M.http_get(MODEL_URL, timeout=120, retries=3))
    return torch.jit.load(str(MODEL)).eval()


def _probe(path):
    out = subprocess.run([M.ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True).stderr
    import re
    m = re.search(r", (\d{2,5})x(\d{2,5})[, ]", out)
    fps = re.search(r"(\d+(?:\.\d+)?) fps", out)
    return (int(m.group(1)), int(m.group(2))) if m else (1080, 1920), float(fps.group(1)) if fps else 30.0


def matte(src, out_dir, fps=None, cuts=None, progress=True):
    """Cut the person out of `src` into out_dir/{c,a}_NNNNN.{jpg,png}, at the video's frame rate
    (T.FPS) so frame n is time n / FPS. `cuts` are (start, end) seconds removed from the
    recording (the same pause cuts the voice sync made), so picture and voice stay in lock-step."""
    import torch
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fps = fps or T.FPS
    (w, h), _ = _probe(src)
    sh = STORE_H
    sw = int(round(w * sh / h / 2)) * 2
    vf = f"fps={fps},scale={WORK_W}:{int(round(WORK_W * h / w / 2)) * 2}"
    if cuts:  # keep only the parts between cuts, back to back
        keep, pos = [], 0.0
        for a, b in sorted(cuts):
            keep.append(f"between(t,{pos:.3f},{a:.3f})")
            pos = b
        keep.append(f"gte(t,{pos:.3f})")
        vf = f"select='{'+'.join(keep)}',setpts=N/FRAME_RATE/TB," + vf
    ww, wh = WORK_W, int(round(WORK_W * h / w / 2)) * 2
    full = subprocess.Popen([M.ffmpeg_exe(), "-loglevel", "error", "-i", str(src), "-vf",
                             vf.replace(f"scale={ww}:{wh}", f"scale={sw}:{sh}"), "-f", "rawvideo",
                             "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    small = subprocess.Popen([M.ffmpeg_exe(), "-loglevel", "error", "-i", str(src), "-vf", vf, "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    model, rec, n = _model(), [None] * 4, 0
    with torch.no_grad():
        while True:
            b = small.stdout.read(ww * wh * 3)
            fb = full.stdout.read(sw * sh * 3)
            if len(b) < ww * wh * 3 or len(fb) < sw * sh * 3:
                break
            x = torch.from_numpy(np.frombuffer(b, np.uint8).reshape(wh, ww, 3).copy()).permute(2, 0, 1).float().div(255)[None]
            _fgr, pha, *rec = model(x, *rec, downsample_ratio=0.4)
            alpha = Image.fromarray((pha[0, 0].numpy() * 255).astype(np.uint8)).resize((sw, sh), Image.BILINEAR)
            Image.fromarray(np.frombuffer(fb, np.uint8).reshape(sh, sw, 3)).save(out_dir / f"c_{n:05d}.jpg", quality=90)
            alpha.save(out_dir / f"a_{n:05d}.png", optimize=True)
            n += 1
            if progress and n % (fps * 5) == 0:
                print(f"  matted {n / fps:.0f}s", flush=True)
    full.wait()
    small.wait()
    (out_dir / "meta.json").write_text(json.dumps({"frames": n, "fps": fps, "width": sw, "height": sh, "src": str(src)}))
    return n


class Presenter:
    """The cut-out for any video time, placed per the storyboard."""

    def __init__(self, frames_dir, spec):
        self.dir = Path(frames_dir)
        self.meta = json.loads((self.dir / "meta.json").read_text())
        self.spec = spec or {}

    # charts and maps need the whole frame: the person steps aside unless a scene asks for them
    HIDE_ON = {"hbars", "vbars", "big_number", "waffle", "stacked", "line", "then_now", "checklist",
               "figure", "map", "article_card"}

    def placement(self, scene_spec):
        p = dict(self.spec)
        sp = scene_spec.get("presenter")
        if sp is False or (sp is None and scene_spec.get("type") in self.HIDE_ON):
            return None
        if isinstance(sp, dict):
            p.update(sp)
        return p

    def layer(self, t, scene_spec, loop=False):
        """(RGBA image, (x, y)) for video time t, or None when hidden for this scene."""
        p = self.placement(scene_spec)
        if p is None:
            return None
        n = int(round(t * self.meta["fps"]))
        if loop:
            n %= self.meta["frames"]
        n = max(0, min(n, self.meta["frames"] - 1))
        img = Image.open(self.dir / f"c_{n:05d}.jpg").convert("RGB")
        img.putalpha(Image.open(self.dir / f"a_{n:05d}.png"))
        full = p.get("size") == "full"
        # "full" fills the lower frame and leaves the top quarter for the scene's headline
        if full:  # as wide as the screen, so where the camera's frame cuts the body is the screen edge
            w = T.W
            h = int(img.height * w / img.width)
        else:
            h = int(T.H * p.get("height", 0.62))
            w = int(img.width * h / img.height)
        img = img.resize((w, h), Image.LANCZOS)
        if full:  # a little low, so hair never reaches the headline and its tag
            x = (T.W - w) // 2
            return img, (x, T.H - h + int(T.H * p.get("drop", 0.08)))
        elif p.get("position", "right") == "left":
            x = int(T.W * (1 - p.get("x", 0.98))) - w // 6
        else:
            x = int(T.W * p.get("x", 0.98)) - w + w // 6
        return img, (x, T.H - h)
