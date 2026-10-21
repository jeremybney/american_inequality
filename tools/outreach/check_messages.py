#!/usr/bin/env python3
"""Check iMessage and WhatsApp on this Mac for book-outreach replies.

Reads a CSV download of the "People who might buy book" tab, finds each
person's phone numbers / emails (from the sheet, plus Mac Contacts by name),
then looks through local iMessage and WhatsApp history for 1:1 conversations
with them since --since.

Writes a results CSV (no message text) with, per sheet row:
  reached_out  - you sent them a message since --since
  responded    - they sent you a message after your first one

Everything stays on this Mac; only the results CSV is written.

Usage:
  python3 check_messages.py --sheet-csv ~/Downloads/people.csv
"""
import argparse
import csv
import datetime as dt
import glob
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata

HOME = os.path.expanduser("~")
IMESSAGE_DB = os.path.join(HOME, "Library/Messages/chat.db")
WHATSAPP_DB = os.path.join(
    HOME, "Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite")
CONTACTS_GLOB = os.path.join(HOME, "Library/Application Support/AddressBook/**/AddressBook-v22.abcddb")
APPLE_EPOCH = 978307200  # 2001-01-01 in Unix time

PHONE_COLS = ["Phone", "Phone-join (Goog + Apple)", "Phone with formulas (Google)",
              "Phone with formulas (Apple)", "Formatted"]
EMAIL_COLS = ["Email", "Email 2", "Email with Formulas"]


def norm_name(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    return " ".join(re.sub(r"[^a-z ]", " ", s).split())


def phone_key(s):
    d = re.sub(r"\D", "", s or "")
    if len(d) < 7:
        return None
    return d[-10:]  # last 10 digits: ignores country code / leading 1


def handle_key(h):
    h = (h or "").strip().lower()
    if "@" in h and not h.endswith("whatsapp.net") and not h.endswith("@lid"):
        return h
    return phone_key(h.split("@")[0])


def open_copy(path, tmp):
    """Open a copy of a SQLite db (plus WAL files) so the live app isn't disturbed."""
    if not os.path.exists(path):
        return None
    dst = os.path.join(tmp, os.path.basename(path))
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            shutil.copy2(path + suffix, dst + suffix)
    return sqlite3.connect(dst)


def apple_time(v):
    if not v:
        return None
    v = float(v)
    if v > 1e11:  # iMessage stores nanoseconds on modern macOS
        v /= 1e9
    return dt.datetime.fromtimestamp(v + APPLE_EPOCH)


def attributed_text(blob):
    """Pull the plain string out of an iMessage attributedBody blob."""
    if not blob:
        return ""
    i = blob.find(b"NSString")
    if i < 0:
        return ""
    s = blob[i + 8:]
    p = s.find(b"+")
    if p < 0:
        return ""
    s = s[p + 1:]
    if not s:
        return ""
    n, start = s[0], 1
    if n == 0x81:
        n, start = int.from_bytes(s[1:3], "little"), 3
    elif n == 0x82:
        n, start = int.from_bytes(s[1:4], "little"), 4
    return s[start:start + n].decode("utf-8", "ignore")


def load_sheet(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        records = list(csv.reader(f))
    hdr_i = next((i for i, r in enumerate(records) if r and r[0].strip() == "Name"), None)
    if hdr_i is None:
        sys.exit("Couldn't find the header row (first cell 'Name') in the CSV.")
    hdr = [h.strip() for h in records[hdr_i]]
    col = {h: i for i, h in enumerate(hdr) if h}
    people = []
    for i, r in enumerate(records[hdr_i + 1:], start=hdr_i + 2):  # sheet rows are 1-based
        get = lambda h: r[col[h]].strip() if h in col and col[h] < len(r) else ""
        name = get("Name")
        if not name:
            continue
        keys = {phone_key(get(c)) for c in PHONE_COLS} | {get(c).lower() for c in EMAIL_COLS if "@" in get(c)}
        people.append(dict(row=i, name=name, keys={k for k in keys if k}, matched=set(),
                           H=get("Reached out?"), I=get("Responded?")))
    return people


def load_contacts(paths, tmp):
    """Mac Contacts: normalized full name -> set of phone/email keys."""
    by_name = {}
    for n, path in enumerate(paths):
        sub = os.path.join(tmp, f"ab{n}")
        os.makedirs(sub, exist_ok=True)
        con = open_copy(path, sub)
        if not con:
            continue
        try:
            q = """SELECT r.Z_PK, r.ZFIRSTNAME, r.ZLASTNAME, p.ZFULLNUMBER, e.ZADDRESS
                   FROM ZABCDRECORD r
                   LEFT JOIN ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK
                   LEFT JOIN ZABCDEMAILADDRESS e ON e.ZOWNER = r.Z_PK"""
            for _, first, last, phone, email in con.execute(q):
                name = norm_name(f"{first or ''} {last or ''}")
                if not name:
                    continue
                keys = by_name.setdefault(name, set())
                if phone_key(phone):
                    keys.add(phone_key(phone))
                if email:
                    keys.add(email.strip().lower())
        except sqlite3.Error as e:
            print(f"  (skipped contacts db {path}: {e})")
        con.close()
    return by_name


def imessage_events(path, tmp):
    con = open_copy(path, tmp)
    if not con:
        print("  iMessage database not found (or no Full Disk Access) - skipping.")
        return []
    q = """SELECT h.id, m.is_from_me, m.date, m.text, m.attributedBody
           FROM message m
           JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
           JOIN chat c ON c.ROWID = cmj.chat_id
           JOIN chat_handle_join chj ON chj.chat_id = c.ROWID
           JOIN handle h ON h.ROWID = chj.handle_id
           WHERE c.style = 45"""  # 45 = one-to-one chat (43 = group)
    out = []
    for hid, from_me, date, text, body in con.execute(q):
        out.append(dict(channel="iMessage", key=handle_key(hid), name=None, from_me=bool(from_me),
                        when=apple_time(date), text=text or attributed_text(body)))
    con.close()
    return out


def whatsapp_events(path, tmp):
    con = open_copy(path, tmp)
    if not con:
        print("  WhatsApp database not found - skipping (is the WhatsApp Mac app installed?).")
        return []
    q = """SELECT s.ZCONTACTJID, s.ZPARTNERNAME, m.ZISFROMME, m.ZMESSAGEDATE, m.ZTEXT
           FROM ZWAMESSAGE m JOIN ZWACHATSESSION s ON m.ZCHATSESSION = s.Z_PK
           WHERE s.ZSESSIONTYPE = 0"""  # 0 = one-to-one chat
    out = []
    for jid, partner, from_me, date, text in con.execute(q):
        out.append(dict(channel="WhatsApp", key=handle_key(jid), name=norm_name(partner),
                        from_me=bool(from_me), when=apple_time(date), text=text or ""))
    con.close()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet-csv", required=True, help="CSV download of the 'People who might buy book' tab")
    ap.add_argument("--since", default="2026-10-01", help="only count messages on/after this date (YYYY-MM-DD)")
    ap.add_argument("--keywords", default="book,opportunity map,pre-order,preorder",
                    help="comma-separated words that mark a sent message as book outreach")
    ap.add_argument("--out", default="message_check_results.csv")
    ap.add_argument("--imessage-db", default=IMESSAGE_DB)
    ap.add_argument("--whatsapp-db", default=WHATSAPP_DB)
    ap.add_argument("--contacts-db", action="append", help="AddressBook db (default: all found)")
    ap.add_argument("--no-imessage", action="store_true")
    ap.add_argument("--no-whatsapp", action="store_true")
    a = ap.parse_args()

    since = dt.datetime.strptime(a.since, "%Y-%m-%d")
    keywords = [k.strip().lower() for k in a.keywords.split(",") if k.strip()]
    tmp = tempfile.mkdtemp(prefix="msgcheck_")
    try:
        print("Reading sheet...")
        people = load_sheet(a.sheet_csv)
        print(f"  {len(people)} people")

        print("Reading Mac Contacts...")
        contacts = load_contacts(a.contacts_db or glob.glob(CONTACTS_GLOB, recursive=True), tmp)
        added = 0
        for p in people:
            extra = contacts.get(norm_name(p["name"]), set()) - p["keys"]
            p["keys"] |= extra
            added += bool(extra)
        print(f"  {len(contacts)} contacts; added numbers/emails for {added} sheet people")

        events = []
        if not a.no_imessage:
            print("Reading iMessage...")
            events += imessage_events(a.imessage_db, tmp)
        if not a.no_whatsapp:
            print("Reading WhatsApp...")
            events += whatsapp_events(a.whatsapp_db, tmp)
        events = [e for e in events if e["when"] and e["when"] >= since]
        print(f"  {len(events)} one-to-one messages since {a.since}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    by_key, by_name = {}, {}
    for p in people:
        for k in p["keys"]:
            by_key.setdefault(k, []).append(p)
        by_name.setdefault(norm_name(p["name"]), []).append(p)

    stats = {}
    for e in events:
        targets = by_key.get(e["key"]) or []
        how = "number/email"
        if not targets and e["name"]:  # WhatsApp chat with no usable number: match on chat name
            targets, how = by_name.get(e["name"], []), "WhatsApp chat name"
        for p in targets:
            s = stats.setdefault(p["row"], dict(sent=0, recv=0, first_sent=None, last_recv=None,
                                                replied=False, book=False, channels=set(), how=set()))
            s["channels"].add(e["channel"])
            s["how"].add(how)
            if e["from_me"]:
                s["sent"] += 1
                s["first_sent"] = min(filter(None, [s["first_sent"], e["when"]]))
                if any(k in (e["text"] or "").lower() for k in keywords):
                    s["book"] = True
            else:
                s["recv"] += 1
                s["last_recv"] = max(filter(None, [s["last_recv"], e["when"]]))
    for p in people:  # replied = a received message after your first sent one
        s = stats.get(p["row"])
        if s and s["first_sent"]:
            s["replied"] = any(e["when"] > s["first_sent"] and not e["from_me"] and
                               (e["key"] in p["keys"] or (e["name"] and e["name"] == norm_name(p["name"])))
                               for e in events)

    fmt = lambda d: d.strftime("%Y-%m-%d") if d else ""
    rows = []
    for p in people:
        s = stats.get(p["row"])
        if not s:
            continue
        rows.append({
            "sheet_row": p["row"], "name": p["name"],
            "channels": "+".join(sorted(s["channels"])), "matched_on": "+".join(sorted(s["how"])),
            "msgs_sent": s["sent"], "msgs_received": s["recv"],
            "first_sent": fmt(s["first_sent"]), "last_received": fmt(s["last_recv"]),
            "sent_msg_mentions_book": "yes" if s["book"] else "no",
            "reached_out": "TRUE" if s["sent"] else "FALSE",
            "responded": "TRUE" if s["replied"] else "FALSE",
            "sheet_reached_out_now": p["H"], "sheet_responded_now": p["I"],
        })
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["sheet_row"])
        w.writeheader()
        w.writerows(rows)

    new_h = sum(r["reached_out"] == "TRUE" and r["sheet_reached_out_now"] != "TRUE" for r in rows)
    new_i = sum(r["responded"] == "TRUE" and r["sheet_responded_now"] != "TRUE" for r in rows)
    print(f"\nFound message history with {len(rows)} people on the sheet.")
    print(f"  Would newly mark Reached out: {new_h}   Responded: {new_i}")
    print(f"Results written to {os.path.abspath(a.out)} (no message text included).")


if __name__ == "__main__":
    main()
