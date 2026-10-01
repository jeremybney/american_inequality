"""Find-and-clip news headlines: screenshot the headline area of a real article page.

The headless browser's requests are all fetched by Python (urllib), which verifies TLS
against the environment's CA bundle, then handed back to the page. That lets the
pre-installed Chromium render pages behind the agent proxy without weakening any
certificate checks.

clip(url, out_png) -> metadata dict:
    {ok, url, title, outlet, date, method: "screenshot"|"metadata"|"failed", reason?}
"""
import asyncio
import json
import os
import re
import urllib.error
import urllib.request
from html import unescape

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
CHROMIUM = os.environ.get("AIQ_CHROMIUM", "/opt/pw-browsers/chromium")
BLOCK = ("doubleclick", "googlesyndication", "googletag", "adservice", "analytics", "pixel",
         "scorecardresearch", "taboola", "outbrain", "chartbeat", "amazon-adsystem", "hotjar")


def _fetch(url, method="GET", headers=None, body=None, timeout=20):
    h = {k: v for k, v in (headers or {}).items()
         if k.lower() not in ("host", "content-length", "accept-encoding")}
    h.setdefault("User-Agent", UA)
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _meta_from_html(html):
    def m(name):
        pat = (r'<meta[^>]+(?:property|name)=["\']' + re.escape(name) +
               r'["\'][^>]*content=["\']([^"\']+)["\']')
        hit = re.search(pat, html, re.I) or re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']' + re.escape(name) + r'["\']', html, re.I)
        return unescape(hit.group(1)).strip() if hit else ""
    date = m("article:published_time") or m("datePublished") or m("parsely-pub-date")
    if not date:
        hit = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
        date = hit.group(1) if hit else ""
    title = m("og:title") or m("twitter:title")
    if not title:
        hit = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        title = unescape(hit.group(1)).strip() if hit else ""
    return {"title": title, "outlet": m("og:site_name"), "date": date, "dek": m("og:description")}


def nice_date(iso):
    from datetime import datetime
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")[:25])
        return d.strftime("%b %-d, %Y")
    except ValueError:
        return iso[:10]


FIND_HEADLINE_JS = r"""(title) => {
  const norm = s => (s || '').toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
  const want = norm(title).slice(0, 60);
  // hide cookie banners, paywall veils and sticky bars that would cover the headline
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if ((cs.position === 'fixed' || cs.position === 'sticky') && el.getBoundingClientRect().height > 40) el.style.display = 'none';
  }
  document.documentElement.style.overflow = 'auto'; document.body.style.overflow = 'auto';
  const cands = [...document.querySelectorAll('h1, h2, [class*="headline" i], [data-testid*="headline" i]')];
  let best = null, bestScore = -1;
  for (const el of cands) {
    const r = el.getBoundingClientRect();
    if (r.width < 200 || r.height < 20 || r.left < -50) continue;
    const t = norm(el.innerText);
    if (!t) continue;
    let score = parseFloat(getComputedStyle(el).fontSize) || 0;
    if (want && (t.startsWith(want.slice(0, 30)) || want.startsWith(t.slice(0, 30)))) score += 1000;
    if (score > bestScore) { bestScore = score; best = el; }
  }
  if (!best) return null;
  best.scrollIntoView({block: 'center'});
  const r = best.getBoundingClientRect();
  return {x: r.left, y: r.top + scrollY, w: r.width, h: r.height, text: best.innerText, matched: bestScore >= 1000};
}"""


async def _shoot(url, out_png, title):
    from playwright.async_api import async_playwright

    async def route(r):
        req = r.request
        if req.resource_type in ("media", "websocket", "eventsource", "font") or any(b in req.url for b in BLOCK):
            return await r.abort()
        try:
            st, hd, body = await asyncio.get_running_loop().run_in_executor(
                None, _fetch, req.url, req.method, req.headers, req.post_data_buffer)
            hd = {k: v for k, v in hd.items() if k.lower() not in
                  ("content-encoding", "transfer-encoding", "content-length", "content-security-policy")}
            await r.fulfill(status=st, headers=hd, body=body)
        except Exception:  # noqa: BLE001
            await r.abort()

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        try:
            ctx = await browser.new_context(viewport={"width": 480, "height": 1400}, device_scale_factor=2,
                                            user_agent=UA)
            await ctx.route("**/*", route)
            page = await ctx.new_page()
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            if resp and resp.status >= 400:
                return {"ok": False, "reason": f"page returned {resp.status}"}
            await page.wait_for_timeout(3000)
            box = await page.evaluate(FIND_HEADLINE_JS, title)
            if not box:
                return {"ok": False, "reason": "no headline element found"}
            await page.wait_for_timeout(500)
            box = await page.evaluate(FIND_HEADLINE_JS, title)  # after scroll
            top = max(0, box["y"] - 130)            # room for the outlet's name/logo above the headline
            height = box["h"] + 130 + 150           # and the dek or byline below
            await page.screenshot(path=out_png, full_page=True,
                                  clip={"x": 0, "y": top, "width": 480, "height": height})
            hy0 = (box["y"] - top) / height
            hy1 = (box["y"] - top + box["h"]) / height
            hx0 = max(0.0, box["x"] / 480 - 0.01)
            hx1 = min(1.0, (box["x"] + box["w"]) / 480 + 0.01)
            return {"ok": True, "headline": box["text"], "matched": box["matched"],
                    "highlight": [round(hx0, 3), round(hy0, 3), round(hx1, 3), round(hy1, 3)]}
        finally:
            await browser.close()


def clip(url, out_png):
    """Screenshot an article's headline; fall back to page metadata for a quoted card."""
    meta = {"url": url, "title": "", "outlet": "", "date": "", "dek": ""}
    try:
        st, _, body = _fetch(url, headers={"Accept": "text/html"})
        if st < 400:
            meta.update(_meta_from_html(body.decode("utf-8", "replace")))
        else:
            meta["reason"] = f"site returned {st} to automated requests"
    except Exception as e:  # noqa: BLE001
        meta["reason"] = f"fetch failed: {e}"
    meta["date_label"] = nice_date(meta.get("date"))
    if meta.get("reason"):
        meta.update({"ok": False, "method": "failed"})
        return meta
    try:
        res = asyncio.run(_shoot(url, str(out_png), meta.get("title", "")))
    except Exception as e:  # noqa: BLE001
        res = {"ok": False, "reason": f"browser failed: {e}"}
    if res.get("ok"):
        meta.update({"ok": True, "method": "screenshot", "matched": res.get("matched"),
                     "highlight": res.get("highlight")})
    else:
        meta.update({"ok": bool(meta.get("title")), "method": "metadata", "reason": res.get("reason")})
    return meta


if __name__ == "__main__":
    import sys
    print(json.dumps(clip(sys.argv[1], sys.argv[2]), indent=2))
