"""Post notes to X with the official API (OAuth 1.0a user context).

Env (GitHub Actions secrets): X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET.
The access token must have been generated with Read and Write permissions.
"""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path

import requests
from requests_oauthlib import OAuth1

API = "https://api.x.com/2"
UPLOAD_V1 = "https://upload.twitter.com/1.1/media/upload.json"


class XError(RuntimeError):
    pass


def _auth():
    keys = [os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")]
    if not all(keys):
        missing = [k for k, v in zip(("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"), keys) if not v]
        raise XError(f"missing GitHub secrets: {', '.join(missing)}")
    return OAuth1(*keys)


def _check(r, what):
    if r.status_code >= 400:
        hint = ""
        if r.status_code == 401:
            hint = " (keys rejected: re-copy all four secrets, and regenerate the access token after setting Read and Write)"
        elif r.status_code == 403:
            hint = (" (forbidden: the app lacks Read and Write, or your X API plan doesn't allow this endpoint; "
                    "check the plan/usage page in the developer portal)")
        elif r.status_code == 429:
            hint = " (rate or monthly limit reached for your X API plan)"
        raise XError(f"{what} -> HTTP {r.status_code}{hint}: {r.text[:300]}")
    return r.json() if r.content else {}


def whoami():
    j = _check(requests.get(f"{API}/users/me", auth=_auth(), timeout=60), "GET /2/users/me")
    d = j.get("data", {})
    return {"id": d.get("id"), "username": d.get("username"), "name": d.get("name")}


def upload_image(path: str, alt: str | None = None) -> str:
    """Upload a chart; returns media_id. Tries the v2 endpoint, falls back to v1.1."""
    data = Path(path).read_bytes()
    mime = mimetypes.guess_type(path)[0] or "image/png"
    auth = _auth()
    r = requests.post(f"{API}/media/upload", auth=auth, timeout=120,
                      files={"media": (Path(path).name, data, mime)},
                      data={"media_category": "tweet_image", "media_type": mime})
    if r.status_code < 400:
        j = r.json()
        mid = (j.get("data") or {}).get("id") or j.get("media_id_string")
    else:
        v2_error = f"v2 {r.status_code}: {r.text[:150]}"
        r = requests.post(UPLOAD_V1, auth=auth, timeout=120, files={"media": (Path(path).name, data, mime)})
        try:
            mid = _check(r, "media upload (v1.1)").get("media_id_string")
        except XError as e:
            raise XError(f"{e} | earlier {v2_error}")
    if not mid:
        raise XError(f"media upload returned no id: {r.text[:200]}")
    if alt:
        requests.post("https://api.x.com/1.1/media/metadata/create.json", auth=auth, timeout=60,
                      json={"media_id": mid, "alt_text": {"text": alt[:1000]}})   # best effort
    return mid


def post(text: str, image: str | None = None, alt: str | None = None) -> dict:
    body = {"text": text}
    if image:
        body["media"] = {"media_ids": [upload_image(image, alt)]}
    j = _check(requests.post(f"{API}/tweets", auth=_auth(), json=body, timeout=60), "POST /2/tweets")
    tid = (j.get("data") or {}).get("id")
    return {"tweet_id": tid, "url": f"https://x.com/i/status/{tid}" if tid else None}
