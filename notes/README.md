# American Inequality: Substack Notes autoposter

Three Notes a day, each with a chart, map or big stat in the American Inequality style,
written to match Jeremy's voice, scheduled at the times his notes actually do best.

```
batches/      one script per batch: pulls data, draws charts, writes the calendar
charts/       rendered PNGs (1700px, Big 5 house style)
existing/     Jeremy's best-performing published charts (reused sparingly; see VOICE.md)
calendar/     the planned notes (JSON); mirrored into the Google Sheet for review
aiq_notes/    charts.py (house style) · fred.py · acs.py · schedule.py · substack.py
post_due.py   queues the next 48h of notes in Substack's native scheduler (runs on Jeremy's Mac; see local/README.md)
local/        Mac installer + runner (Substack's Cloudflare check blocks cloud servers)
learn.py      weekly: re-reads engagement, retunes posting windows, writes data/performance.md
VOICE.md      voice rules + what the engagement data says works
config.json   sheet id, Substack ids, "paused" kill switch
state/        what has been posted (written by the workflow)
```

## How review works

The Google Sheet is the calendar. Edit any of these and the poster uses your version:

| Column | What you can do |
|---|---|
| Post at (ET) | Move a note. Format `2026-11-16 07:04`. |
| Status | `Scheduled` posts on time (edits count until it's queued in Substack, ~48h ahead). `Approved` is the same, just a marker that you've looked. `Hold` or `Skip` never posts. |
| Note text | Rewrite freely. Blank line = new paragraph, single line break = line break. |
| Chart file | Swap the image: another path in this repo, or any public image URL. |

If you don't touch a row, it posts as written.

Kill switch: set `"paused": true` in `config.json` (or set Status to Hold on everything).

## One-time setup

**Posting runs on your Mac, not GitHub.** Follow `local/README.md` (one Terminal command).
GitHub Actions still re-learns posting windows weekly and runs manual dry-runs.

(Original GitHub-based steps, kept for reference:)

1. **Substack cookie.** Log in to substack.com in a browser → DevTools → Application → Cookies →
   `https://substack.com` → copy the value of `substack.sid`.
   In GitHub: repo Settings → Secrets and variables → Actions → New repository secret, name `SUBSTACK_SID`.
   The cookie expires every few months; when posting starts failing with 401/403, repeat this step.
2. **Sheet access.** The poster reads the Google Sheet without logging in, so the sheet must be shared as
   *Anyone with the link: Viewer*. (Only people with the link can see drafts.)
3. **Merge to the default branch.** GitHub only runs scheduled workflows from the default branch.
4. **Test.** Actions → Substack Notes → Run workflow → `verify` (checks login), then `dry-run`
   (shows what's due). `post-now` with a note ID posts one note immediately.

## Weekly refresh

Each week a scheduled Claude session writes the next batch: new data releases (BLS, Census, HUD, Fed,
FRED), news hooks, Jeremy's past charts, new charts in the house style, notes per VOICE.md. It adds the
rows to the Sheet as `Scheduled` at least five days ahead, so there's always time to review.

## Notes on the Substack API

Substack has no official Notes API; `aiq_notes/substack.py` uses the same endpoints the web app calls,
with your session cookie. It can break if Substack changes those endpoints. When a post fails, the
note is marked `Error` in `state/posted.json` and never retried automatically, so a failure can't cause
a double post. Automated posting through private endpoints is a gray area under Substack's terms;
the low volume (3/day) and human-like timing keep it close to normal use.
