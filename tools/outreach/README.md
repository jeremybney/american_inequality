# Book outreach: iMessage / WhatsApp / Instagram check

`check_messages.py` runs on your Mac and checks who you've messaged about the book and who wrote back. It reads your local iMessage and WhatsApp history, Mac Contacts, and (optionally) an Instagram data export; nothing is uploaded, and the output contains no message text.

## One-time setup

1. **Full Disk Access for Terminal** (needed to read Messages): System Settings → Privacy & Security → Full Disk Access → turn on **Terminal** (add it with `+` from Applications → Utilities if it's not listed). Quit and reopen Terminal.
2. WhatsApp is read from the **WhatsApp Mac app**, so the app must be installed and synced. WhatsApp Web history can't be read.

## Each run

1. In the Google Sheet, open the **People who might buy book** tab → File → Download → Comma-separated values (.csv). It lands in `~/Downloads`.
2. In Terminal:

   ```
   cd ~/Downloads
   curl -sO https://raw.githubusercontent.com/jeremybney/american_inequality/claude/friendly-einstein-kbqksx/tools/outreach/check_messages.py
   python3 check_messages.py --sheet-csv "The Opportunity Map Outreach and Topics - People who might buy book.csv"
   ```

   To include Instagram DMs, add `--instagram-export ~/Downloads/<instagram zip name>.zip` (see below).

3. Send the resulting `message_check_results.csv` to Claude, which will update columns H and I.

## Instagram DMs

Instagram doesn't store messages on your Mac, so download them from Instagram first:

1. In the Instagram app: Settings → Accounts Center → Your information and permissions → Download your information → Download or transfer information.
2. Pick your account → **Some of your information** → tick **Messages** only → **Download to device**.
3. Date range: **Last month** (or since the campaign started). Format: **JSON** (not HTML). Tap **Create files**.
4. Instagram emails you when it's ready (minutes to a few hours). Download the .zip to `~/Downloads` and pass it with `--instagram-export`. No need to unzip.

Instagram DMs are matched on display name only, since there are no phone numbers, so a person whose Instagram name differs from their name in the sheet won't be found. Group chats are skipped.

## Options

- `--since 2026-10-01` — only count messages on or after this date (default 2026-10-01).
- `--keywords "book,opportunity map"` — words that flag a sent message as book outreach (the `sent_msg_mentions_book` column).
- `--no-whatsapp` / `--no-imessage` — skip a source.
- `--instagram-export PATH` — Instagram export .zip or unzipped folder; `--instagram-name "Your Name"` if your own name isn't detected correctly.

## How it decides

- **reached_out**: you sent at least one message in a one-to-one chat with them since `--since`.
- **responded**: they sent a message after your first one.
- People are matched by the phone numbers and emails in the sheet, plus numbers from Mac Contacts with the same name. For WhatsApp chats without a phone number, and for all Instagram DMs, the chat name is used.
- Group chats are ignored.

# Drafting and sending personalized outreach texts

`text_drafter.py` drafts a personal text for everyone on the tab who has a phone number, isn't marked "Reached out?" yet, and has texted with you before. Then it opens a review page where you edit and send each one.

Each draft reads: `NAME!! <a 1–2 sentence opener Claude writes from your recent texts with them> <your book announcement>`. Claude only writes the opener, in your own texting voice (it reads your recent sent texts, including earlier book texts, as examples), using only things that actually came up in your conversation with that person.

## One-time setup

1. Full Disk Access for Terminal (same as above).
2. `pip3 install anthropic`
3. A Claude API key from https://console.anthropic.com → API Keys. Then in Terminal: `export ANTHROPIC_API_KEY=sk-ant-...` (add that line to `~/.zshrc` to keep it). Without a key the drafts are still made, with the opener left for you to write.

## Each run

```
cd ~/Downloads
curl -sO https://raw.githubusercontent.com/jeremybney/american_inequality/claude/friendly-einstein-kbqksx/tools/outreach/check_messages.py
curl -sO https://raw.githubusercontent.com/jeremybney/american_inequality/claude/friendly-einstein-kbqksx/tools/outreach/text_drafter.py
python3 text_drafter.py --sheet-csv "The Opportunity Map Outreach and Topics - People who might buy book.csv" --limit 20
```

This drafts 20 people (the ones you texted most recently first), then opens http://localhost:8765. For each card:

- **Edit** the text in the box. Open "Recent texts" to see what the opener was based on.
- **Send** sends it through the Messages app (iMessage, falling back to SMS). It asks you to confirm first. The first time, macOS asks whether Terminal may control Messages; click OK.
- **Skip** hides the card without sending.

Nothing is sent until you click Send. Press Ctrl+C in Terminal when you're done. To come back later without re-drafting: `python3 text_drafter.py --review`. Running the drafting command again only drafts people who don't have a draft yet.

Each send is logged to `sent_log.csv` (sheet row, name, number, time; no message text). Send that file to Claude to mark those people as "Reached out?" in the sheet.

Options: `--dry-run` (the Send button only logs, so you can try it out safely), `--body-file announcement.txt` (use your own announcement text instead of the built-in one), `--limit N`.

Privacy: to write the openers, your recent texts with each person (up to the last 40 messages) and a sample of your own sent texts go to Claude through your API key. Drafts are stored on your Mac in `drafts.json`.
