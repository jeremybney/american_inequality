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

The installer checks your login and does a test upload that publishes nothing. If either fails it
stops, installs nothing, and prints an error to send to Claude.

The cookie is stored in your macOS Keychain, not in a file or in GitHub.

## Keep the Mac awake at post times

Posts go out while the Mac is awake. A note whose time passed while it was asleep still posts if the
Mac wakes within 3 hours; after that it's skipped (never dumped all at once).

- Desktop / laptop on power: System Settings → Battery (or Energy) → Options →
  turn on "Prevent automatic sleeping on power adapter when the display is off".
- Laptop lid closed = asleep. Leave it open or plugged into a display.

## Everyday

- Edit the Google Sheet as before. The Mac reads it right before each post.
- Log: `~/aiq-notes/logs/poster.log`
- Pause: `launchctl unload ~/Library/LaunchAgents/com.americaninequality.notes.plist`
- Resume: same command with `load`
- Cookie expired (log shows 401/403 or "Could not confirm login"): run the install command again.
