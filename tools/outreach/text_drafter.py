#!/usr/bin/env python3
"""Draft personalized book-outreach texts and review/send them from a local page.

For everyone on the "People who might buy book" tab who has a phone number,
isn't marked "Reached out?" yet, and has past iMessages with you, this:
  1. reads your recent 1:1 texts with them (local Messages database),
  2. asks Claude for a 1-2 sentence personal opener in your texting voice,
  3. assembles  NAME!! <opener> <your book announcement>,
  4. serves a review page at http://localhost:8765 where you can edit each
     text and click Send (sends through the Messages app) or Skip.

Nothing is sent without a click. Drafts are saved to drafts.json, and each
send is logged to sent_log.csv (sheet row, name, time - no message text) so
the sheet's "Reached out?" column can be updated.

Needs check_messages.py in the same folder, Full Disk Access for Terminal,
`pip3 install anthropic`, and ANTHROPIC_API_KEY set. Without a key, drafts are
created with an empty opener for you to write.

Usage:
  python3 text_drafter.py --sheet-csv ~/Downloads/people.csv           # draft + review
  python3 text_drafter.py --sheet-csv ~/Downloads/people.csv --limit 10
  python3 text_drafter.py --review                                     # reopen saved drafts
"""
import argparse
import csv
import datetime as dt
import glob
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_messages as cm  # noqa: E402

MODEL = "claude-opus-5-5"
DEFAULT_BODY = (
    "I wanted you to be one of the first people I reached out to with the exciting news that my book, "
    "The Opportunity Map, is available for pre-order! I really think you're going to love it, and I would be "
    "incredibly grateful for the support in helping get it out in the world. The book is about closing the divide "
    "between inequality and prosperity in America, and it is for real the proudest I've been of anything I've ever "
    "worked on https://www.amazon.com/dp/1541705874"
)
BOOK_WORDS = ("opportunity map", "pre-order", "preorder", "my book")

SYSTEM = """You write the opening of a personal text message from Jeremy to someone he knows.
The full text will read: "<NAME>!! <your opening> <Jeremy's book announcement>". You write only the opening.

Write 1-2 sentences, in Jeremy's own texting voice (examples of his texts are below), that make the
message feel personal: reference something specific from their recent conversation (the last time they
hung out, something the person mentioned about their life, work, family or plans), or warmly wish them well.

Rules:
- Use only facts that appear in the conversation. Never invent events, names or plans.
- If the conversation is old, it's fine to say it's been a while.
- If there is nothing usable, write a short, warm, generic line.
- Do not mention the book, launch or pre-orders - the next part of the text does that.
- Do not start with a greeting or their name - that comes before your opening.
- Match his punctuation, capitalization and emoji habits from the examples.
- Output only the opening sentences, nothing else.

Examples of Jeremy's texts:
{style}"""


def first_name(name):
    n = name.split("(")[0].strip().split()
    return n[0] if n else name


def send_handle(key):
    """Turn a matched handle key (10 digits or email) into something Messages can send to."""
    if key and "@" in key:
        return key
    if key and key.isdigit():
        return "+1" + key if len(key) == 10 else "+" + key
    return None


def load_history(sheet_csv, since_days, imessage_db, contacts_dbs):
    tmp = tempfile.mkdtemp(prefix="drafter_")
    try:
        people = cm.load_sheet(sheet_csv)
        contacts = cm.load_contacts(contacts_dbs or glob.glob(cm.CONTACTS_GLOB, recursive=True), tmp)
        for p in people:
            p["keys"] |= contacts.get(cm.norm_name(p["name"]), set())
        events = cm.imessage_events(imessage_db, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    cutoff = dt.datetime.now() - dt.timedelta(days=since_days)
    events = [e for e in events if e["when"] and e["text"]]
    style = [e for e in events if e["from_me"] and len(e["text"]) > 40]
    style.sort(key=lambda e: e["when"], reverse=True)
    book = [e["text"] for e in style if any(w in e["text"].lower() for w in BOOK_WORDS)][:4]
    other = [e["text"] for e in style if e["when"] >= cutoff and e["text"] not in book][:16]
    by_key = {}
    for e in events:
        by_key.setdefault(e["key"], []).append(e)
    return people, by_key, book + other


def history_for(person, by_key):
    msgs, best_key, best_when = [], None, None
    for k in person["keys"]:
        for e in by_key.get(k, []):
            msgs.append(e)
            if best_when is None or e["when"] > best_when:
                best_key, best_when = k, e["when"]
    msgs.sort(key=lambda e: e["when"])
    return msgs, best_key


def transcript(msgs, n=40):
    lines = []
    for e in msgs[-n:]:
        who = "Jeremy" if e["from_me"] else "Them"
        lines.append(f"[{e['when']:%Y-%m-%d}] {who}: {e['text'][:500]}")
    return "\n".join(lines)


def make_client():
    try:
        import anthropic
    except ImportError:
        print("  (anthropic package not installed - run `pip3 install anthropic`; drafting without openers)")
        return None
    try:
        return anthropic.Anthropic()
    except Exception as e:  # missing credentials
        print(f"  (couldn't start the Claude client: {e}; drafting without openers)")
        return None


def write_opener(client, style, name, convo):
    import anthropic
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM.format(style="\n---\n".join(style) or "(none available)"),
            messages=[{"role": "user", "content":
                       f"Person: {name}\n\nRecent texts between Jeremy and {first_name(name)}:\n{convo}"}],
        )
    except anthropic.APIStatusError as e:
        return "", f"Claude API error {e.status_code}"
    except anthropic.APIConnectionError:
        return "", "Couldn't reach the Claude API"
    if resp.stop_reason == "refusal":
        return "", "Claude declined this one - write the opener yourself"
    text = " ".join(b.text for b in resp.content if b.type == "text").strip()
    return text, ""


def draft(a):
    print("Reading sheet, contacts and iMessage history...")
    people, by_key, style = load_history(a.sheet_csv, a.style_days, a.imessage_db, a.contacts_db)
    body = open(os.path.expanduser(a.body_file)).read().strip() if a.body_file else DEFAULT_BODY
    drafts = load_drafts(a.drafts)
    done = {d["sheet_row"] for d in drafts}
    todo = []
    for p in people:
        if p["H"].upper() == "TRUE" or p["row"] in done:
            continue
        msgs, key = history_for(p, by_key)
        if not msgs or not send_handle(key):
            continue
        todo.append((p, msgs, key))
    todo.sort(key=lambda t: t[1][-1]["when"], reverse=True)  # most recently texted first
    if a.limit:
        todo = todo[:a.limit]
    print(f"  {len(todo)} people to draft (have past texts, not yet reached out)")
    client = make_client()
    for i, (p, msgs, key) in enumerate(todo, 1):
        opener, note = ("", "No Claude client - write the opener yourself") if not client else \
            write_opener(client, style, p["name"], transcript(msgs))
        greeting = first_name(p["name"]).upper() + "!!"
        drafts.append(dict(
            sheet_row=p["row"], name=p["name"], to=send_handle(key), status="draft", note=note,
            text=" ".join(x for x in (greeting, opener, body) if x),
            context=[dict(when=f"{e['when']:%b %d, %Y}", me=e["from_me"], text=e["text"][:300]) for e in msgs[-8:]],
        ))
        save_drafts(a.drafts, drafts)
        print(f"  [{i}/{len(todo)}] {p['name']}" + (f"  ({note})" if note else ""))
    return drafts


def load_drafts(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def save_drafts(path, drafts):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(drafts, f, indent=1)
    os.replace(tmp, path)


SEND_SCRIPT = """on run argv
  set toHandle to item 1 of argv
  set msg to item 2 of argv
  set svcType to item 3 of argv
  tell application "Messages"
    if svcType is "SMS" then
      set svc to 1st account whose service type = SMS
    else
      set svc to 1st account whose service type = iMessage
    end if
    send msg to participant toHandle of svc
  end tell
end run"""


def send_imessage(to, text, dry_run):
    if dry_run:
        print(f"  [dry run] would send to {to}: {text[:60]}...")
        return None
    err = None
    for svc in ("iMessage", "SMS"):
        r = subprocess.run(["osascript", "-e", SEND_SCRIPT, to, text, svc], capture_output=True, text=True)
        if r.returncode == 0:
            return None
        err = r.stderr.strip()
    return err or "Messages couldn't send this text"


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Book outreach texts</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1f;--mute:#6e6e73;--line:#e3e1dc;--accent:#d9480f;--ok:#2b8a3e}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mute);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 0 14px}
.card.sent{opacity:.55}.card.skipped{opacity:.4}
.top{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.name{font-weight:600}.to{color:var(--mute);font-size:13px}
textarea{width:100%;box-sizing:border-box;min-height:150px;margin:10px 0;padding:10px;border:1px solid var(--line);
border-radius:8px;font:inherit;resize:vertical}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
button{border:0;border-radius:8px;padding:8px 14px;font:inherit;cursor:pointer;background:#ececec}
button.send{background:var(--accent);color:#fff}button:disabled{opacity:.5;cursor:default}
.status{font-size:13px;color:var(--mute)}.status.ok{color:var(--ok)}.note{font-size:13px;color:var(--accent)}
details{margin-top:8px;font-size:13px;color:var(--mute)}details p{margin:4px 0}
.me{color:var(--ink)}.filter{margin:0 0 16px}
</style></head><body><main>
<h1>Book outreach texts</h1>
<p class="sub">Edit any text, then click Send. Nothing goes out until you click. __COUNTS__</p>
<div class="filter"><label><input type="checkbox" id="hide" checked> Hide sent and skipped</label></div>
__CARDS__
</main><script>
function apply(){document.querySelectorAll('.card').forEach(c=>{
 c.style.display=(document.getElementById('hide').checked&&c.dataset.status!=='draft')?'none':''})}
document.getElementById('hide').onchange=apply;apply();
async function act(row,action){
 const card=document.getElementById('c'+row),st=card.querySelector('.status');
 const text=card.querySelector('textarea').value;
 if(action==='send'&&!confirm('Send this text to '+card.dataset.name+'?'))return;
 card.querySelectorAll('button').forEach(b=>b.disabled=true);st.textContent='Working...';
 const r=await fetch('/'+action,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({sheet_row:row,text:text})});const j=await r.json();
 if(j.ok){card.dataset.status=j.status;card.className='card '+j.status;st.className='status ok';
  st.textContent=j.status==='sent'?'Sent':(j.status==='skipped'?'Skipped':'Saved');
  if(j.status==='draft')card.querySelectorAll('button').forEach(b=>b.disabled=false);
  else setTimeout(apply,800)}
 else{st.className='status';st.textContent='Error: '+j.error;card.querySelectorAll('button').forEach(b=>b.disabled=false)}}
</script></body></html>"""


def render(drafts):
    cards = []
    for d in drafts:
        ctx = "".join(f'<p class="{"me" if m["me"] else ""}">{html.escape(m["when"])} - '
                      f'{"You" if m["me"] else "Them"}: {html.escape(m["text"])}</p>' for m in d["context"])
        disabled = "" if d["status"] == "draft" else " disabled"
        label = {"sent": "Sent", "skipped": "Skipped"}.get(d["status"], "")
        cards.append(f"""<div class="card {d['status']}" id="c{d['sheet_row']}" data-status="{d['status']}"
 data-name="{html.escape(d['name'])}"><div class="top"><span class="name">{html.escape(d['name'])}</span>
 <span class="to">{html.escape(d['to'])} · sheet row {d['sheet_row']}</span></div>
 {f'<div class="note">{html.escape(d["note"])}</div>' if d.get("note") else ''}
 <textarea{disabled}>{html.escape(d['text'])}</textarea>
 <div class="row"><button class="send" onclick="act({d['sheet_row']},'send')"{disabled}>Send</button>
 <button onclick="act({d['sheet_row']},'save')"{disabled}>Save edits</button>
 <button onclick="act({d['sheet_row']},'skip')"{disabled}>Skip</button>
 <span class="status">{label}</span></div>
 <details><summary>Recent texts with {html.escape(first_name(d['name']))}</summary>{ctx}</details></div>""")
    n = {s: sum(d["status"] == s for d in drafts) for s in ("draft", "sent", "skipped")}
    counts = f"{n['draft']} to review, {n['sent']} sent, {n['skipped']} skipped."
    return PAGE.replace("__COUNTS__", counts).replace("__CARDS__", "\n".join(cards) or "<p>No drafts.</p>")


def serve(a):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, body, ctype="application/json"):
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != "/":
                return self.reply(404, {"ok": False})
            self.reply(200, render(load_drafts(a.drafts)), "text/html")

        def do_POST(self):
            action = self.path.strip("/")
            if action not in ("send", "save", "skip"):
                return self.reply(404, {"ok": False, "error": "unknown action"})
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            with lock:
                drafts = load_drafts(a.drafts)
                d = next((x for x in drafts if x["sheet_row"] == req.get("sheet_row")), None)
                if not d:
                    return self.reply(404, {"ok": False, "error": "draft not found"})
                if d["status"] != "draft":
                    return self.reply(409, {"ok": False, "error": f"already {d['status']}"})
                d["text"] = (req.get("text") or d["text"]).strip()
                if action == "send":
                    err = send_imessage(d["to"], d["text"], a.dry_run)
                    if err:
                        save_drafts(a.drafts, drafts)
                        return self.reply(200, {"ok": False, "error": err})
                    d["status"], d["sent_at"] = "sent", dt.datetime.now().isoformat(timespec="seconds")
                    new = not os.path.exists(a.sent_log)
                    with open(a.sent_log, "a", newline="") as f:
                        w = csv.writer(f)
                        if new:
                            w.writerow(["sheet_row", "name", "sent_to", "sent_at", "dry_run"])
                        w.writerow([d["sheet_row"], d["name"], d["to"], d["sent_at"], a.dry_run])
                elif action == "skip":
                    d["status"] = "skipped"
                save_drafts(a.drafts, drafts)
                self.reply(200, {"ok": True, "status": d["status"]})

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)  # local only
    url = f"http://localhost:{a.port}"
    print(f"\nReview page: {url}   (Ctrl+C to stop)" + ("   [DRY RUN - nothing will be sent]" if a.dry_run else ""))
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Sends are logged in", os.path.abspath(a.sent_log))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet-csv", help="CSV download of the 'People who might buy book' tab")
    ap.add_argument("--review", action="store_true", help="skip drafting; reopen the review page for saved drafts")
    ap.add_argument("--limit", type=int, help="only draft this many people (most recently texted first)")
    ap.add_argument("--body-file", help="text file with your announcement, to replace the built-in one")
    ap.add_argument("--style-days", type=int, default=180, help="use your texts from this many days as voice examples")
    ap.add_argument("--imessage-db", default=cm.IMESSAGE_DB)
    ap.add_argument("--contacts-db", action="append", help="AddressBook db (default: all found)")
    ap.add_argument("--drafts", default="drafts.json")
    ap.add_argument("--sent-log", default="sent_log.csv")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--dry-run", action="store_true", help="the Send button logs instead of sending")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if not a.review:
        if not a.sheet_csv:
            ap.error("--sheet-csv is required unless you pass --review")
        draft(a)
    if not load_drafts(a.drafts):
        sys.exit("No drafts to review.")
    serve(a)


if __name__ == "__main__":
    main()
