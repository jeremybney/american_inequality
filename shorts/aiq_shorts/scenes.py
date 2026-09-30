"""Scene library. Each scene draws one beat of the video (captions are added by
the engine on top). Scene types mirror the visual vocabulary of the reference
videos: a real-photo hook, the article card, and a set of animated data
graphics on the brand-orange background.

Every scene is configured from a storyboard entry; see storyboard_reference.md.
"""
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import gfx as G
from . import media as M
from . import theme as T


# =============================================================================
# Base classes
# =============================================================================

class Scene:
    dark = False  # True when the background is a photo (captions styled for it)

    def __init__(self, spec, ctx):
        self.spec = spec
        self.ctx = ctx
        self.dur = 5.0

    def prepare(self, duration):
        self.dur = duration

    def source_line(self):
        return self.spec.get("source")

    def render(self, t):
        raise NotImplementedError

    # helpers -------------------------------------------------------------
    def at(self, key, default):
        """Timing value from the spec; negative numbers count back from the end."""
        v = self.spec.get(key, default)
        return self.dur + v if v < 0 else v


class ChartScene(Scene):
    """Orange background + optional title/subtitle, like Tal's chart beats."""

    def canvas(self, t):
        variant = self.spec.get("background", "orange")
        img = G.orange_background(variant).copy()
        d = ImageDraw.Draw(img, "RGBA")
        a = G.ease_out(G.prog(t, 0.0, 0.35))
        y = T.CHART_TITLE_Y
        title = self.spec.get("title")
        if title:
            f = G.font("sans", self.spec.get("title_size", 52))
            for line in G.wrap(title, f, T.W - 2 * T.MARGIN):
                G.draw_centered(d, T.W / 2, y, line, f, G.rgba(T.TITLE, a))
                y += f.size * 1.2
        sub = self.spec.get("subtitle")
        if sub:
            f = G.font("mono_semi", 28)
            for line in G.wrap(sub, f, T.W - 2 * T.MARGIN):
                G.draw_centered(d, T.W / 2, y + 6, line, f, G.rgba(T.NAVY, a))
                y += f.size * 1.35
        note = self.spec.get("note")
        if note:
            na = G.ease_out(G.prog(t, self.at("note_at", 0.8), 0.4))
            f = G.font("mono_med", 26)
            ny = self.spec.get("note_y", T.CHART_BOTTOM + 20)
            for line in G.wrap(note, f, T.W - 2 * T.MARGIN):
                G.draw_centered(d, T.W / 2, ny, line, f, G.rgba(T.NAVY, na))
                ny += f.size * 1.35
        return img, d


def fmt_from(spec, value, parent=None):
    """Format a number using prefix/suffix/decimals from a spec (falling back to parent)."""
    parent = parent or {}
    g = lambda k, dflt: spec.get(k, parent.get(k, dflt))  # noqa: E731
    return G.fmt_num(value * g("scale", 1), g("decimals", 0), g("prefix", ""), g("suffix", ""),
                     g("commas", True))


def rich_segments(text, highlight, base_col, hi_col):
    """Split `text` into coloured segments. Highlight with {braces} in the text
    or by passing the phrase to highlight separately."""
    segs = []
    if "{" in text:
        parts = text.replace("}", "{").split("{")
        for i, p in enumerate(parts):
            if p:
                segs.append((p, hi_col if i % 2 else base_col))
    else:
        segs.append((text, base_col))
    if highlight:
        segs.append((highlight, hi_col))
    return segs


def truncate_rich(lines, n):
    """Keep only the first n characters of rich lines (typewriter reveal)."""
    out, left = [], n
    for line in lines:
        cur = []
        for w, c in line:
            if left <= 0:
                break
            cur.append((w[:left], c))
            left -= len(w) + 1
        out.append(cur)
        if left <= 0:
            break
    return out


# =============================================================================
# Photo / video scenes
# =============================================================================

class PhotoScene(Scene):
    """Full-bleed real photo (slow Ken Burns) or video clip, with optional
    headline, brand chip and overlays (stamp, big stat, tag, callout)."""
    dark = True

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.media_name = spec.get("media")
        self.path = ctx.media_path(self.media_name) if self.media_name else None
        self.frames = None
        self.still = None

    def prepare(self, duration):
        super().prepare(duration)
        focus = tuple(self.spec.get("focus", (0.5, 0.5)))
        dim = self.spec.get("dim", 0.3)
        if self.path and self.path.exists() and M.is_video(self.path):
            cache = self.ctx.cache_dir / f"frames_{self.path.stem}_{self.spec.get('start', 0)}"
            self.frames = M.extract_video_frames(self.path, cache, duration + T.CROSSFADE,
                                                 self.spec.get("start", 0), focus)
            self.dim = dim
        elif self.path and self.path.exists():
            self.still = M.load_still(str(self.path), focus, dim, self.spec.get("blur", 0))
        else:
            self.ctx.warn(f"media not found for scene: {self.media_name!r} (placeholder used)")
            self.still = M.fallback_backdrop(f"add media: {self.media_name or 'none'}")

    def source_line(self):
        parts = []
        credit = self.spec.get("credit") or self.ctx.credit_for(self.media_name)
        if credit:
            parts.append(credit)
        if self.spec.get("source"):
            parts.append(self.spec["source"])
        return " · ".join(parts) or None

    def background(self, t):
        p = G.clamp01(t / max(self.dur, 0.01))
        if self.frames:
            idx = min(int(t * T.FPS), len(self.frames) - 1)
            fr = Image.open(self.frames[idx]).convert("RGB")
            fr = M.grade(fr, self.dim)
            if self.spec.get("blur"):
                fr = fr.filter(ImageFilter.GaussianBlur(self.spec["blur"]))
            z = self.spec.get("zoom", [1.0, 1.05])
            s = z[0] + (z[1] - z[0]) * p
            if abs(s - 1) > 1e-3:
                w, h = T.W / s, T.H / s
                fr = fr.resize((T.W, T.H), Image.BILINEAR,
                               box=((T.W - w) / 2, (T.H - h) / 2, (T.W + w) / 2, (T.H + h) / 2))
            return fr
        zoom = self.spec.get("zoom", [1.0, 1.12])
        pan = self.spec.get("pan", [[0.5, 0.5], [0.5, 0.5]])
        return M.kenburns_frame(self.still, G.ease_in_out(p) * 0.3 + p * 0.7, zoom, pan)

    def render(self, t):
        img = self.background(t)
        if self.spec.get("scrim", True):
            G.paste_rgba(img, G.bottom_scrim(self.spec.get("scrim_strength", 0.85)), (0, 0))
        d = ImageDraw.Draw(img, "RGBA")
        overlays = self.spec.get("overlays", [])
        for ov in overlays:  # traced lines sit under the headline
            if ov.get("kind") == "line_draw":
                draw_overlay(img, d, ov, t, self)
        hl = self.spec.get("headline")
        if hl:
            self.draw_headline(img, t, hl)
        for ov in overlays:
            if ov.get("kind") != "line_draw":
                draw_overlay(img, d, ov, t, self)
        return img

    def draw_headline(self, img, t, hl):
        if isinstance(hl, str):
            hl = {"text": hl}
        segs = rich_segments(hl["text"], hl.get("highlight"), T.TITLE, T.color(hl.get("highlight_color", "yellow")))
        max_w = T.W - 2 * 80
        size = hl.get("size", 76)
        # step the size down (to 60px) until the last line isn't a lone orphaned word
        for size in ([size] if "size" in hl else range(size, 58, -4)):
            f = G.font("mono", size)
            lines = G.balanced(G.wrap_rich, segs, f, max_w)
            if len(lines) < 2 or len(lines[-1]) > 1:
                break
        total = sum(len(w) + 1 for line in lines for w, _ in line)
        start = hl.get("at", 0.1)
        speed = hl.get("cps", 60)  # characters per second: the hook reads in about a second
        n = int((t - start) * speed) if t >= start else 0
        if n <= 0:
            return
        shown = truncate_rich(lines, min(n, total))
        line_h = size * 1.18
        block_h = line_h * len(lines)
        y0 = hl.get("y", 0.34) * T.H - block_h / 2
        layer = G.shadowed_text_layer(shown + [[]] * (len(lines) - len(shown)), f, T.TITLE, line_h, max_w,
                                      shadow=T.INK, shadow_alpha=0.8, blur=14)
        G.paste_rgba(img, layer, (80 - 30, y0 - 30))
        chip = self.spec.get("chip")
        if chip:
            ca = G.ease_out(G.prog(t, start + total / speed + 0.1, 0.35))
            draw_chip(img, chip, T.W / 2, y0 + block_h + 40, ca)


def draw_chip(img, text, cx, y, alpha):
    """Orange pill: 'Topic · American Inequality' with the brand in navy."""
    if alpha <= 0:
        return
    d = ImageDraw.Draw(img, "RGBA")
    f = G.font("mono", 30)
    if " · " in text:
        a, b = text.rsplit(" · ", 1)
        segs = [(a + " · ", T.TITLE), (b, T.NAVY)]
    else:
        segs = [(text, T.TITLE)]
    w = sum(f.getlength(s) for s, _ in segs)
    x0 = cx - w / 2 - 22
    d.rounded_rectangle((x0, y, x0 + w + 44, y + 58), 12, fill=G.rgba(T.ORANGE, alpha))
    x = x0 + 22
    for s, c in segs:
        d.text((x, y + 11), s, font=f, fill=G.rgba(c, alpha))
        x += f.getlength(s)


def draw_overlay(img, d, ov, t, scene):
    kind = ov.get("kind", "stamp")
    at = ov.get("at", 0.5)
    p = G.prog(t, at, ov.get("in", 0.45))
    if p <= 0:
        return
    a = G.ease_out(p)
    cx = ov.get("x", 0.5) * T.W
    cy = ov.get("y", 0.4) * T.H
    col = T.color(ov.get("color", "yellow"))
    if kind == "stamp":
        f = G.font("mono", ov.get("size", 64))
        txt = ov["text"]
        w = f.getlength(txt)
        s = 1 + 0.25 * (1 - G.ease_out(p))
        layer = Image.new("RGBA", (int(w + 80), int(f.size * 1.9)), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle((4, 4, layer.width - 4, layer.height - 4), 10,
                             fill=G.rgba(T.INK, 0.55), outline=G.rgba(col), width=4)
        ld.text((40, f.size * 0.38), txt, font=f, fill=G.rgba(col))
        G.rotated_paste(img, layer, (cx, cy), ov.get("angle", 0), a, s)
    elif kind == "stat":
        f = G.font("display", ov.get("size", 170))
        val = G.count_value(ov["value"], G.prog(t, at, ov.get("count", 1.4)), ov.get("from", 0))
        txt = fmt_from(ov, val)
        lay = G.shadowed_text_layer([txt], f, col, f.size * 1.1, T.W - 100, shadow=T.INK,
                                    shadow_alpha=0.7, blur=16)
        G.paste_rgba(img, lay, (50 - 30, cy - f.size * 0.6 - 30), a)
        if ov.get("label"):
            lf = G.font("sans", 38)
            for i, line in enumerate(G.wrap(ov["label"], lf, T.W - 200)):
                lay = G.shadowed_text_layer([line], lf, T.TITLE, lf.size * 1.2, T.W - 100, shadow=T.INK,
                                            shadow_alpha=0.8, blur=10)
                G.paste_rgba(img, lay, (20, cy + f.size * 0.55 + i * lf.size * 1.25 - 30), a)
    elif kind == "tag":
        f = G.font("mono", ov.get("size", 32))
        txt = ov["text"]
        w = f.getlength(txt)
        bg = T.color(ov.get("background", "orange"))
        d.rounded_rectangle((cx - w / 2 - 20, cy - 30, cx + w / 2 + 20, cy + 30), 30, fill=G.rgba(bg, a))
        d.text((cx - w / 2, cy - f.size * 0.62), txt, font=f, fill=G.rgba(T.color(ov.get("color", "white")), a))
    elif kind == "callout":
        # A value box with a leader line to a point in the photo (Tal's "$0.00" meter).
        f = G.font("mono", ov.get("size", 64))
        txt = ov["text"]
        sub = ov.get("sub")
        w = max(f.getlength(txt), G.font("mono", 24).getlength(sub or "")) + 60
        h = f.size * 1.3 + (40 if sub else 0) + 20
        px, py = ov.get("point", [ov.get("x", 0.5), ov.get("y", 0.4) + 0.12])
        s = 0.85 + 0.15 * G.ease_back(p)
        box = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
        bd = ImageDraw.Draw(box)
        bd.rounded_rectangle((0, 0, w - 1, h - 1), 16, fill=G.rgba(T.INK, 0.88), outline=G.rgba(col), width=4)
        bd.text(((w - f.getlength(txt)) / 2, 14), txt, font=f, fill=G.rgba(col))
        if sub:
            sf = G.font("mono", 24)
            bd.text(((w - sf.getlength(sub)) / 2, 14 + f.size * 1.2), sub, font=sf, fill=G.rgba(T.TITLE, 0.9))
        d.line((cx, cy + h / 2, px * T.W, py * T.H), fill=G.rgba(T.TITLE, a * 0.9), width=4)
        G.rotated_paste(img, box, (cx, cy), 0, a, s)
    elif kind == "line_draw":
        # An orange line drawing itself across the photo (Tal's rail-line trace).
        pts = [(x * T.W, y * T.H) for x, y in ov["points"]]
        dp = G.ease_in_out(G.prog(t, at, ov.get("draw", 2.0)))
        seg = _partial_polyline(pts, dp)
        if len(seg) > 1:
            d.line(seg, fill=G.rgba(T.color(ov.get("color", "orange"))), width=ov.get("width", 10), joint="curve")


def _partial_polyline(pts, p):
    import math
    lens = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    total = sum(lens) * p
    out = [pts[0]]
    for (a, b), L in zip(zip(pts, pts[1:]), lens):
        if total <= 0:
            break
        if total >= L:
            out.append(b)
            total -= L
        else:
            f = total / L
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            break
    return out


# =============================================================================
# Article card
# =============================================================================

def months_ago_label(post_date, today=None):
    if not post_date:
        return None
    try:
        pd = datetime.fromisoformat(str(post_date).replace("Z", "+00:00")).date()
    except ValueError:
        return None
    today = today or date.today()
    days = (today - pd).days
    if days < 2:
        return "THIS WEEK" if days >= 0 else None
    if days < 14:
        return "LAST WEEK"
    if days < 45:
        return f"{max(2, days // 7)} WEEKS AGO"
    months = round(days / 30.44)
    if months < 12:
        return f"{months} MONTHS AGO"
    years = round(days / 365.25)
    return "A YEAR AGO" if years <= 1 else f"{years} YEARS AGO"


def build_article_card(article, cover_path=None, width=860):
    """Draw a Substack-style post card from article metadata."""
    pad = 46
    inner = width - 2 * pad
    title_f = G.font("sans_heavy", 54)
    sub_f = G.font("sans_semi", 31)
    pub_f = G.font("mono", 23)
    by_f = G.font("sans", 27)
    date_f = G.font("mono_med", 23)
    title_lines = G.wrap(article.get("title", ""), title_f, inner)
    sub_lines = G.wrap(article.get("subtitle", ""), sub_f, inner)
    cover_h = 0
    cover = None
    if cover_path and Path(cover_path).exists():
        cover = ImageOps.fit(Image.open(cover_path).convert("RGB"), (width, int(width * 0.5)), Image.LANCZOS)
        cover_h = cover.height
    h = (cover_h + pad + 34 + 26 + len(title_lines) * 64 + 18 + len(sub_lines) * 42 + 34 + 64 + pad)
    card = Image.new("RGBA", (width, int(h)), (0, 0, 0, 0))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, h - 1), 28, fill=255)
    body = Image.new("RGBA", card.size, G.rgba(T.TITLE))
    if cover:
        body.paste(cover, (0, 0))
    d = ImageDraw.Draw(body)
    y = cover_h + pad
    pub = article.get("publication", T.BRAND).upper()
    if article.get("section"):
        pub += f" · {article['section'].upper()}"
    d.text((pad, y), pub, font=pub_f, fill=G.rgba(T.ORANGE))
    y += 34 + 26
    for line in title_lines:
        d.text((pad, y), line, font=title_f, fill=G.rgba(T.NAVY))
        y += 64
    y += 18
    for line in sub_lines:
        d.text((pad, y), line, font=sub_f, fill=G.rgba(G.mix(T.NAVY, T.TITLE, 0.3)))
        y += 42
    y += 34
    # byline: initials avatar + names + date
    names = article.get("authors") or []
    initials = "".join(n.split()[0][0] for n in names[:1]) + "".join(n.split()[-1][0] for n in names[:1])
    d.ellipse((pad, y, pad + 56, y + 56), fill=G.rgba(T.ORANGE))
    af = G.font("sans", 22)
    d.text((pad + 28 - af.getlength(initials) / 2, y + 14), initials, font=af, fill=G.rgba(T.TITLE))
    byline = " & ".join(names) if len(names) <= 2 else ", ".join(names[:-1]) + " & " + names[-1]
    while by_f.getlength(byline) > inner - 76 and len(names) > 2:  # too long for the card
        byline = f"{names[0]} et al."
    d.text((pad + 76, y + 1), byline, font=by_f, fill=G.rgba(T.NAVY))
    d.text((pad + 76, y + 34), article.get("date_label", ""), font=date_f, fill=G.rgba(G.mix(T.NAVY, T.TITLE, 0.4)))
    card.paste(body, (0, 0), mask)
    return card


class ArticleCardScene(Scene):
    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        cover = ctx.media_path(spec.get("cover", "cover.jpg"))
        art = dict(ctx.article)
        art.update(spec.get("override", {}))
        self.card = build_article_card(art, cover if spec.get("show_cover", True) else None)
        self.shadow, self.shadow_pad = G.soft_shadow(self.card.size, 28, 30, 0.35, T.INK)
        badge = spec.get("badge", "auto")
        if badge == "auto":
            badge = months_ago_label(art.get("post_date"), ctx.today)
        self.badge = badge

    def render(self, t):
        img = G.orange_background().copy()
        p = G.prog(t, 0.05, 0.75)
        e = G.ease_back(p, 1.2)
        cy = self.spec.get("y", 0.40) * T.H + (1 - G.ease_out(p)) * 380
        ang = -2.5 - 6 * (1 - e)
        # shadow then card
        sh = self.shadow
        G.rotated_paste(img, sh, (T.W / 2 + 6, cy + 18), ang, G.ease_out(p))
        G.rotated_paste(img, self.card, (T.W / 2, cy), ang, G.ease_out(p) if p < 1 else 1)
        if self.badge:
            bp = G.prog(t, self.at("badge_at", 0.9), 0.35)
            if bp > 0:
                f = G.font("mono", 38)
                w = f.getlength(self.badge)
                lay = Image.new("RGBA", (int(w + 56), 74), (0, 0, 0, 0))
                ld = ImageDraw.Draw(lay)
                ld.rounded_rectangle((0, 0, lay.width - 1, 73), 10, fill=G.rgba(T.YELLOW), outline=G.rgba(T.NAVY), width=3)
                ld.text((28, 12), self.badge, font=f, fill=G.rgba(T.NAVY))
                s = 1 + 0.5 * (1 - G.ease_out(bp))
                bx = T.W / 2 + self.card.width / 2 - lay.width / 2 + 10
                by = cy - self.card.height / 2 - 10
                G.rotated_paste(img, lay, (bx, by), 7, G.ease_out(bp), s)
        chips = self.spec.get("chips", [])
        if chips:
            start = self.at("chips_at", max(1.2, self.dur * 0.5))
            gap = self.spec.get("chips_gap", 0.4)
            f = G.font("mono", 30)
            d = ImageDraw.Draw(img, "RGBA")
            y = cy + self.card.height / 2 + 70
            ws = [f.getlength(c) + 48 for c in chips]
            rows, row = [], []
            for c, w in zip(chips, ws):
                if row and sum(x[1] for x in row) + 18 * len(row) + w > T.W - 2 * T.MARGIN:
                    rows.append(row)
                    row = []
                row.append((c, w))
            rows.append(row)
            k = 0
            for r in rows:
                total = sum(w for _, w in r) + 18 * (len(r) - 1)
                x = (T.W - total) / 2
                for c, w in r:
                    a = G.ease_out(G.prog(t, start + k * gap, 0.3))
                    if a > 0:
                        d.rounded_rectangle((x, y, x + w, y + 62), 12, fill=G.rgba(T.NAVY, a))
                        d.text((x + 24, y + 12), c, font=f, fill=G.rgba(T.TITLE, a))
                    x += w + 18
                    k += 1
                y += 80
        return img


# =============================================================================
# Data scenes
# =============================================================================

class HBarsScene(ChartScene):
    """Horizontal bars that grow and count up, staggered (Tal's commute bars)."""

    def render(self, t):
        img, d = self.canvas(t)
        bars = self.spec["bars"]
        vmax = self.spec.get("max") or max(b["value"] for b in bars)
        x0, x1 = T.MARGIN, T.W - T.MARGIN
        row_h = self.spec.get("row_height", 200 if len(bars) <= 4 else 150)
        bar_h = self.spec.get("bar_height", 96 if len(bars) <= 4 else 72)
        top = self.spec.get("top", max(T.CHART_TOP + 20, (T.CHART_TOP + T.CHART_BOTTOM) / 2 - row_h * len(bars) / 2))
        lf = G.font("mono_semi", 34)
        vf = G.font("mono", 46)
        for i, b in enumerate(bars):
            start = b.get("at", 0.35 + i * self.spec.get("stagger", 0.9))
            grow = self.spec.get("grow", 1.2)
            appear = G.ease_out(G.prog(t, start - 0.25, 0.3))
            if appear <= 0:
                continue
            y = top + i * row_h
            d.text((x0, y), b["label"], font=lf, fill=G.rgba(T.NAVY, appear))
            by = y + 52
            d.rounded_rectangle((x0, by, x1, by + bar_h), 8, fill=G.rgba(T.INK, 0.16 * appear))
            p = G.ease_out(G.prog(t, start, grow))
            val = b["value"] * p
            wfill = (x1 - x0) * (val / vmax)
            col = T.color(b.get("color", "navy"))
            if wfill >= 4:
                d.rounded_rectangle((x0, by, x0 + wfill, by + bar_h), 8, fill=G.rgba(col, appear))
            txt = b.get("display") if (b.get("display") and p >= 1) else fmt_from(b, val, self.spec)
            tw = vf.getlength(txt)
            tcol = T.TITLE
            d.text((x1 - tw - 18, by + (bar_h - vf.size) / 2 - 4), txt, font=vf, fill=G.rgba(tcol, appear))
        return img


class VBarsScene(ChartScene):
    """Side-by-side vertical bars (Tal's '$5.5B vs $11.1B' comparison)."""

    def render(self, t):
        img, d = self.canvas(t)
        bars = self.spec["bars"]
        n = len(bars)
        vmax = self.spec.get("max") or max(b["value"] for b in bars)
        base = self.spec.get("baseline", 1140)
        max_h = self.spec.get("max_height", 520)
        span = T.W - 2 * T.MARGIN
        slot = span / n
        bw = min(210, slot * 0.62)
        vf = G.font("mono", 46 if n <= 3 else 36)
        nf = G.font("sans", 32 if n <= 3 else 28)
        sf = G.font("mono_med", 24)
        for i, b in enumerate(bars):
            start = b.get("at", 0.4 + i * self.spec.get("stagger", 1.2))
            appear = G.ease_out(G.prog(t, start - 0.2, 0.3))
            if appear <= 0:
                continue
            cx = T.MARGIN + slot * (i + 0.5)
            p = G.ease_out(G.prog(t, start, self.spec.get("grow", 1.3)))
            val = b["value"] * p
            h = max_h * val / vmax
            col = T.color(b.get("color", "navy" if i == 0 else "white"))
            if h >= 2:
                d.rounded_rectangle((cx - bw / 2, base - h, cx + bw / 2, base), 6, fill=G.rgba(col, appear))
            txt = b["display"] if (b.get("display") and p >= 1) else fmt_from(b, val, self.spec)
            vcol = T.color(b.get("value_color", "white"))
            G.draw_centered(d, cx, base - h - vf.size - 18, txt, vf, G.rgba(vcol, appear))
            ny = base + 20
            for line in G.wrap(b["label"], nf, slot - 10):
                G.draw_centered(d, cx, ny, line, nf, G.rgba(T.TITLE, appear))
                ny += nf.size * 1.2
            for line in (b.get("sublabel") or "").split("\n"):
                if line:
                    G.draw_centered(d, cx, ny + 6, line, sf, G.rgba(T.NAVY, appear))
                    ny += sf.size * 1.3
        ann = self.spec.get("annotation")
        if ann:
            p = G.prog(t, self.at("annotation_at", ann.get("at", self.dur * 0.6)), 0.35)
            if p > 0:
                i = ann.get("bar", n - 1)
                b = bars[i]
                cx = T.MARGIN + slot * (i + 0.5)
                h = max_h * b["value"] / vmax
                f = G.font("mono", 52)
                s = 1 + 0.4 * (1 - G.ease_out(p))
                lay = Image.new("RGBA", (int(f.getlength(ann["text"]) + 40), 80), (0, 0, 0, 0))
                ImageDraw.Draw(lay).text((20, 6), ann["text"], font=f, fill=G.rgba(T.color(ann.get("color", "yellow"))))
                G.rotated_paste(img, lay, (cx, base - h - vf.size - 90), 0, G.ease_out(p), s)
        return img


class BigNumberScene(ChartScene):
    """One or more giant count-up numbers with labels."""

    def render(self, t):
        img, d = self.canvas(t)
        stats = self.spec["stats"]
        n = len(stats)
        area_top = self.spec.get("top", T.CHART_TOP + (60 if self.spec.get("title") else 0))
        area_bot = T.CHART_BOTTOM
        slot = (area_bot - area_top) / n
        kick = self.spec.get("kicker")
        if kick:
            f = G.font("mono_semi", 30)
            a = G.ease_out(G.prog(t, 0.1, 0.4))
            G.draw_centered(d, T.W / 2, area_top - 10, kick.upper(), f, G.rgba(T.NAVY, a))
        for i, s in enumerate(stats):
            start = s.get("at", 0.3 + i * self.spec.get("stagger", 1.6))
            p = G.prog(t, start, s.get("count", 1.6))
            appear = G.ease_out(G.prog(t, start, 0.3))
            if appear <= 0:
                continue
            size = s.get("size", 230 if n == 1 else 170 if n == 2 else 130)
            f = G.font("display", size)
            val = G.count_value(s["value"], p, s.get("from", 0))
            txt = s.get("display") if (s.get("display") and p >= 1) else fmt_from(s, val)
            col = T.color(s.get("color", "white"))
            cy = area_top + slot * (i + 0.45)
            lay = G.shadowed_text_layer([txt], f, col, f.size * 1.08, T.W - 80, shadow=T.INK,
                                        shadow_alpha=0.18, blur=18)
            G.paste_rgba(img, lay, (40 - 30, cy - f.size * 0.62 - 30), appear)
            lf = G.font("sans", s.get("label_size", 44))
            ly = cy + f.size * 0.52
            for line in G.wrap(s.get("label", ""), lf, T.W - 2 * T.MARGIN):
                G.draw_centered(d, T.W / 2, ly, line, lf, G.rgba(T.color(s.get("label_color", "navy")), appear))
                ly += lf.size * 1.22
        return img


class WaffleScene(ChartScene):
    """10x10 grid of squares filled by group (Tal's '96% of parking is free')."""

    def render(self, t):
        img, d = self.canvas(t)
        groups = self.spec["groups"]
        cols = self.spec.get("cols", 10)
        total = self.spec.get("total", 100)
        rows = (total + cols - 1) // cols
        cell = self.spec.get("cell", 54)
        gap = self.spec.get("gap", 10)
        gw = cols * cell + (cols - 1) * gap
        x0 = (T.W - gw) / 2
        y0 = self.spec.get("top", T.CHART_TOP + 20)
        # which group each cell belongs to, in reading order
        owner = []
        for gi, g in enumerate(groups):
            owner += [gi] * int(round(g["count"]))
        owner = (owner + [None] * total)[:total]
        grid_in = G.prog(t, 0.1, 0.6)
        fill_start = self.at("fill_at", 0.8)
        fill_dur = self.spec.get("fill", 1.8)
        # groups fill one after another, each over a share of fill_dur
        counts = [int(round(g["count"])) for g in groups]
        starts, acc = [], 0
        for c in counts:
            starts.append(acc)
            acc += c
        for k in range(total):
            r, c = divmod(k, cols)
            x = x0 + c * (cell + gap)
            y = y0 + r * (cell + gap)
            ga = G.ease_out(G.clamp01(grid_in * 1.6 - (k / total) * 0.6))
            if ga <= 0:
                continue
            gi = owner[k]
            filled = 0.0
            if gi is not None:
                g = groups[gi]
                g_start = g.get("at", fill_start + fill_dur * starts[gi] / max(acc, 1))
                g_dur = max(0.25, fill_dur * counts[gi] / max(acc, 1))
                local = (k - starts[gi]) / max(counts[gi], 1)
                filled = G.ease_out(G.prog(t, g_start + local * g_dur, 0.25))
            d.rounded_rectangle((x, y, x + cell, y + cell), 8, fill=G.rgba(T.INK, 0.14 * ga))
            if filled > 0:
                col = T.color(groups[gi].get("color", "navy"))
                inset = (1 - filled) * cell / 2
                d.rounded_rectangle((x + inset, y + inset, x + cell - inset, y + cell - inset), 8,
                                    fill=G.rgba(col, ga))
        # legend
        ly = y0 + rows * (cell + gap) + 30
        lf = G.font("mono_semi", 28)
        items = [(g["label"], T.color(g.get("color", "navy")),
                  g.get("at", fill_start + fill_dur * starts[i] / max(acc, 1))) for i, g in enumerate(groups)
                 if g.get("label")]
        widths = [lf.getlength(lbl) + 56 for lbl, _, _ in items]
        rows_l, cur = [], []
        for it, w in zip(items, widths):
            if cur and sum(x[1] for x in cur) + w > T.W - 2 * T.MARGIN:
                rows_l.append(cur)
                cur = []
            cur.append((it, w))
        if cur:
            rows_l.append(cur)
        for row in rows_l:
            x = (T.W - sum(w for _, w in row)) / 2
            for (lbl, col, st), w in row:
                a = G.ease_out(G.prog(t, st, 0.4))
                d.rounded_rectangle((x, ly + 4, x + 28, ly + 32), 5, fill=G.rgba(col, a))
                d.text((x + 38, ly), lbl, font=lf, fill=G.rgba(T.NAVY, a))
                x += w
            ly += 46
        big = self.spec.get("big")
        if big:
            st = self.at("big_at", big.get("at", fill_start + fill_dur))
            p = G.prog(t, st, big.get("count", 1.2))
            a = G.ease_out(G.prog(t, st, 0.3))
            if a > 0:
                f = G.font("display", big.get("size", 130))
                txt = fmt_from(big, G.count_value(big["value"], p))
                col = T.color(big.get("color", "white"))
                sw = f.getlength(txt)
                lab = big.get("label", "")
                lf2 = G.font("sans", 40)
                lw = lf2.getlength(lab)
                x = (T.W - sw - (lw + 20 if lab else 0)) / 2
                by = ly + 4
                d.text((x, by), txt, font=f, fill=G.rgba(col, a))
                if lab:
                    d.text((x + sw + 20, by + f.size * 0.62), lab, font=lf2, fill=G.rgba(T.NAVY, a))
        return img


class StackedScene(ChartScene):
    """100%-stacked horizontal bars, e.g. share of wealth vs share of population."""

    def render(self, t):
        img, d = self.canvas(t)
        rows = self.spec["rows"]
        x0, x1 = T.MARGIN, T.W - T.MARGIN
        bar_h = self.spec.get("bar_height", 180)
        row_gap = self.spec.get("row_gap", 150)
        top = self.spec.get("top", T.CHART_TOP + 40)
        lf = G.font("mono_semi", 30)
        pf = G.font("mono", 56)
        nf = G.font("mono_semi", 26)
        seg_dur = self.spec.get("grow", 0.6)
        for ri, row in enumerate(rows):
            y = top + ri * (bar_h + row_gap)
            rstart = row.get("at", 0.3 + ri * self.spec.get("row_stagger", 2.0))
            a = G.ease_out(G.prog(t, rstart - 0.2, 0.3))
            if a <= 0:
                continue
            d.text((x0, y), row["label"], font=lf, fill=G.rgba(T.NAVY, a))
            by = y + 48
            d.rectangle((x0, by, x1, by + bar_h), fill=G.rgba(T.INK, 0.14 * a))
            tot = row.get("total") or sum(s["value"] for s in row["segments"])
            x = x0
            for si, s in enumerate(row["segments"]):
                st = s.get("at", rstart + si * seg_dur * 0.8)
                p = G.ease_out(G.prog(t, st, seg_dur))
                w = (x1 - x0) * s["value"] / tot
                col = T.color(s.get("color", "navy"))
                if p > 0 and w * p >= 1:
                    d.rectangle((x, by, x + w * p, by + bar_h), fill=G.rgba(col, a))
                    if si:
                        d.line((x, by, x, by + bar_h), fill=G.rgba(T.ORANGE, a), width=4)
                # label inside if it fits
                if p > 0.6 and w > 90:
                    la = G.ease_out(G.prog(t, st + seg_dur * 0.6, 0.3)) * a
                    txt = s.get("display") or fmt_from(s, s["value"], self.spec)
                    tc = T.color(s.get("text_color", "navy" if col in (T.TITLE, T.YELLOW, T.GOLD) else "white"))
                    d.text((x + 20, by + 24), txt, font=pf, fill=G.rgba(tc, la))
                    if s.get("label") and w > 150:
                        name = s["label"]
                        while nf.getlength(name) > w - 26 and len(name) > 3:
                            name = name[:-2] + "…"
                        d.text((x + 20, by + bar_h - 50), name, font=nf, fill=G.rgba(tc, la))
                x += w
        return img


class LineScene(ChartScene):
    """Line/area chart that draws left to right, with a live counter (Tal's 5 -> 870)."""

    def render(self, t):
        img, d = self.canvas(t)
        series = self.spec["series"]
        allx = [p[0] for s in series for p in s["points"]]
        ally = [p[1] for s in series for p in s["points"]]
        xmin, xmax = self.spec.get("x_range", [min(allx), max(allx)])
        ymin, ymax = self.spec.get("y_range", [min(0, min(ally)), max(ally) * 1.08])
        top = self.spec.get("top", T.CHART_TOP + (150 if self.spec.get("counter") else 40))
        bot = self.spec.get("bottom", 1250)
        left, right = T.MARGIN + 10, T.W - T.MARGIN - 10
        start = self.at("draw_at", 0.4)
        dp = G.ease_in_out(G.prog(t, start, self.spec.get("draw", 2.6)))
        ax_a = G.ease_out(G.prog(t, 0.1, 0.4))
        X = lambda v: left + (right - left) * (v - xmin) / (xmax - xmin)  # noqa: E731
        Y = lambda v: bot - (bot - top) * (v - ymin) / (ymax - ymin)  # noqa: E731
        # baseline + ticks
        d.line((left, bot, right, bot), fill=G.rgba(T.NAVY, 0.6 * ax_a), width=3)
        tf = G.font("mono_semi", 28)
        for tick in self.spec.get("x_ticks", [xmin, xmax]):
            lab = str(tick[1]) if isinstance(tick, list) else str(tick)
            val = tick[0] if isinstance(tick, list) else tick
            G.draw_centered(d, X(val), bot + 14, lab, tf, G.rgba(T.NAVY, ax_a))
        for yt in self.spec.get("y_ticks", []):
            val, lab = (yt[0], yt[1]) if isinstance(yt, list) else (yt, fmt_from(self.spec, yt))
            d.line((left, Y(val), right, Y(val)), fill=G.rgba(T.NAVY, 0.18 * ax_a), width=2)
            d.text((left, Y(val) - 32), str(lab), font=tf, fill=G.rgba(T.NAVY, 0.9 * ax_a))
        # supersampled layer for smooth lines
        ss = 2
        box = (int(left - 20), int(top - 80), int(right + 20), int(bot + 4))
        bw, bh = box[2] - box[0], box[3] - box[1]
        layer = Image.new("RGBA", (bw * ss, bh * ss), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer, "RGBA")
        xcut = xmin + (xmax - xmin) * dp
        heads = []
        for s in series:
            pts = sorted(s["points"])
            vis = []
            for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                if xa > xcut:
                    break
                vis.append((xa, ya))
                if xb > xcut:
                    f = (xcut - xa) / (xb - xa) if xb != xa else 1
                    vis.append((xcut, ya + (yb - ya) * f))
                    break
            else:
                vis.append(pts[-1])
            if len(vis) < 2 or dp <= 0:
                continue
            P = [((X(x) - box[0]) * ss, (Y(y) - box[1]) * ss) for x, y in vis]
            col = T.color(s.get("color", "navy"))
            if s.get("area"):
                poly = P + [(P[-1][0], (bot - box[1]) * ss), (P[0][0], (bot - box[1]) * ss)]
                area_col = T.color(s.get("area_color", "white"))
                ld.polygon(poly, fill=G.rgba(area_col, s.get("area_alpha", 0.22)))
            ld.line(P, fill=G.rgba(col), width=s.get("width", 8) * ss, joint="curve")
            hx, hy = P[-1]
            r = 11 * ss
            ld.ellipse((hx - r, hy - r, hx + r, hy + r), fill=G.rgba(col), outline=G.rgba(T.TITLE), width=3 * ss)
            heads.append((s, vis[-1]))
        layer = layer.resize((bw, bh), Image.LANCZOS)
        img.paste(layer, (box[0], box[1]), layer)
        vf = G.font("mono", 38)
        lf = G.font("sans", 34)
        for s, (hx, hy) in heads:
            if not s.get("head_label", True):
                continue
            val = fmt_from(s, hy, self.spec)
            col = G.rgba(T.color(s.get("label_color", s.get("color", "navy"))))
            name = f"{s['label']}  " if s.get("label") else ""
            w = lf.getlength(name) + vf.getlength(val)
            tx = min(X(hx) + 18, right - w)
            ty = Y(hy) - 58 + s.get("label_dy", 0)
            d.text((tx, ty + 4), name, font=lf, fill=col)
            d.text((tx + lf.getlength(name), ty), val, font=vf, fill=col)
        c = self.spec.get("counter")
        if c:
            s = series[c.get("series", 0)]
            pts = sorted(s["points"])
            cur = pts[0][1]
            for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                if xcut >= xb:
                    cur = yb
                elif xcut >= xa:
                    cur = ya + (yb - ya) * ((xcut - xa) / (xb - xa) if xb != xa else 1)
            f = G.font("display", c.get("size", 150))
            txt = fmt_from(c, cur)
            G.draw_centered(d, T.W / 2, T.CHART_TOP - 20, txt, f, G.rgba(T.color(c.get("color", "white")), ax_a))
            if c.get("label"):
                lf = G.font("sans", 36)
                G.draw_centered(d, T.W / 2, T.CHART_TOP + f.size * 0.95, c["label"], lf, G.rgba(T.NAVY, ax_a))
        return img


class ThenNowScene(ChartScene):
    """Rows of 'old -> new' values with the old one struck through (Tal's 'Since February')."""

    def render(self, t):
        img, d = self.canvas(t)
        rows = self.spec["rows"]
        row_h = self.spec.get("row_height", 180)
        top = self.spec.get("top", max(T.CHART_TOP + 60, (T.CHART_TOP + T.CHART_BOTTOM) / 2 - row_h * len(rows) / 2))
        lf = G.font("sans", 42)
        of = G.font("mono", 46)
        nf = G.font("mono", 76)
        hf = G.font("mono_semi", 30)
        heads = self.spec.get("headers")
        if heads:
            a = G.ease_out(G.prog(t, 0.1, 0.4))
            x_new = T.W - T.MARGIN
            d.text((x_new - hf.getlength(heads[1]), top - 50), heads[1], font=hf, fill=G.rgba(T.TITLE, a))
            d.text((x_new - 360 - hf.getlength(heads[0]) / 2, top - 50), heads[0], font=hf, fill=G.rgba(T.NAVY, a))
        for i, r in enumerate(rows):
            st = r.get("at", 0.4 + i * self.spec.get("stagger", 1.3))
            a = G.ease_out(G.prog(t, st, 0.35))
            if a <= 0:
                continue
            y = top + i * row_h
            label_lines = G.wrap(r["label"], lf, 420)
            for j, line in enumerate(label_lines):
                d.text((T.MARGIN, y + 16 + j * 50), line, font=lf, fill=G.rgba(T.TITLE, a))
            old = str(r.get("old", ""))
            new = str(r["new"])
            xr = T.W - T.MARGIN
            nw = nf.getlength(new)
            ox = xr - 360 - of.getlength(old) / 2 if heads else xr - nw - 40 - of.getlength(old)
            d.text((ox, y + 26), old, font=of, fill=G.rgba(T.NAVY, a))
            sp = G.ease_out(G.prog(t, st + 0.35, 0.35))
            if sp > 0 and r.get("strike", True):
                d.line((ox - 4, y + 56, ox - 4 + (of.getlength(old) + 8) * sp, y + 56),
                       fill=G.rgba(T.NAVY, a), width=4)
            npop = G.prog(t, st + 0.6, 0.35)
            if npop > 0:
                col = T.color(r.get("color", "white"))
                d.text((xr - nw, y + 6 - 10 * (1 - G.ease_out(npop))), new, font=nf,
                       fill=G.rgba(col, G.ease_out(npop)))
            d.line((T.MARGIN, y + row_h - 22, xr, y + row_h - 22), fill=G.rgba(T.NAVY, 0.25 * a), width=2)
        return img


class ChecklistScene(ChartScene):
    """Items that tick off one by one."""

    def render(self, t):
        img, d = self.canvas(t)
        items = self.spec["items"]
        gap = self.spec.get("row_height", 124)
        top = self.spec.get("top", (T.CHART_TOP + T.CHART_BOTTOM) / 2 - gap * len(items) / 2)
        f = G.font("sans", self.spec.get("size", 54))
        for i, it in enumerate(items):
            it = {"text": it} if isinstance(it, str) else it
            st = it.get("at", 0.4 + i * self.spec.get("stagger", 0.8))
            a = G.ease_out(G.prog(t, st, 0.3))
            if a <= 0:
                continue
            y = top + i * gap
            x = T.MARGIN + 20
            box = 64
            d.rounded_rectangle((x, y, x + box, y + box), 10, outline=G.rgba(T.TITLE, a), width=5)
            cp = G.ease_out(G.prog(t, st + 0.2, 0.3))
            if cp > 0:
                col = T.color(it.get("color", "navy"))
                d.rounded_rectangle((x, y, x + box, y + box), 10, fill=G.rgba(col, cp))
                pts = [(x + 14, y + 33), (x + 27, y + 47), (x + 51, y + 17)]
                d.line(pts, fill=G.rgba(T.TITLE, cp), width=8, joint="curve")
            d.text((x + box + 34, y + 1), it["text"], font=f, fill=G.rgba(T.TITLE, a))
        return img


class StatementScene(ChartScene):
    """A big typed statement. {Braced} words get a navy marker highlight."""

    def render(self, t):
        img, d = self.canvas(t)
        size = self.spec.get("size", 76)
        f = G.font("mono", size)
        segs = rich_segments(self.spec["text"], None, T.TITLE, "HI")
        lines = G.balanced(G.wrap_rich, segs, f, T.W - 2 * 80)
        total = sum(len(w) + 1 for line in lines for w, _ in line)
        n = int((t - self.at("at", 0.3)) * self.spec.get("cps", 32))
        shown = truncate_rich(lines, max(0, min(n, total)))
        line_h = size * 1.3
        y = self.spec.get("y", 0.40) * T.H - line_h * len(lines) / 2
        kick = self.spec.get("kicker")
        if kick:
            kf = G.font("mono_semi", 30)
            G.draw_centered(d, T.W / 2, y - 80, kick.upper(), kf, G.rgba(T.NAVY, G.ease_out(G.prog(t, 0, 0.4))))
        space = f.getlength(" ")
        for i, line in enumerate(lines):
            full_w = sum(f.getlength(w) for w, _ in line) + space * (len(line) - 1)
            x = (T.W - full_w) / 2
            vis = shown[i] if i < len(shown) else []
            for j, (w, c) in enumerate(vis):
                ww = f.getlength(w)
                if c == "HI":
                    nxt_hi = j + 1 < len(vis) and vis[j + 1][1] == "HI"
                    d.rectangle((x - 10, y + i * line_h - 4, x + ww + (space if nxt_hi else 10),
                                 y + i * line_h + size * 1.14), fill=G.rgba(T.NAVY))
                    d.text((x, y + i * line_h), w, font=f, fill=G.rgba(T.YELLOW))
                else:
                    d.text((x, y + i * line_h), w, font=f, fill=G.rgba(T.TITLE))
                x += f.getlength(line[j][0]) + space
        return img


class OutroScene(Scene):
    """Brand end card over a faded copy of the article card."""

    def render(self, t):
        img = G.orange_background().copy()
        d = ImageDraw.Draw(img, "RGBA")
        p = G.ease_back(G.prog(t, 0.1, 0.6))
        a = G.ease_out(G.prog(t, 0.1, 0.4))
        f = G.font("display", 118)
        y = T.H * 0.30
        for i, word in enumerate(self.spec.get("wordmark", ["AMERICAN", "INEQUALITY"])):
            lay = G.shadowed_text_layer([word], f, T.TITLE, f.size * 1.05, T.W - 80, shadow=T.INK,
                                        shadow_alpha=0.25, blur=16)
            G.rotated_paste(img, lay, (T.W / 2, y + i * 128 + lay.height / 2 - 30), 0, a, 0.9 + 0.1 * p)
        url = self.spec.get("url", T.BRAND_URL)
        uf = G.font("mono", 34)
        ua = G.ease_out(G.prog(t, 0.6, 0.4))
        uw = uf.getlength(url)
        uy = y + 300
        d.rounded_rectangle((T.W / 2 - uw / 2 - 28, uy, T.W / 2 + uw / 2 + 28, uy + 72), 14, fill=G.rgba(T.NAVY, ua))
        G.draw_centered(d, T.W / 2, uy + 15, url, uf, G.rgba(T.TITLE, ua))
        authors = self.ctx.article.get("authors") or []
        names = authors[:-1] and ", ".join(authors[:-1]) + " & " + authors[-1] or "".join(authors)
        by = self.spec.get("byline", f"by {names}" if authors else "")
        if by:
            bf = G.font("sans_semi", 36)
            G.draw_centered(d, T.W / 2, y - 70, by, bf, G.rgba(T.NAVY, a))
        cta = self.spec.get("cta", "Full story + data at the link in bio")
        cf = G.font("mono_semi", 30)
        G.draw_centered(d, T.W / 2, uy + 110, cta, cf, G.rgba(T.NAVY, G.ease_out(G.prog(t, 0.9, 0.4))))
        return img


# =============================================================================
# Figure: reuse the author's own map / graphic
# =============================================================================

class FigureScene(Scene):
    """The article's own map or distinctive graphic on a card, with an optional
    slow push into a region (`zoom_to: [x0, y0, x1, y1]` as fractions of the image).
    Animated GIFs play their own animation."""

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.path = ctx.media_path(spec.get("media"))
        self.frames, self.times = [], []
        if self.path and self.path.exists():
            im = Image.open(self.path)
            t = 0.0
            try:
                n = getattr(im, "n_frames", 1)
                for k in range(n if spec.get("animate", True) else 1):
                    im.seek(k)
                    self.frames.append(im.convert("RGB"))
                    self.times.append(t)
                    t += (im.info.get("duration") or 100) / 1000.0
            except EOFError:
                pass
            self.loop = max(t, 0.1)
        else:
            ctx.warn(f"figure media not found: {spec.get('media')!r}")
            self.frames = [Image.new("RGB", (800, 600), (230, 230, 230))]
            self.times, self.loop = [0.0], 1.0
        rng = spec.get("frames")  # [first, last] GIF frames to play (then hold on the last)
        if rng and len(self.frames) > 1:
            a, b = rng[0], min(rng[1], len(self.frames) - 1)
            base = self.times[a]
            self.frames = self.frames[a:b + 1]
            self.times = [t - base for t in self.times[a:b + 1]]
            self.loop = max(self.times[-1] + 0.1, 0.1)
        crop = spec.get("crop")  # trim chrome (titles, toolbars) from the source: [x0,y0,x1,y1] fractions
        if crop:
            w, h = self.frames[0].size
            box = (int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h))
            self.frames = [f.crop(box) for f in self.frames]

    def source_line(self):
        return self.spec.get("source") or self.ctx.credit_for(self.spec.get("media"))

    def frame_at(self, t):
        if len(self.frames) == 1:
            return self.frames[0]
        # play the GIF once starting at `play_at`, then hold on its last frame
        lt = max(0.0, t - self.spec.get("play_at", 0.3)) * self.spec.get("speed", 1.0)
        if self.spec.get("loop", False):
            lt %= self.loop
        idx = 0
        for k, st in enumerate(self.times):
            if st <= lt:
                idx = k
        return self.frames[idx]

    def render(self, t):
        img = G.orange_background(self.spec.get("background", "orange")).copy()
        d = ImageDraw.Draw(img, "RGBA")
        y = T.CHART_TITLE_Y
        a = G.ease_out(G.prog(t, 0.0, 0.35))
        if self.spec.get("title"):
            f = G.font("sans", 52)
            for line in G.wrap(self.spec["title"], f, T.W - 2 * T.MARGIN):
                G.draw_centered(d, T.W / 2, y, line, f, G.rgba(T.TITLE, a))
                y += f.size * 1.2
        src = self.frame_at(t)
        sw, sh = src.size
        # visible window: full image easing toward zoom_to (kept at the image's aspect)
        zt = self.spec.get("zoom_to")
        p = G.ease_in_out(G.prog(t, self.at("zoom_at", 0.8), self.spec.get("zoom_dur", max(1.0, self.dur - 1.2))))
        x0, y0, x1, y1 = 0.0, 0.0, 1.0, 1.0
        if zt:
            zx0, zy0, zx1, zy1 = zt
            cx, cy = (zx0 + zx1) / 2, (zy0 + zy1) / 2
            zw = max(zx1 - zx0, (zy1 - zy0))  # square-ish in fractional space keeps aspect
            zw = min(1.0, zw)
            tx0, ty0 = min(max(cx - zw / 2, 0), 1 - zw), min(max(cy - zw / 2, 0), 1 - zw)
            x0, y0 = G.lerp(0, tx0, p), G.lerp(0, ty0, p)
            x1, y1 = G.lerp(1, tx0 + zw, p), G.lerp(1, ty0 + zw, p)
        max_w, max_h = T.W - 2 * 60, self.spec.get("max_height", 1000)
        pad = 22
        scale = min((max_w - 2 * pad) / sw, (max_h - 2 * pad) / sh)
        dw, dh = int(sw * scale), int(sh * scale)
        view = src.resize((dw, dh), Image.LANCZOS, box=(x0 * sw, y0 * sh, x1 * sw, y1 * sh))
        e = G.ease_out(G.prog(t, 0.05, 0.6))
        card = Image.new("RGBA", (dw + 2 * pad, dh + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle((0, 0, card.width - 1, card.height - 1), 22,
                                                fill=G.rgba(self.spec.get("card_color") and
                                                            T.color(self.spec["card_color"]) or (255, 255, 255)))
        card.paste(view, (pad, pad))
        cy = self.spec.get("y", 0.47) * T.H + (1 - e) * 200
        top_lim = y + 20 + card.height / 2
        cy = max(cy, top_lim)
        sh_img, _ = G.soft_shadow(card.size, 22, 28, 0.3, T.INK)
        G.rotated_paste(img, sh_img, (T.W / 2 + 4, cy + 16), self.spec.get("angle", 0), e)
        G.rotated_paste(img, card, (T.W / 2, cy), self.spec.get("angle", 0), e)
        for ov in self.spec.get("overlays", []):
            draw_overlay(img, d, ov, t, self)
        return img


SCENES = {
    "photo": PhotoScene,
    "hook": PhotoScene,
    "video": PhotoScene,
    "article_card": ArticleCardScene,
    "hbars": HBarsScene,
    "vbars": VBarsScene,
    "big_number": BigNumberScene,
    "waffle": WaffleScene,
    "stacked": StackedScene,
    "line": LineScene,
    "then_now": ThenNowScene,
    "checklist": ChecklistScene,
    "statement": StatementScene,
    "outro": OutroScene,
    "figure": FigureScene,
    "map": FigureScene,
}
