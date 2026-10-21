# Book outreach: iMessage / WhatsApp check

`check_messages.py` runs on your Mac and checks who you've texted about the book and who wrote back. It reads your local iMessage and WhatsApp history and Mac Contacts; nothing is uploaded, and the output contains no message text.

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

3. Send the resulting `message_check_results.csv` to Claude, which will update columns H and I.

## Options

- `--since 2026-10-01` — only count messages on or after this date (default 2026-10-01).
- `--keywords "book,opportunity map"` — words that flag a sent message as book outreach (the `sent_msg_mentions_book` column).
- `--no-whatsapp` / `--no-imessage` — skip a source.

## How it decides

- **reached_out**: you sent at least one message in a one-to-one chat with them since `--since`.
- **responded**: they sent a message after your first one.
- People are matched by the phone numbers and emails in the sheet, plus numbers from Mac Contacts with the same name. For WhatsApp chats without a phone number, the chat name is used.
- Group chats are ignored.
