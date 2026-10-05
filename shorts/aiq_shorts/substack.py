"""Fetch a Substack post (text, metadata, cover and inline images/charts)."""
import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path

from . import media as M


def slug_from_url(url):
    path = urllib.parse.urlparse(url).path
    m = re.search(r"/p/([^/?#]+)", path)
    if not m:
        raise SystemExit(f"Not a Substack post URL: {url}")
    return m.group(1)


def html_to_text(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    blocks = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote", "figcaption"]):
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            blocks.append(f"\n## {txt}")
        elif el.name == "li":
            blocks.append(f"- {txt}")
        elif el.name == "figcaption":
            blocks.append(f"[Figure caption] {txt}")
        else:
            blocks.append(txt)
    return "\n\n".join(blocks).strip()


def original_image_url(url):
    """Substack CDN links wrap the original upload (…/fetch/<opts>/https%3A%2F%2F…);
    return the original full-resolution file when present."""
    m = re.search(r"/(https?%3A%2F%2F.+)$", url or "")
    return urllib.parse.unquote(m.group(1)) if m else url


def cdn_url(original, width=1456):
    """Substack's image CDN copy of an original upload. Older posts keep their originals in a
    legacy S3 bucket ("bucketeer-…") that now refuses direct downloads; the CDN still serves them."""
    return ("https://substackcdn.com/image/fetch/"
            f"w_{width},c_limit,f_png,q_auto:good,fl_progressive:steep/{urllib.parse.quote(original, safe='')}")


def download_image(url, dest):
    """The original upload, or the CDN copy when the original host refuses."""
    try:
        return M.download(url, dest)
    except Exception:  # noqa: BLE001
        if "substackcdn.com" in url:
            raise
        return M.download(cdn_url(url), dest)


def inline_images(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    out = []
    for fig in soup.find_all(["figure", "img"]):
        img = fig if fig.name == "img" else fig.find("img")
        if not img:
            continue
        src = img.get("src") or ""
        srcset = img.get("srcset") or ""
        if srcset:  # take the widest candidate (Substack URLs contain commas, so no naive split)
            cands = re.findall(r"(\S+)\s+(\d+)w", srcset)
            if cands:
                src = max(cands, key=lambda c: int(c[1]))[0]
        src = original_image_url(src)
        cap = fig.find("figcaption") if fig.name == "figure" else None
        if src and src not in [o["url"] for o in out]:
            out.append({"url": src, "caption": cap.get_text(" ", strip=True) if cap else "",
                        "alt": img.get("alt", "")})
    return out


def fetch(url, project_dir):
    """Download post JSON via Substack's public API into project_dir."""
    project_dir = Path(project_dir)
    media_dir = project_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    parts = urllib.parse.urlparse(url)
    slug = slug_from_url(url)
    api = f"{parts.scheme or 'https'}://{parts.netloc}/api/v1/posts/{slug}"
    post = M.http_json(api)
    (project_dir / "post_raw.json").write_text(json.dumps(post, indent=2))
    authors = [b.get("name") for b in post.get("publishedBylines", []) if b.get("name")]
    pd = post.get("post_date")
    date_label = ""
    if pd:
        date_label = datetime.fromisoformat(pd.replace("Z", "+00:00")).strftime("%b %-d, %Y")
    article = {
        "url": post.get("canonical_url") or url,
        "slug": slug,
        "title": post.get("title", ""),
        "subtitle": post.get("subtitle", ""),
        "authors": authors,
        "post_date": pd,
        "date_label": date_label,
        "section": (post.get("section") or {}).get("name") if isinstance(post.get("section"), dict) else None,
        "publication": (post.get("publication") or {}).get("name") if isinstance(post.get("publication"), dict)
        else "American Inequality",
        "cover_image": original_image_url(post.get("cover_image")),
        "wordcount": post.get("wordcount"),
        "images": inline_images(post.get("body_html")),
    }
    (project_dir / "article.json").write_text(json.dumps(article, indent=2))
    (project_dir / "article.md").write_text(
        f"# {article['title']}\n\n_{article['subtitle']}_\n\n{', '.join(authors)} · {date_label}\n\n"
        + html_to_text(post.get("body_html")))
    # cover + inline images (charts from the article make great on-screen visuals)
    if article["cover_image"]:
        try:
            download_image(article["cover_image"], media_dir / "cover.jpg")
            M.save_credit(media_dir, "cover.jpg", {"credit": f"Image: {article['publication']}",
                                                   "url": article["cover_image"]})
        except Exception as e:  # noqa: BLE001
            print(f"  ! cover download failed: {e}")
    for i, im in enumerate(article["images"], 1):
        ext = Path(urllib.parse.urlparse(im["url"]).path).suffix.lower() or ".jpg"
        ext = ext if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif") else ".jpg"
        name = f"article_{i:02d}{ext}"
        try:
            download_image(im["url"], media_dir / name)
            M.save_credit(media_dir, name, {"credit": im["caption"][:120] or f"Chart: {article['publication']}",
                                            "url": im["url"]})
        except Exception as e:  # noqa: BLE001
            print(f"  ! image {i} download failed: {e}")
    return article


def from_manual(project_dir, title, subtitle="", authors=None, post_date=None, url="", text_file=None):
    """Create article.json by hand when the Substack API can't be reached."""
    project_dir = Path(project_dir)
    (project_dir / "media").mkdir(parents=True, exist_ok=True)
    date_label = ""
    if post_date:
        date_label = datetime.fromisoformat(post_date.replace("Z", "+00:00")).strftime("%b %-d, %Y")
    article = {"url": url, "slug": project_dir.name, "title": title, "subtitle": subtitle,
               "authors": authors or [], "post_date": post_date, "date_label": date_label,
               "publication": "American Inequality", "images": []}
    (project_dir / "article.json").write_text(json.dumps(article, indent=2))
    if text_file:
        (project_dir / "article.md").write_text(Path(text_file).read_text())
    return article
