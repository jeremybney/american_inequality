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
