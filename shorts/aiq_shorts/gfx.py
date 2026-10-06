"""Drawing primitives: fonts, text layout, easing, number formatting, backgrounds."""
from functools import lru_cache
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import theme as T


# --- Fonts & text -------------------------------------------------------------

@lru_cache(maxsize=256)
def font(key, size):
    return ImageFont.truetype(str(T.FONT_DIR / T.FONTS[key]), int(size))


def text_w(text, f):
    return f.getlength(text)


def text_box(text, f):
    """(width, ascent-to-baseline height) using the font's cap metrics."""
    l, t, r, b = f.getbbox(text or "Hg")
    return r - l, b - t


def wrap(text, f, max_w):
    """Greedy word wrap. Returns a list of lines."""
    lines, cur = [], ""
    for word in str(text).split():
        trial = f"{cur} {word}".strip()
        if cur and f.getlength(trial) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def balanced(wrap_fn, content, f, max_w):
    """Re-wrap at the narrowest width that keeps the same line count, so lines
    come out even instead of leaving one orphaned word on the last line."""
    lines = wrap_fn(content, f, max_w)
    if len(lines) < 2:
        return lines
    lo, hi = max_w * 0.4, max_w
    for _ in range(12):
        mid = (lo + hi) / 2
        if len(wrap_fn(content, f, mid)) > len(lines):
            lo = mid
        else:
            hi = mid
    return wrap_fn(content, f, hi + 1)


def wrap_rich(segments, f, max_w):
    """Wrap coloured segments [(text, rgb), ...] into lines of [(word, rgb), ...]."""
    words = []
    for text, col in segments:
        for w in str(text).split():
            words.append((w, col))
    lines, cur, cur_w = [], [], 0.0
    space = f.getlength(" ")
    for w, col in words:
        ww = f.getlength(w)
        add = ww if not cur else space + ww
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [(w, col)], ww
        else:
            cur.append((w, col))
            cur_w += add
    if cur:
        lines.append(cur)
    return lines


def draw_centered(draw, cx, y, text, f, fill):
    draw.text((cx - f.getlength(text) / 2, y), text, font=f, fill=fill)


def rgba(rgb, a=1.0):
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]), int(max(0, min(1, a)) * 255))


def mix(c1, c2, t):
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


# --- Easing -----------------------------------------------------------------------

def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def prog(t, start, dur):
    """Linear progress of an animation that starts at `start` and lasts `dur`."""
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return clamp01((t - start) / dur)


def ease_out(x):
    return 1 - (1 - clamp01(x)) ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_back(x, s=1.4):
    x = clamp01(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


# --- Numbers ------------------------------------------------------------------------

def fmt_num(value, decimals=0, prefix="", suffix="", commas=True):
    if decimals:
        body = f"{value:,.{decimals}f}" if commas else f"{value:.{decimals}f}"
    else:
        body = f"{int(round(value)):,}" if commas else f"{int(round(value))}"
    neg = body.startswith("-")
    body = body.lstrip("-")
    return f"{'-' if neg else ''}{prefix}{body}{suffix}"


def count_value(target, p, start=0.0):
    """Value shown by a count-up at eased progress p (fast start, soft landing)."""
    return start + (target - start) * ease_out(p)


# --- Backgrounds ------------------------------------------------------------------

@lru_cache(maxsize=4)
def orange_background(variant="orange"):
    """Brand orange with a soft radial vignette and fine film grain.

    The grain keeps the flat colour from banding on phones and makes it read
    as print rather than a flat digital fill.
    """
    yy, xx = np.mgrid[0:T.H, 0:T.W].astype(np.float32)
    cx, cy = T.W * 0.5, T.H * 0.42
    d = np.sqrt(((xx - cx) / (T.W * 0.9)) ** 2 + ((yy - cy) / (T.H * 0.75)) ** 2)
    d = np.clip(d, 0, 1) ** 1.8
    if variant == "navy":
        inner, outer = np.array(T.NAVY, np.float32), np.array(T.INK, np.float32)
    else:
        inner, outer = np.array(T.ORANGE, np.float32), np.array(T.ORANGE_DEEP, np.float32)
    img = inner[None, None, :] * (1 - d[..., None]) + outer[None, None, :] * d[..., None]
    rng = np.random.default_rng(7)
    img += rng.normal(0, 3.2, size=(T.H, T.W, 1)).astype(np.float32)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def bottom_scrim(strength=0.85, start=0.52):
    """Vertical gradient (RGBA) that darkens the lower part of a photo for captions."""
    return _scrim(round(strength, 3), round(start, 3))


@lru_cache(maxsize=8)
def _scrim(strength, start):
    ys = np.linspace(0, 1, T.H, dtype=np.float32)
    a = np.clip((ys - start) / (1 - start), 0, 1) ** 1.3 * strength
    top = np.clip((0.22 - ys) / 0.22, 0, 1) ** 1.5 * 0.45  # light top shade for headlines/UI
    a = np.maximum(a, top)
    arr = np.zeros((T.H, T.W, 4), np.uint8)
    arr[..., :3] = T.INK
    arr[..., 3] = (a * 255).astype(np.uint8)[:, None]
    return Image.fromarray(arr, "RGBA")


# --- Shapes -------------------------------------------------------------------------

def shadowed_text_layer(lines, f, fill, line_h, max_w, align="center",
                        shadow=(0, 0, 0), shadow_alpha=0.55, blur=10, pad=30):
    """Render wrapped lines to a transparent RGBA layer with a soft drop shadow.

    `lines` is a list of strings or of [(word, rgb)] rich lines.
    """
    h = int(line_h * len(lines) + pad * 2)
    w = int(max_w + pad * 2)
    txt = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    for i, line in enumerate(lines):
        y = pad + i * line_h
        if isinstance(line, str):
            lw = f.getlength(line)
            x = pad + (max_w - lw) / 2 if align == "center" else pad
            d.text((x, y), line, font=f, fill=rgba(fill))
        else:
            space = f.getlength(" ")
            lw = sum(f.getlength(wd) for wd, _ in line) + space * (len(line) - 1)
            x = pad + (max_w - lw) / 2 if align == "center" else pad
            for wd, col in line:
                d.text((x, y), wd, font=f, fill=rgba(col))
                x += f.getlength(wd) + space
    if shadow_alpha <= 0:
        return txt
    alpha = txt.split()[3]
    sh = Image.new("RGBA", (w, h), rgba(shadow, 0))
    sh.putalpha(alpha.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * shadow_alpha)))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(sh, (0, 4))
    out.alpha_composite(txt)
    return out


def paste_rgba(base, layer, xy, alpha=1.0):
    """Alpha-composite an RGBA layer onto an RGB base image in place."""
    if alpha <= 0:
        return
    if alpha < 1:
        layer = layer.copy()
        a = layer.split()[3].point(lambda v: int(v * alpha))
        layer.putalpha(a)
    x, y = int(round(xy[0])), int(round(xy[1]))
    base.paste(layer, (x, y), layer)


def rotated_paste(base, layer, center, angle, alpha=1.0, scale=1.0):
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))),
                             Image.BICUBIC)
    rot = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    paste_rgba(base, rot, (center[0] - rot.width / 2, center[1] - rot.height / 2), alpha)


def soft_shadow(size, radius=24, blur=26, alpha=0.35, color=(0, 0, 0)):
    w, h = size
    pad = blur * 2
    im = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((pad, pad, pad + w, pad + h), radius, fill=rgba(color, alpha))
    return im.filter(ImageFilter.GaussianBlur(blur)), pad


def seeded(seed):
    return random.Random(seed)


def lerp(a, b, t):
    return a + (b - a) * t


def angle_pt(cx, cy, r, deg):
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)
