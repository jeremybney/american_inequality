# American Inequality Shorts

Turns an American Inequality Substack article into a vertical 1080×1920 video
for TikTok / Reels / Shorts, plus the voiceover script to record over it.

The style follows the data explainers by Tal Roded: a real photo and a typed
headline for the hook, the article card, then one animated chart per number
(bars, waffles, count-ups, lines), with captions burned in. It's rebuilt in the
American Inequality brand: orange background, cream titles, navy labels.

## The fast way (Claude Code)

Paste the Substack link into Claude Code in this repo and ask for a TikTok. The
`substack-to-tiktok` skill (`.claude/skills/substack-to-tiktok/SKILL.md`) runs
every step below: it writes the storyboard from the article, picks real photos,
QA-checks the frames, renders, and hands back the MP4 plus `script.md`.

## The Shorts Queue

Drop links into the **Shorts Queue** page (https://claude.ai/artifact/Pi2uynjVTBEhzNg9bDMBSB)
instead of pasting them into chat. Then tell Claude Code "make the queued shorts": it
works through the queue, marks each link Making and then Ready, and writes the runtime
and file location back to the page. Mark videos Posted on the page when they go up.

## By hand

```bash
pip install -r shorts/requirements.txt
python shorts/make_short.py doctor            # checks network access + API keys

python shorts/make_short.py new https://americaninequality.substack.com/p/<slug>
#  → shorts/projects/<slug>/article.md, article.json, media/cover.jpg, media/article_*.png

python shorts/make_short.py plan <slug>
#  → visual_plan.md: which photos this story needs (places, buildings, themes, eras),
#    ranked, with Wikimedia candidates; plus which article images to reuse (maps)
python shorts/make_short.py use <slug> congress 3 --as capitol          # save a plan candidate

#  write shorts/projects/<slug>/storyboard.json  (see storyboard_reference.md)

python shorts/make_short.py autofill <slug>                            # fetch each scene's `query` photo
python shorts/make_short.py search <slug> "suburban house florida"      # Wikimedia Commons
python shorts/make_short.py search <slug> "apartment renters" --video   # stock clips, needs PIXABAY_API_KEY
python shorts/make_short.py pick <slug> 3 --as hook                     # → media/hook.jpg (+ credit)

python shorts/make_short.py stills <slug>     # output/stills.png: key frames for review
python shorts/make_short.py render <slug>     # output/<slug>.mp4 + script.md + captions.srt
```

Rendering a 60-second video takes about 1.5 minutes on 4 cores.

## Outputs (`shorts/projects/<slug>/output/`)

| file | what it is |
|---|---|
| `<slug>.mp4` | the video with burned-in captions (`render --no-captions` for a clean cut) |
| `script.md` | **the voiceover to read**, a timed shot list, and a cue for each line |
| `captions.srt` | caption timings, if you'd rather caption in your editor |
| `credits.md` | photo credits and data sources shown on screen |
| `tiktok_post.txt` | post caption + hashtags + article link |

## Recording the voiceover

Upload the recording on the Shorts Queue page and tell Claude "sync my voiceovers", or run
`python shorts/make_short.py voice <slug> <recording>`. The voice that goes into the video is
studio-cleaned automatically (`aiq_shorts/enhance.py`): a neural model (DeepFilterNet 3)
removes the room echo and background noise that make a phone memo sound hollow, then the tone
is EQ'd toward a close-mic voice, de-essed, compressed and leveled to -14 LUFS. To clean any
recording on its own and compare by ear:

```bash
python shorts/make_short.py enhance my_take.m4a --out cleaned/
#  → cleaned/my_take_studio.wav, my_take_before.mp3, my_take_after.mp3
```

Cleanup can't fully rescue a bad room. For the best result record close to the mic (earbuds
like AirPods are ideal), in a small room with soft furnishings, and avoid the
compressed/"lossy" setting in your voice memo app.


Scenes are timed from the script at 170 words per minute, so each caption
appears when you'd be saying it. Read `script.md` at a brisk pace, drop the MP4
and your audio into CapCut / Premiere / TikTok's editor, and nudge clips if you
drift. If you naturally read slower or faster, set `"wpm"` in `storyboard.json`
(e.g. 155 or 185) and re-render so the video matches your pace.

## Layout

```
shorts/
  make_short.py              CLI
  aiq_shorts/theme.py        brand colours, fonts, layout constants (change the look here)
  aiq_shorts/scenes.py       scene types (photo/video hook, article card, charts, outro)
  aiq_shorts/engine.py       timing, captions, crossfades, parallel render → ffmpeg
  aiq_shorts/media.py        Wikimedia / Pexels search, Ken Burns, video frames
  aiq_shorts/substack.py     article fetch
  aiq_shorts/export.py       script.md, SRT, credits, post text
  assets/fonts/              IBM Plex Mono + Inter (SIL OFL)
  projects/<slug>/           one folder per video (storyboard.json, article, media, output)
  storyboard_reference.md    every scene type and option
```

## Network access

Fetching needs outbound access to `*.substack.com` and `substackcdn.com`
(article), `commons.wikimedia.org` and `upload.wikimedia.org` (photos), and
`pixabay.com` and `cdn.pixabay.com` (stock footage; key in `PIXABAY_API_KEY`).
Rendering itself works offline.
