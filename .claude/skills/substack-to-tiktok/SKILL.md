---
name: substack-to-tiktok
description: Turn an American Inequality Substack article into a vertical (9:16) TikTok/Reels/Shorts video plus a voiceover script, in the Tal Roded data-explainer style with the American Inequality orange brand. Use whenever the user shares a Substack post link (americaninequality.substack.com/p/...) and wants a short-form video, TikTok, Reel, Short, or voiceover script from it.
---

# Substack → TikTok short

The pipeline lives in `shorts/`. You write the storyboard (the creative step);
the scripts fetch the article, source real photos, render the video, and
write the script. Work from the repo root.

```
python shorts/make_short.py new <substack-url>            # 1. fetch article → shorts/projects/<slug>/
# 2. read article.md, write storyboard.json
python shorts/make_short.py autofill <slug>                # 3. fetch every scene's `query` photo, then review
python shorts/make_short.py search <slug> "<query>"        #    or search by hand (Wikimedia)
python shorts/make_short.py search <slug> "<query>" --pexels --video   #    real footage (needs PEXELS_API_KEY)
python shorts/make_short.py pick <slug> <n> --as hook      #    save candidate #n as media/hook.<ext>
python shorts/make_short.py stills <slug>                  # 4. key-frame sheet → output/stills.png (LOOK AT IT)
python shorts/make_short.py render <slug>                  # 5. MP4 + script.md + captions.srt + credits + post
```
Dependencies: `pip install -r shorts/requirements.txt` (pillow, numpy, imageio-ffmpeg, beautifulsoup4).
Every scene type and field is documented in `shorts/storyboard_reference.md`.
Read it before writing a storyboard. `shorts/projects/boomers-wealth-millenials-gen-z/storyboard.json`
is a worked example.

## Step 1: Fetch
`new` calls Substack's public API and saves `article.json` (metadata),
`article.md` (full text), `media/cover.jpg`, and every inline image as
`media/article_NN.*` (the article's own charts can go straight into photo
scenes). If Substack is unreachable (network policy), ask the user to allow
`*.substack.com` and `substackcdn.com`, or to paste the article text. Then run
`new <url> --manual --title … --subtitle … --authors … --date … --text pasted.md`.
The Substack MCP `list_posts` tool also returns the title, subtitle, bylines and date.

## Step 2: Write the storyboard (the part that matters)
Target **55–80 seconds, 150–210 spoken words, 9–14 scenes** at `wpm: 170`.

The formula from the reference videos:
1. **Hook (0–5s): real photo + typed headline.** State the most surprising fact as a
   claim, then the turn in yellow: `"Boomers own half of America's wealth." / "Millennials own the debt."`
   Chip: `"<Topic> · American Inequality"`. The first spoken line must work with no context.
2. **Stakes (5–12s):** one more real photo beat that makes it concrete (a place, a person, an object).
3. **Article card (~12–18s):** "In March I wrote about…" plus 2–3 chips previewing the structure
   ("WHO OWNS IT", "WHY", "WHAT FIXES IT").
4. **Evidence (the middle, 4–7 beats):** one number per beat, each shown by the chart that
   makes its *scale* obvious:
   - share of a whole → `waffle` or `stacked`
   - two things compared → `vbars` (with a "2x" annotation) or `stacked` (population vs wealth)
   - several categories → `hbars`
   - change over time → `line` with a `counter`
   - before vs after → `then_now`
   - one shocking figure → `big_number`, or `stat` overlay on a photo
   - causes / to-dos → `checklist`
   Alternate charts with photo beats: roughly **one real photo every 2–3 scenes**, so it
   never feels like a slideshow. Whenever the script names a place, building or thing
   (a city, a neighbourhood, a type of home, a landmark), show *that* place: e.g.
   "Los Angeles" → an LA street or aerial, "D.C." → D.C. rowhouses or the Capitol,
   "three-bedroom homes" → a real family house. A strong pattern is a **blurred real
   photo with a giant count-up stat on top** (`blur: 8`, `overlays: [{"kind": "stat", …}]`).
5. **Turn / so-what:** a `statement` scene with the takeaway, key words in {braces}.
6. **Outro:** "Full story on American Inequality" over the end card.

Script rules:
- Write for the ear. Short sentences, one idea per `say` line, ≤ 12 words per line.
  Spell numbers the way they're spoken ("fifty-one percent", "eighty-four trillion dollars").
- The narration and the chart must say the same number at the same moment.
- **Every number must come from the article** (or its cited source). Put the source in
  that scene's `source` field. Never invent or "round up" a statistic. If a figure isn't
  in the article, leave it out, or set `"draft": true` and list it in `notes`.
- First person, the author's voice ("I wrote", "I found"). No hype words, no "Let's dive in".
- Fill `post.caption` (one or two sentences) and 5–8 `post.hashtags`.

## Step 3: Media (no AI slop)
Give every photo scene a specific `query` (place + subject, e.g. "Washington DC rowhouses
Capitol Hill"), then run `autofill`: it saves the top result and a contact sheet per scene at
`.cache/candidates/<name>/contact_sheet.jpg`. Review each sheet and, if a better candidate
exists, `search` + `pick` it by hand.

Use **real photographs and footage of real places**. Never generated images.
- Search Wikimedia Commons first: it's freely licensed and attributed, and the credit
  prints on screen automatically. Use Pexels (`--pexels`, add `--video` for clips)
  for real stock footage of generic scenes: streets, homes, workers, city life.
- ALWAYS open the contact sheet (`.cache/candidates/contact_sheet.jpg`) and look
  before picking. Reject anything blurry, watermarked, low-res, stock-cheesy (people
  pointing at laptops, handshake photos), AI-looking, or off-topic. Prefer
  documentary / photojournalistic images with a clear subject and a natural 9:16 crop.
- Use `focus` to frame the subject in the vertical crop. If no good image exists for
  a beat, replace that beat with a chart scene rather than using a weak photo.
- The article's own charts (`media/article_NN.png`) work well as a photo beat with `dim: 0.1`.
- If image hosts are blocked by the environment's network policy, tell the user which
  hosts to allow (`commons.wikimedia.org`, `upload.wikimedia.org`, `api.pexels.com`,
  `images.pexels.com`, `videos.pexels.com`) or ask them to drop photos into `media/`.

## Step 4: QA before rendering
Run `stills` and view `output/stills.png` (2 frames per scene). Check for:
text colliding with captions (captions occupy y≈1440–1600), numbers that don't
match the narration, orphaned words, empty-looking scenes, placeholders
("[ add media … ]"), and photos whose subject is cropped out. Fix, re-run, then render.
Use `frame <slug> <seconds>` to inspect one frame at full size.

## Step 5: Render and hand off
`render` writes to `shorts/projects/<slug>/output/`:
- `<slug>.mp4`: 1080×1920, 30fps, H.264, silent audio track, captions burned in
  (`--no-captions` renders a clean version)
- `script.md`: the voiceover to read, with timed shot list and per-line cues
- `captions.srt`, `credits.md`, `tiktok_post.txt`

Send the user the MP4 and `script.md` (SendUserFile), summarize the runtime and word
count, and list any `notes`/warnings. Commit the project folder (the storyboard, article
and media; outputs are gitignored) and push to the working branch.

## Brand (shorts/aiq_shorts/theme.py)
Orange `#fc5528` background · titles `#fef8fb` · subtitles/author/labels navy `#003375`.
Data colours: navy + white first, light blue `#0098c6` third, yellow `#f1e827` for the one
number that matters, green `#008c39` sparingly, dark blue `#004c90`, gold `#ffb100` for accents.
Fonts: IBM Plex Mono (headlines, numbers, labels) and Inter (captions, titles).
