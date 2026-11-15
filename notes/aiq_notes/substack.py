"""Minimal Substack Notes client.

Substack has no official API for Notes. This uses the same private endpoints
the substack.com web app calls, authenticated with your browser session
cookie (`substack.sid`). Endpoints can change without notice; if a post fails
the poster marks the note as `Error` and stops retrying it, so nothing goes
out twice or garbled.

Env:
  SUBSTACK_SID   value of the `substack.sid` cookie from a logged-in browser
"""
import base64
import mimetypes
import os
from pathlib import Path

import requests

BASE = "https://substack.com/api/v1"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0 Safari/537.36")


class SubstackError(RuntimeError):
    pass


def to_body_json(text: str) -> dict:
    """Plain text -> Substack's ProseMirror doc. Blank lines split paragraphs,
    single newlines become hard breaks (so stat 'ladders' keep their shape)."""
    paras = []
    for block in text.strip().split("\n\n"):
        content = []
        for j, line in enumerate(block.split("\n")):
            if j:
                content.append({"type": "hard_break"})
            if line:
                content.append({"type": "text", "text": line})
        paras.append({"type": "paragraph", "content": content})
    return {"type": "doc", "attrs": {"schemaVersion": "v1"}, "content": paras}


class Client:
    def __init__(self, sid=None):
        sid = sid or os.environ.get("SUBSTACK_SID")
        if not sid:
            raise SubstackError("SUBSTACK_SID is not set")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Origin": "https://substack.com",
                               "Referer": "https://substack.com/home"})
        self.s.cookies.set("substack.sid", sid, domain=".substack.com")

    def _req(self, method, path, **kw):
        r = self.s.request(method, BASE + path, timeout=60, **kw)
        if r.status_code >= 400:
            raise SubstackError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    # -- auth check -------------------------------------------------------
    def whoami(self):
        """Returns the logged-in user's id/handle, or raises."""
        for path in ("/user/profile/self", "/subscriber/self", "/user/self"):
            try:
                j = self._req("GET", path)
                if isinstance(j, dict) and (j.get("id") or j.get("user_id")):
                    return {"id": j.get("id") or j.get("user_id"), "handle": j.get("handle"), "via": path}
            except SubstackError:
                continue
        raise SubstackError("Could not confirm login. Is SUBSTACK_SID current?")

    # -- posting ------------------------------------------------------------
    def upload_image(self, path_or_url: str) -> str:
        if path_or_url.startswith("http"):
            r = requests.get(path_or_url, timeout=60)
            r.raise_for_status()
            data, mime = r.content, r.headers.get("content-type", "image/png").split(";")[0]
        else:
            data = Path(path_or_url).read_bytes()
            mime = mimetypes.guess_type(path_or_url)[0] or "image/png"
        uri = f"data:{mime};base64," + base64.b64encode(data).decode()
        j = self._req("POST", "/image", json={"image": uri})
        if not j.get("url"):
            raise SubstackError(f"image upload returned no url: {j}")
        return j["url"]

    def attach_image(self, image_url: str) -> str:
        j = self._req("POST", "/comment/attachment", json={"url": image_url, "type": "image"})
        if not j.get("id"):
            raise SubstackError(f"attachment returned no id: {j}")
        return j["id"]

    def post_note(self, text: str, image: str | None = None) -> dict:
        attachment_ids = []
        if image:
            attachment_ids.append(self.attach_image(self.upload_image(image)))
        payload = {"bodyJson": to_body_json(text), "tabId": "for-you", "surface": "feed",
                   "replyMinimumRole": "everyone"}
        if attachment_ids:
            payload["attachmentIds"] = attachment_ids
        j = self._req("POST", "/comment/feed", json=payload)
        return {"note_id": j.get("id"), "raw_keys": sorted(j.keys())[:20]}
