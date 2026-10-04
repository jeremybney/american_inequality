"""Visual plan: decide which pictures a story needs before writing the storyboard.

The rule, applied to every article:
  1. The author's own MAPS and distinctive graphics are reused (shown on a card
     with a slow push into the key area). Ordinary line/bar charts are rebuilt as
     native animated chart scenes using the article's numbers.
  2. Every PLACE the story names (city, state, D.C.) gets a real photo of that place.
  3. Every INSTITUTION gets its building (Congress -> the Capitol, the Fed -> Eccles).
  4. Every recurring THEME gets a documentary photo of the concrete thing
     (housing -> real houses; tuition -> a campus; immigration -> Ellis Island).
  5. When the story talks about an ERA (the 1950s baby boom), prefer a
     public-domain historical photo from that era.
Subjects are ranked by how central they are (title/subtitle, opening paragraph,
number of mentions), and candidates come from Wikimedia Commons, preferring its
curated "Quality images" / "Featured pictures" sets.
"""
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from . import media as M
from . import theme as T
from .gfx import font

# --- Gazetteer: places -> iconic, photographable queries --------------------------------
CITIES = {
    "New York City": ["Manhattan skyline", "New York City street apartment buildings"],
    "Los Angeles": ["Aerial photographs of Los Angeles", "Los Angeles skyline", "Los Angeles neighborhood houses"],
    "Chicago": ["Chicago skyline", "Chicago bungalow neighborhood"],
    "Houston": ["Houston skyline", "Houston suburb aerial"],
    "Phoenix": ["Phoenix Arizona suburb aerial", "Phoenix skyline"],
    "Philadelphia": ["Philadelphia rowhouses", "Philadelphia skyline"],
    "San Antonio": ["San Antonio skyline"],
    "San Diego": ["San Diego skyline"],
    "Dallas": ["Dallas skyline"],
    "Austin": ["Austin Texas skyline"],
    "San Francisco": ["San Francisco Victorian houses", "San Francisco skyline"],
    "San Jose": ["San Jose California skyline"],
    "Seattle": ["Seattle skyline"],
    "Denver": ["Denver skyline"],
    "Boston": ["Boston brownstones", "Boston skyline"],
    "Detroit": ["Detroit skyline", "Detroit abandoned houses"],
    "Miami": ["Miami skyline"],
    "Atlanta": ["Atlanta skyline"],
    "Nashville": ["Nashville skyline"],
    "Las Vegas": ["Las Vegas suburb aerial"],
    "Portland": ["Portland Oregon skyline"],
    "Baltimore": ["Baltimore rowhouses"],
    "Cleveland": ["Cleveland skyline"],
    "St. Louis": ["Gateway Arch St. Louis"],
    "New Orleans": ["New Orleans shotgun houses", "French Quarter New Orleans"],
    "Minneapolis": ["Minneapolis skyline"],
    "Pittsburgh": ["Pittsburgh skyline"],
    "Memphis": ["Memphis Tennessee downtown"],
    "Birmingham": ["Birmingham Alabama skyline"],
    "Flint": ["Flint Michigan"],
    "Appalachia": ["Appalachia town West Virginia"],
    "Silicon Valley": ["Silicon Valley aerial"],
    "Washington, D.C.": ["Washington DC rowhouses", "Washington DC aerial Capitol"],
}
CITY_ALIASES = {"D.C.": "Washington, D.C.", "Washington D.C.": "Washington, D.C.", "DC": "Washington, D.C.",
                "NYC": "New York City", "New York": "New York City", "L.A.": "Los Angeles", "LA": "Los Angeles"}
STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
          "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
          "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
          "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico",
          "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
          "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
          "Washington State", "West Virginia", "Wisconsin", "Wyoming"]

# --- Institutions -> their buildings -------------------------------------------------------------
INSTITUTIONS = {
    "congress": (["Congress", "Senate", "House of Representatives", "lawmakers", "legislat"],
                 ["United States Capitol", "United States Capitol dome"]),
    "supreme_court": (["Supreme Court"], ["Supreme Court of the United States building"]),
    "white_house": (["White House", "Oval Office", "president"], ["White House north facade"]),
    "federal_reserve": (["Federal Reserve", "the Fed "], ["Marriner S. Eccles Federal Reserve Board Building"]),
    "wall_street": (["Wall Street", "stock market", "stocks", "S&P"], ["New York Stock Exchange facade"]),
    "irs": (["IRS", "tax code", "tax structure"], ["Internal Revenue Service building"]),
}

# --- Recurring American Inequality themes -> concrete subjects ----------------------------------
THEMES = {
    "housing": (["housing", "home price", "homes", "homeowner", "real estate", "mortgage"],
                ["Suburbs in the United States", "houses in the United States street", "aerial suburb subdivision"]),
    "big_homes": (["bedroom", "square feet", "large homes", "bigger homes", "mcmansion"],
                  ["McMansions", "large suburban house United States", "new subdivision houses"]),
    "construction": (["construction", "building fewer homes", "housing development", "zoning"],
                     ["houses under construction in the United States", "house framing construction"]),
    "renting": (["rent", "renter", "tenant", "apartment", "eviction"],
                ["apartment building United States", "for rent sign apartment"]),
    "homelessness": (["homeless", "encampment", "unhoused"], ["homeless encampment street"]),
    "college": (["college", "tuition", "student debt", "student loan", "university", "higher education"],
                ["university campuses in the United States", "graduation ceremony gowns"]),
    "schools": (["school", "classroom", "teacher", "students"],
                ["public school classroom United States", "school building"]),
    "credit_debt": (["credit card", "debt"], ["Credit cards", "credit card payment terminal"]),
    "retirement": (["retire", "retirement", "social security", "pension", "seniors", "elderly"],
                   ["retirement communities in the United States", "The Villages Florida", "senior citizens"]),
    "wages_work": (["wage", "worker", "labor", "jobs", "employment", "union"],
                   ["factory workers assembly line", "warehouse workers"]),
    "healthcare": (["health care", "healthcare", "hospital", "medical", "insurance", "life expectancy"],
                   ["hospital emergency department", "hospital corridor"]),
    "childcare": (["childcare", "child care", "daycare"], ["daycare center children playing"]),
    "immigration": (["immigra", "foreign born", "newcomers"],
                    ["Ellis Island immigrants", "naturalization ceremonies in the United States"]),
    "voting": (["vote", "voting", "voter", "election", "ballot"], ["polling place voters", "voting booth"]),
    "civil_rights": (["civil rights"], ["March on Washington 1963", "civil rights march"]),
    "food": (["food insecurity", "food bank", "hunger", "snap benefits", "food stamps"],
             ["food bank volunteers", "grocery store aisle"]),
    "rural": (["rural", "farm", "small town"], ["rural main street small town", "farmland barn"]),
    "wealth_top": (["billionaire", "top 1%", "top 10%", "wealthiest", "the rich"],
                   ["Manhattan luxury apartments skyline", "mansion estate"]),
    "transit": (["transit", "commute", "subway", "highway"], ["highway traffic", "subway platform"]),
    "guns": (["gun", "firearm", "shooting"], ["memorial candles vigil"]),
    "climate": (["climate", "heat wave", "flood", "wildfire", "hurricane"],
                ["wildfire smoke neighborhood", "flooded street"]),
    "prison": (["prison", "incarceration", "jail"], ["prison fence"]),
    "shopping": (["consumer", "retail sales", "shopping"], ["shopping mall 1960s", "retail store"]),
    "television": (["television", "tv "], ["1950s family watching television"]),
}
# Era-specific historical subjects, used when an era is mentioned near a theme
ERAS = {
    "baby_boom": (["baby boom", "boomer years", "1946", "post-war", "postwar", "1950s", "50's", "50s"],
                  ["Levittown, New York", "1950s in the United States suburb", "baby carriages 1950s"]),
    "sixties": (["1960s", "60s", "60's"], ["1960s college campus protest", "1960s street"]),
    "seventies": (["1970s", "1973", "1975", "1976"], ["1970s suburban street"]),
    "depression": (["great depression", "1930s"], ["Great Depression breadline"]),
}
THEME_NOUN = {"housing": "houses", "big_homes": "large houses", "construction": "housing construction",
              "renting": "apartments", "homelessness": "homeless encampment", "college": "university",
              "schools": "school", "retirement": "retirees", "wages_work": "workers", "healthcare": "hospital",
              "immigration": "immigrants", "voting": "voters", "civil_rights": "civil rights march",
              "rural": "farm", "wealth_top": "mansions", "transit": "freeway", "climate": "wildfire"}
ERA_WORD = {"baby_boom": "1950s", "sixties": "1960s", "seventies": "1970s", "depression": "1930s"}
BAD_TITLE = re.compile(r"\b(map|logo|seal|flag|chart|diagram|graph|coat of arms|svg|icon|locator|plan)\b", re.I)
MAP_WORDS = re.compile(r"\b(map|county|counties|by state|state by state|zip code|metro area|choropleth|"
                       r"district map|across the country|across america)\b", re.I)


def _sentences(text):
    # drop headings, figure captions and boilerplate so evidence is real prose
    lines = [ln for ln in text.splitlines()
             if ln.strip() and not ln.lstrip().startswith(("#", "[Figure caption]", "_", "- "))]
    text = " ".join(lines)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text)) if s.strip()]


def _context_queries(place, ev_sents):
    """Place + what the story says about it, e.g. 'Los Angeles school 1950s'."""
    out = []
    for s in ev_sents:
        nouns = [THEME_NOUN[k] for k, (words, _) in THEMES.items() if k in THEME_NOUN and _count(s, words)]
        era = next((ERA_WORD[k] for k, (words, _) in ERAS.items() if _count(s, words)), "")
        for n in nouns[:2]:
            out.append(f"{place} {n} {era}".strip())
        if era and not nouns:
            out.append(f"{place} {era}")
    return list(dict.fromkeys(out))


def _count(text, words):
    n = 0
    for w in words:
        if w.endswith(" ") or not w[-1].isalpha():
            n += text.lower().count(w.lower())
        else:
            n += len(re.findall(r"\b" + re.escape(w.lower()), text.lower()))
    return n


def _evidence(sents, words, k=2):
    out = []
    for s in sents:
        if _count(s, words):
            out.append(s if len(s) < 220 else s[:217] + "…")
            if len(out) >= k:
                break
    return out


def find_subjects(article, body):
    """Rank photographable subjects mentioned in the article."""
    head = f"{article.get('title', '')} {article.get('subtitle', '')}"
    first = body[:1200]
    sents = _sentences(body)
    subjects = []

    def add(key, kind, label, words, queries):
        n = _count(body, words)
        if not n:
            return
        score = n + 3 * _count(head, words) + 1.5 * _count(first, words)
        subjects.append({"key": key, "kind": kind, "label": label, "mentions": n, "score": round(score, 1),
                         "queries": queries, "evidence": _evidence(sents, words)})

    for city, qs in CITIES.items():
        words = [city] + [a for a, c in CITY_ALIASES.items() if c == city]
        # case-sensitive aliases like "DC"/"LA" need exact matching
        n = sum(len(re.findall(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", body)) for w in words)
        if n:
            score = n + 3 * sum(head.count(w) for w in words) + 1.5 * sum(first.count(w) for w in words)
            ev = [s for s in sents if any(re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", s)
                                          for w in words)][:3]
            place = city.replace("Washington, D.C.", "Washington DC")
            subjects.append({"key": "place_" + re.sub(r"\W+", "_", city.lower()).strip("_"), "kind": "place",
                             "label": city, "mentions": n, "score": round(score + 2, 1),
                             "queries": _context_queries(place, ev) + qs, "evidence": ev[:2]})
    for st in STATES:
        n = len(re.findall(r"\b" + re.escape(st) + r"\b", body))
        if n:
            ev = [s for s in sents if st in s][:3]
            subjects.append({"key": "place_" + st.lower().replace(" ", "_"), "kind": "place", "label": st,
                             "mentions": n, "score": n + 1,
                             "queries": _context_queries(st, ev) + [f"{st} landscape town", f"{st} main street"],
                             "evidence": ev[:2]})
    for key, (words, qs) in INSTITUTIONS.items():
        add(key, "institution", key.replace("_", " ").title(), words, qs)
    for key, (words, qs) in THEMES.items():
        add(key, "theme", key.replace("_", " ").title(), words, qs)
    for key, (words, qs) in ERAS.items():
        add(key, "era", key.replace("_", " ").title(), words, qs)
    subjects.sort(key=lambda s: -s["score"])
    return subjects


def classify_article_images(article):
    """Label each article image: reuse (maps / distinctive graphics) or rebuild (standard charts)."""
    out = []
    for i, im in enumerate(article.get("images", []), 1):
        cap = f"{im.get('caption', '')} {im.get('alt', '')}".strip()
        is_map = bool(MAP_WORDS.search(cap))
        out.append({"file": None, "index": i, "caption": cap,
                    "suggest": "reuse (map)" if is_map else "rebuild as chart scene — or reuse if it's a map "
                                                           "or a distinctive graphic (check the sheet)"})
    return out


def wikimedia_candidates(query, n=6, enough=None):
    """Curated categories, then curated Quality/Featured images, then full-text search."""
    seen, out = set(), []
    # Curated categories first (most precise for places & themes), then the curated
    # Quality/Featured sets (great for landmarks, loose for generic words), then full text.
    sources = [
        ("category", lambda: M.search_wikimedia_categories(query, n=12)),
        ("quality", lambda: M.search_wikimedia(f"{query} incategory:Quality_images|Featured_pictures_on_Wikimedia_Commons",
                                               n=12, min_width=1600)),
        ("text", lambda: M.search_wikimedia(query, n=12, min_width=1600)),
    ]
    for tag, fn in sources:
        try:
            res = fn()
        except Exception as e:  # noqa: BLE001
            print(f"    {tag} search failed ({query}): {e}")
            continue
        for c in res:
            if c["id"] in seen or BAD_TITLE.search(c["title"]):
                continue
            seen.add(c["id"])
            c["query"], c["via"], c["quality"] = query, tag, tag == "quality"
            out.append(c)
        if len(out) >= (enough or n):
            break
    return out[:n]


def subject_candidates(queries, per):
    """Round-robin across a subject's queries so no single query crowds out the rest.
    Each query stops early once it has its share, which keeps a plan to a few minutes."""
    qs = queries[:3]
    share = -(-per // len(qs)) + 1  # ceil(per / n) + 1 spare
    pools = [wikimedia_candidates(q, per, enough=share) for q in qs]
    out, seen = [], set()
    while len(out) < per and any(pools):
        for pool in pools:
            while pool:
                c = pool.pop(0)
                if c["id"] not in seen:
                    seen.add(c["id"])
                    out.append(c)
                    break
    return out[:per]


def article_image_sheet(project_dir, article, out_path):
    media_dir = Path(project_dir) / "media"
    files = sorted(media_dir.glob("article_*"))
    if not files:
        return None
    tw, th = 520, 420
    cols = 3
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    f = font("mono", 18)
    caps = {f"article_{i:02d}": im.get("caption", "") for i, im in enumerate(article.get("images", []), 1)}
    for k, p in enumerate(files):
        x, y = (k % cols) * tw, (k // cols) * th
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((tw - 16, th - 60))
            sheet.paste(im, (x + 8, y + 50))
        except Exception:  # noqa: BLE001
            pass
        d.text((x + 8, y + 6), p.name, font=f, fill=T.ORANGE)
        d.text((x + 8, y + 28), caps.get(p.stem, "")[:52], font=font("mono_med", 15), fill=T.NAVY)
    sheet.save(out_path, quality=88)
    return out_path


def candidate_sheet(cands, thumbs_dir, out_path, title):
    tiles = []
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(cands):
        tp = thumbs_dir / f"{i:02d}.jpg"
        try:
            if not tp.exists():
                M.download(c["thumb"], tp)
            tiles.append(ImageOps.fit(Image.open(tp).convert("RGB"), (240, 426)))
        except Exception:  # noqa: BLE001
            tiles.append(Image.new("RGB", (240, 426), (40, 40, 40)))
    sheet = Image.new("RGB", (max(1, len(tiles)) * 250 + 10, 500), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), title[:90], font=font("mono", 22), fill=T.YELLOW)
    for i, im in enumerate(tiles):
        x = 10 + i * 250
        sheet.paste(im, (x, 40))
        c = cands[i]
        d.text((x + 4, 470), f"#{i} {c['width']}x{c['height']} {c.get('via', '')[:4]}",
               font=font("mono", 18), fill=T.TITLE)
    sheet.save(out_path, quality=85)
    return out_path


def plan(project_dir, top=12, per=6, fetch=True, only=None):
    project_dir = Path(project_dir)
    article = json.loads((project_dir / "article.json").read_text())
    body = (project_dir / "article.md").read_text() if (project_dir / "article.md").exists() else ""
    body = body.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    subjects = find_subjects(article, body)
    # Places and institutions are the most "Tal-like" visuals (show the actual place the
    # script names), so they're always included even with a single mention; themes and
    # eras fill the remaining slots by score.
    must = [s for s in subjects if s["kind"] == "place"][:4] + \
           [s for s in subjects if s["kind"] == "institution"][:2]
    rest = [s for s in subjects if s not in must]
    chosen = must + rest[:max(0, top - len(must))]
    pdir = project_dir / ".cache" / "plan"
    pdir.mkdir(parents=True, exist_ok=True)
    art_sheet = article_image_sheet(project_dir, article, pdir / "article_images.jpg")
    prev = {}
    prev_path = pdir / "visual_plan.json"
    if only and prev_path.exists():  # keep earlier results for subjects we aren't re-running
        prev = {s["key"]: s for s in json.loads(prev_path.read_text()).get("subjects", [])}
    for s in chosen:
        s["candidates"] = []
        if only and s["key"] not in only:
            s.update({k: prev[s["key"]][k] for k in ("candidates", "sheet") if k in prev.get(s["key"], {})})
            continue
        if not fetch:
            continue
        s["candidates"], _hidden = M.fresh_only(project_dir, subject_candidates(s["queries"], per))
        if s["candidates"]:
            s["sheet"] = str(candidate_sheet(s["candidates"], pdir / s["key"], pdir / f"{s['key']}.jpg",
                                             f"{s['label']}  ({s['kind']}, score {s['score']})"))
        print(f"  {s['label']:<24} {s['kind']:<12} score {s['score']:<5} {len(s['candidates'])} candidates")
    images = classify_article_images(article)
    out = {"subjects": chosen, "article_images": images, "article_image_sheet": str(art_sheet) if art_sheet else None}
    (pdir / "visual_plan.json").write_text(json.dumps(out, indent=2))
    md = ["# Visual plan", "", "## Article images (reuse maps & distinctive graphics; rebuild plain charts)", ""]
    for im in images:
        md.append(f"- `article_{im['index']:02d}` — {im['caption'] or '(no caption)'} → **{im['suggest']}**")
    md += ["", f"Sheet: `{art_sheet}`" if art_sheet else "", "", "## Photo subjects (ranked)", ""]
    for s in chosen:
        md.append(f"### {s['label']} · {s['kind']} · score {s['score']} · {s['mentions']} mentions")
        for e in s["evidence"]:
            md.append(f"> {e}")
        md.append(f"Queries: {', '.join(s['queries'])}")
        if s.get("sheet"):
            md.append(f"Candidates: `{s['sheet']}` — pick with "
                      f"`make_short.py use <slug> {s['key']} <n> --as <name>`")
        md.append("")
    (project_dir / "visual_plan.md").write_text("\n".join(md))
    return out


def use_candidate(project_dir, key, n, as_name):
    project_dir = Path(project_dir)
    data = json.loads((project_dir / ".cache" / "plan" / "visual_plan.json").read_text())
    subj = next((s for s in data["subjects"] if s["key"] == key), None)
    if not subj:
        raise SystemExit(f"No subject {key!r}; options: {[s['key'] for s in data['subjects']]}")
    c = subj["candidates"][n]
    M.ensure_fresh(project_dir, c)
    if c.get("source") == "wikimedia":
        c["url"] = M.best_url(c["url"], c.get("thumb"), c.get("width", 0))
    ext = Path(c["url"].split("?")[0]).suffix.lower() or ".jpg"
    name = f"{as_name}{ext}"
    M.download(c["url"], project_dir / "media" / name)
    M.save_credit(project_dir / "media", name, {"credit": c["credit"], "url": c.get("page")})
    return name, c
