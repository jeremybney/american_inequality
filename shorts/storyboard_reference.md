# storyboard.json reference

A storyboard lives at `projects/<slug>/storyboard.json`. It is a list of scenes.
Every scene has a `type` and a `say` list — the lines the narrator reads. Each
`say` line becomes one on-screen caption and one line of `script.md`, and the
scene lasts as long as it takes to say its lines at `wpm`.

```jsonc
{
  "title": "…",                 // used in script.md
  "wpm": 170,                   // narration pace used for timing (150 = relaxed, 185 = fast)
  "draft": false,               // true stamps "DRAFT · VERIFY NUMBERS" on every frame
  "today": "2026-09-30",        // optional; drives the "6 MONTHS AGO" badge (defaults to today)
  "article": {"section": "The Dividing Line"},   // overrides/extra fields for article.json
  "post": {"caption": "…", "hashtags": ["inequality", "…"]},
  "notes": ["anything the editor should know"],
  "music_credit": "Music: … (CC BY 4.0)",       // optional, goes in credits.md
  "scenes": [ … ]
}
```

## Fields every scene accepts

| field | meaning |
|---|---|
| `say` | list of caption/narration lines (keep each ≤ ~12 words) |
| `source` | small print under the caption: the data source for that beat |
| `duration` | force a length in seconds (otherwise derived from `say`) |
| `hold` | extra seconds after the last line (default 0.35) |
| `crossfade` | seconds of crossfade into this scene (default 0.3; 0 = hard cut) |

Chart scenes (everything on the orange background) also take `title`,
`subtitle`, `note` (small navy text under the chart), and
`background: "navy"` for an occasional dark beat.

Timing keys like `at` are seconds from the start of the scene; a negative value
counts back from the end.

Colours: `navy`, `white`, `yellow`, `gold`, `green`, `lightblue`, `darkblue`,
`orange`, `ink`, or any `#rrggbb`. On the orange background use **navy / white**
as the main pair, **lightblue** as a third series, and **yellow** for a single
emphasised value. Gold is too close to the orange to carry data on its own.

Number formatting (bars, stats, segments, counters): `prefix`, `suffix`,
`decimals`, `scale` (multiply before display), `commas` (default true),
`display` (literal text shown once a count finishes, e.g. `"$84T"`).

---

## `hook` / `photo` / `video`
A full-bleed real photo with a slow Ken Burns move, or a video clip.

```json
{"type": "hook", "media": "hook.jpg",
 "headline": {"text": "Boomers own half of America's wealth.", "highlight": "Millennials own the debt."},
 "chip": "Generational wealth · American Inequality",
 "zoom": [1.0, 1.12], "pan": [[0.5, 0.5], [0.5, 0.45]], "focus": [0.5, 0.4], "dim": 0.3,
 "overlays": [ … ],
 "say": ["…"]}
```
- `media`: a file in `media/`: `.jpg/.png/.webp` or `.mp4/.mov/.webm`. Video clips play from `start` seconds.
- `focus`: where to centre the 9:16 crop, `[x, y]` from 0 to 1.
- `zoom` `[from, to]`: 1.0 is the full frame, >1 pushes in. `pan`: centre point from → to.
- `dim`: darken 0 to 1 (default 0.3). `scrim: false` removes the bottom gradient.
- `headline.text` may mark the highlight inline with braces: `"Boomers own {half} of the wealth"`. It can also take `size`, `y` (0 to 1, default 0.34), `cps` (typing speed), `at`.
- `chip`: `"Topic · American Inequality"`. The text after the last `·` is set in navy.

Overlays (`kind`):
| kind | fields | looks like |
|---|---|---|
| `stamp` | `text`, `x`, `y`, `angle`, `color`, `size`, `at` | outlined label, e.g. "FREIGHT ONLY" |
| `stat` | `value`, `prefix`, `suffix`, `decimals`, `label`, `y`, `color`, `at`, `count` | giant count-up over the photo ("$44M") |
| `tag` | `text`, `x`, `y`, `background`, `color` | orange pill label ("the 4% that's metered:") |
| `callout` | `text`, `sub`, `x`, `y`, `point: [x, y]`, `color` | value box with a leader line ("$0.00") |
| `line_draw` | `points: [[x, y], …]`, `draw`, `width`, `color` | a line tracing itself across the photo (drawn under the headline) |

## `article_card`
The article's header card, built from `article.json` (title, subtitle, authors,
date, and `media/cover.jpg` if present), sliding in with an "N MONTHS AGO" badge.
```json
{"type": "article_card", "chips": ["WHY IT MATTERS", "WHAT CHANGED"], "badge": "auto",
 "show_cover": true, "say": ["In March I wrote about…"]}
```
`badge`: `"auto"` (computed from the post date), any text, or `null`. `chips_at` sets when the chips start.

## `hbars`: horizontal bars that grow and count up
```json
{"type": "hbars", "title": "Household wealth by generation", "prefix": "$", "suffix": "T",
 "bars": [{"label": "Boomers", "value": 85, "color": "navy"},
          {"label": "Millennials", "value": 17, "color": "white", "at": 2.5}],
 "max": 100, "stagger": 0.9}
```

## `vbars`: side-by-side comparison columns
```json
{"type": "vbars", "title": "What $5.5B buys",
 "bars": [{"label": "Boomers", "sublabel": "in 1990", "value": 21, "suffix": "%", "color": "navy"},
          {"label": "Millennials", "sublabel": "in 2025", "value": 10, "suffix": "%", "color": "white"}],
 "annotation": {"text": "2x", "bar": 0, "at": 3.0, "color": "yellow"}}
```

## `big_number`: one to three giant count-up numbers
```json
{"type": "big_number", "kicker": "the great wealth transfer",
 "stats": [{"value": 84, "prefix": "$", "suffix": "T", "label": "passing down by 2045", "color": "white"}]}
```
Per stat: `at`, `count` (seconds to count), `from`, `size`, `label_color`.

## `waffle`: 100 squares filled by group
```json
{"type": "waffle", "title": "Every $100 of U.S. wealth",
 "groups": [{"label": "Boomers", "count": 51, "color": "navy"}, {"label": "Millennials", "count": 10, "color": "yellow"}],
 "fill_at": 0.6, "fill": 2.4,
 "big": {"value": 10, "prefix": "$", "label": "for Millennials", "color": "yellow", "at": 3.4}}
```

## `stacked`: 100% bars (share of X vs share of Y)
```json
{"type": "stacked", "title": "Boomers' share of America",
 "rows": [{"label": "Share of population", "segments": [{"label": "Boomers", "value": 21, "suffix": "%", "color": "navy"},
                                                        {"label": "Everyone else", "value": 79, "suffix": "%", "color": "white"}]},
          {"label": "Share of wealth", "at": 2.4, "segments": [ … ]}]}
```

## `line`: a line/area chart that draws itself, with an optional live counter
```json
{"type": "line", "title": "…",
 "series": [{"label": "Boomers", "color": "navy", "area": true, "suffix": "%",
             "points": [[1990, 21], [2000, 38], [2010, 50], [2025, 51]]},
            {"label": "Millennials", "color": "white", "suffix": "%", "points": [[2010, 2], [2025, 10]]}],
 "x_ticks": [1990, 2000, 2010, 2025], "y_range": [0, 60],
 "counter": {"series": 0, "suffix": "%", "label": "Boomers' share of wealth"},
 "draw": 2.6}
```

## `then_now`: old value struck through, new value pops in
```json
{"type": "then_now", "title": "Since 1990", "headers": ["1990", "2025"],
 "rows": [{"label": "Median home price", "old": "$79K", "new": "$420K", "color": "white"}]}
```

## `checklist`
```json
{"type": "checklist", "title": "Why it's harder", "items": ["Housing costs", "Student debt"], "stagger": 0.9}
```

## `statement`: a big typed line with a navy marker highlight on {braced} words
```json
{"type": "statement", "kicker": "What comes next", "text": "Wealth isn't just earned. {It's inherited.}"}
```

## `outro`
```json
{"type": "outro", "cta": "Full story + data at the link in bio", "say": ["…"]}
```
Optional: `wordmark` (list of lines), `url`, `byline`.
