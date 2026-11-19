"""Post notes to Bluesky with the official AT Protocol API.

Env (GitHub Actions secrets): BLUESKY_HANDLE (e.g. jeremybney.bsky.social),
BLUESKY_APP_PASSWORD (Settings > Privacy and security > App passwords).
"""
from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image

PDS = "https://bsky.social/xrpc"
MAX_BLOB = 950_000          # Bluesky rejects images over ~1 MB


class BskyError(RuntimeError):
    pass


def _check(r, what):
    if r.status_code >= 400:
        hint = ""
        if r.status_code == 401:
            hint = " (handle or app password rejected: re-check both secrets)"
        elif r.status_code == 429:
            hint = " (rate limited)"
        raise BskyError(f"{what} -> HTTP {r.status_code}{hint}: {r.text[:300]}")
    return r.json() if r.content else {}


def session():
    h, p = os.environ.get("BLUESKY_HANDLE"), os.environ.get("BLUESKY_APP_PASSWORD")
    if not h or not p:
        raise BskyError("missing GitHub secrets: " + ", ".join(k for k, v in
                        (("BLUESKY_HANDLE", h), ("BLUESKY_APP_PASSWORD", p)) if not v))
    h = h.strip().lstrip("@").replace("https://bsky.app/profile/", "")
    j = _check(requests.post(f"{PDS}/com.atproto.server.createSession",
                             json={"identifier": h, "password": p.strip()}, timeout=60), "login")
    return {"did": j["did"], "handle": j["handle"], "jwt": j["accessJwt"]}


def _image_bytes(path):
    """PNG if it fits under Bluesky's limit; otherwise a high-quality JPEG, shrinking until it fits."""
    im = Image.open(path).convert("RGB")
    raw = Path(path).read_bytes()
    if len(raw) <= MAX_BLOB and path.lower().endswith(".png"):
        return raw, "image/png", im.size
    w = im.width
    for q in (90, 85, 80, 75):
        for scale in (1.0, 0.85, 0.7, 0.55):
            buf = io.BytesIO()
            im.resize((int(w * scale), int(im.height * scale))).save(buf, "JPEG", quality=q, optimize=True)
            if buf.tell() <= MAX_BLOB:
                return buf.getvalue(), "image/jpeg", (int(w * scale), int(im.height * scale))
    raise BskyError("could not shrink image under 1 MB")


def upload_image(s, path):
    data, mime, size = _image_bytes(path)
    j = _check(requests.post(f"{PDS}/com.atproto.repo.uploadBlob", data=data, timeout=120,
                             headers={"Authorization": f"Bearer {s['jwt']}", "Content-Type": mime}), "image upload")
    return j["blob"], size


def post(text: str, image: str | None = None, alt: str = "") -> dict:
    s = session()
    rec = {"$type": "app.bsky.feed.post", "text": text, "langs": ["en"],
           "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    if image:
        blob, (w, h) = upload_image(s, image)
        rec["embed"] = {"$type": "app.bsky.embed.images",
                        "images": [{"alt": alt[:2000], "image": blob, "aspectRatio": {"width": w, "height": h}}]}
    j = _check(requests.post(f"{PDS}/com.atproto.repo.createRecord", timeout=60,
                             headers={"Authorization": f"Bearer {s['jwt']}"},
                             json={"repo": s["did"], "collection": "app.bsky.feed.post", "record": rec}), "create post")
    rkey = j.get("uri", "").rsplit("/", 1)[-1]
    return {"uri": j.get("uri"), "url": f"https://bsky.app/profile/{s['handle']}/post/{rkey}"}
