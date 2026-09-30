"""Loading real-world photos/video for scenes, and sourcing them from the web.

Sourcing (needs network access to the hosts involved):
  * Wikimedia Commons  - freely licensed, attributed photos (no key needed)
  * Pexels             - real stock footage and photos (free key: PEXELS_API_KEY)
  * Substack           - the article's own cover and inline images

Everything downloaded is recorded in <project>/media/credits.json so the
renderer can print "Photo: Author, License (Source)" on screen like Tal does.
"""
import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from . import theme as T
from .gfx import font

UA = "AmericanInequalityShorts/1.0 (https://americaninequality.substack.com)"
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}
OVERSCAN = 1.22
OK_LICENSES = ("cc0", "public domain", "pd", "cc by", "cc-by")  # excludes NC / ND


def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # bundled static ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


# --- HTTP ------------------------------------------------------------------------

def http_get(url, headers=None, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_json(url, headers=None):
    return json.loads(http_get(url, headers).decode("utf-8"))


def download(url, dest, headers=None):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(http_get(url, headers, timeout=300))
    return dest


# --- Credits ------------------------------------------------------------------------

def load_credits(media_dir):
    p = Path(media_dir) / "credits.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_credit(media_dir, filename, credit):
    credits = load_credits(media_dir)
    credits[filename] = credit
    (Path(media_dir) / "credits.json").write_text(json.dumps(credits, indent=2))


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


# --- Wikimedia Commons ---------------------------------------------------------------

def search_wikimedia(query, n=12, min_width=1200):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": 40,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 480,
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    pages = http_json(url).get("query", {}).get("pages", {})
    out = []
    for p in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = strip_html(meta.get("LicenseShortName", {}).get("value", ""))
        if info.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
            continue
        if info.get("width", 0) < min_width:
            continue
        if lic and not lic.lower().startswith(OK_LICENSES):
            continue
        if any(bad in lic.lower() for bad in ("nc", "nd")) and "cc" in lic.lower():
            continue
        author = strip_html(meta.get("Artist", {}).get("value", "")) or "Unknown"
        out.append({
            "source": "wikimedia", "id": str(p["pageid"]), "title": p.get("title", ""),
            "thumb": info.get("thumburl"), "url": info.get("url"),
            "width": info.get("width"), "height": info.get("height"),
            "page": info.get("descriptionurl"),
            "credit": f"Photo: {author[:60]}, {lic} (Wikimedia Commons)",
        })
        if len(out) >= n:
            break
    return out


# --- Pexels ---------------------------------------------------------------------------

def _pexels_headers():
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise SystemExit("Set PEXELS_API_KEY (free at https://www.pexels.com/api/) to search Pexels.")
    return {"Authorization": key}


def search_pexels(query, n=12, video=False):
    q = urllib.parse.quote(query)
    if video:
        data = http_json(f"https://api.pexels.com/videos/search?query={q}&orientation=portrait&size=large&per_page=40",
                         _pexels_headers())
        out = []
        for v in data.get("videos", []):
            files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("height")]
            files.sort(key=lambda f: (f["height"] >= 1920, -abs(f["height"] - 1920)), reverse=True)
            if not files or files[0]["height"] < 1080:
                continue
            out.append({
                "source": "pexels", "id": f"v{v['id']}", "title": v.get("url", ""),
                "thumb": v.get("image"), "url": files[0]["link"], "video": True,
                "width": files[0].get("width"), "height": files[0].get("height"),
                "duration": v.get("duration"), "page": v.get("url"),
                "credit": f"Video: {v.get('user', {}).get('name', 'Pexels')} (Pexels)",
            })
            if len(out) >= n:
                break
        return out
    data = http_json(f"https://api.pexels.com/v1/search?query={q}&orientation=portrait&size=large&per_page=40",
                     _pexels_headers())
    out = []
    for ph in data.get("photos", []):
        out.append({
            "source": "pexels", "id": f"p{ph['id']}", "title": ph.get("alt", ""),
            "thumb": ph["src"]["medium"], "url": ph["src"]["original"],
            "width": ph.get("width"), "height": ph.get("height"), "page": ph.get("url"),
            "credit": f"Photo: {ph.get('photographer', 'Pexels')} (Pexels)",
        })
        if len(out) >= n:
            break
    return out


def search(query, source="wikimedia", n=12, video=False):
    if source == "pexels":
        return search_pexels(query, n, video)
    return search_wikimedia(query, n)


def contact_sheet(candidates, thumbs_dir, out_path, cols=4):
    """Numbered grid of candidate thumbnails so a human (or Claude) can pick visually."""
    tiles = []
    for i, c in enumerate(candidates):
        tp = Path(thumbs_dir) / f"{i:02d}.jpg"
        try:
            if not tp.exists():
                download(c["thumb"], tp)
            im = Image.open(tp).convert("RGB")
        except Exception:
            im = Image.new("RGB", (270, 480), (60, 60, 60))
        tiles.append(ImageOps.fit(im, (270, 480)))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 280, max(1, rows) * 520), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    f = font("mono", 26)
    for i, im in enumerate(tiles):
        x, y = (i % cols) * 280 + 5, (i // cols) * 520 + 5
        sheet.paste(im, (x, y))
        c = candidates[i]
        label = f"#{i}  {c.get('width')}x{c.get('height')}{'  VIDEO' if c.get('video') else ''}"
        d.rectangle((x, y + 480, x + 270, y + 512), fill=(0, 0, 0))
        d.text((x + 6, y + 482), label, font=f, fill=T.YELLOW)
    sheet.save(out_path, quality=88)
    return out_path


# --- Loading for render -----------------------------------------------------------------

def is_video(path):
    return Path(path).suffix.lower() in VIDEO_EXT


def grade(im, dim=0.0, saturation=0.92, contrast=1.06):
    """Gentle editorial grade: slightly muted, slightly contrasty, optionally darker."""
    im = ImageEnhance.Color(im).enhance(saturation)
    im = ImageEnhance.Contrast(im).enhance(contrast)
    if dim:
        im = ImageEnhance.Brightness(im).enhance(1 - dim)
    return im


@lru_cache(maxsize=16)
def load_still(path, focus=(0.5, 0.5), dim=0.0):
    """Load a photo, cover-crop it to 9:16 with headroom for a Ken Burns move."""
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    tw, th = int(T.W * OVERSCAN), int(T.H * OVERSCAN)
    im = ImageOps.fit(im, (tw, th), method=Image.LANCZOS, centering=focus)
    return grade(im, dim)


def kenburns_frame(src, p, zoom=(1.0, 1.1), pan=((0.5, 0.5), (0.5, 0.5))):
    """Crop/scale a still for progress p in [0,1]. zoom>1 pushes in."""
    z = zoom[0] + (zoom[1] - zoom[0]) * p
    cx = pan[0][0] + (pan[1][0] - pan[0][0]) * p
    cy = pan[0][1] + (pan[1][1] - pan[0][1]) * p
    sw, sh = src.size
    # Sources are overscanned by OVERSCAN, so zoom 1.0 shows a 1/OVERSCAN window
    # and leaves room to pan; higher zoom pushes in further.
    w = min(sw, sw / (OVERSCAN * max(z, 0.01)))
    h = w * T.H / T.W
    x0 = min(max(cx * sw - w / 2, 0), sw - w)
    y0 = min(max(cy * sh - h / 2, 0), sh - h)
    return src.resize((T.W, T.H), Image.BILINEAR, box=(x0, y0, x0 + w, y0 + h))


def extract_video_frames(path, out_dir, seconds, start=0.0, focus=(0.5, 0.5)):
    """Decode a clip to cover-cropped 1080x1920 JPEG frames for fast random access."""
    out_dir = Path(out_dir)
    stamp = out_dir / ".done"
    key = f"{Path(path).stat().st_mtime}-{seconds}-{start}-{focus}"
    if stamp.exists() and stamp.read_text() == key:
        return sorted(out_dir.glob("*.jpg"))
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    fx, fy = focus
    vf = (f"scale={T.W}:{T.H}:force_original_aspect_ratio=increase,"
          f"crop={T.W}:{T.H}:(in_w-{T.W})*{fx}:(in_h-{T.H})*{fy},fps={T.FPS}")
    cmd = [ffmpeg_exe(), "-loglevel", "error", "-y", "-ss", str(start), "-t", str(seconds + 0.5),
           "-i", str(path), "-vf", vf, "-q:v", "3", str(out_dir / "%05d.jpg")]
    subprocess.run(cmd, check=True)
    stamp.write_text(key)
    return sorted(out_dir.glob("*.jpg"))


def fallback_backdrop(label="image missing"):
    """Used only when a scene's media file can't be found: an obvious placeholder,
    never a fake photo, so a missing image is caught at review time."""
    im = Image.new("RGB", (int(T.W * OVERSCAN), int(T.H * OVERSCAN)), T.INK)
    d = ImageDraw.Draw(im)
    step = 60
    for x in range(-im.height, im.width, step):
        d.line((x, 0, x + im.height, im.height), fill=(20, 38, 70), width=18)
    f = font("mono", 40)
    msg = f"[ {label} ]"
    d.text(((im.width - f.getlength(msg)) / 2, im.height * 0.62), msg, font=f, fill=T.GOLD)
    return im
