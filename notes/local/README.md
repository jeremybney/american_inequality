# Posting from your Mac

Substack's Cloudflare bot check blocks posts coming from cloud servers like GitHub Actions.
From your own Mac, Substack sees your home connection and your own login, same as your browser.

## Install (once, about 2 minutes)

1. Copy your `substack.sid` cookie value (same steps as before: substack.com → DevTools →
   Application → Cookies → https://substack.com → `substack.sid` → copy Value).
2. Open **Terminal** (Cmd + Space, type Terminal, Return) and paste:

   ```
   curl -fsSL https://raw.githubusercontent.com/jeremybney/american_inequality/main/notes/local/install_mac.sh -o /tmp/aiq_install.sh && bash /tmp/aiq_install.sh
   ```

3. Paste the cookie when asked (it stays hidden) and press Return.

The installer does a test image upload that publishes nothing (that's the login check). If either fails it
stops, installs nothing, and prints an error to send to Claude.

The cookie is stored in your macOS Keychain, not in a file or in GitHub.

## What happens when

- Edit or Hold notes in the Google Sheet until they're queued (about 48 hours before post time).
  After that, change or delete them in Substack's scheduled notes list.
- If the Mac was off for days and a note's time is under 15 minutes away (or up to 3 hours past),
  it posts immediately; older missed notes are skipped, never dumped at once.

## Everyday

- Edit the Google Sheet as before. The Mac reads it right before each post.
- Log: `~/aiq-notes/logs/poster.log`
- Pause: `launchctl unload ~/Library/LaunchAgents/com.americaninequality.notes.plist`
- Resume: same command with `load`
- Cookie expired (log shows 401/403 or "Could not confirm login"): run the install command again.
