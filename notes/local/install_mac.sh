#!/bin/bash
# One-time setup: posts Substack Notes from this Mac (your home connection, your login).
# Usage:  bash install_mac.sh
set -euo pipefail

DIR="$HOME/aiq-notes"
REPO="https://github.com/jeremybney/american_inequality.git"
LABEL="com.americaninequality.notes"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "1/5  Getting the code into $DIR"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull -q --ff-only
else
  git clone -q --depth 1 --filter=blob:none --sparse "$REPO" "$DIR"
  git -C "$DIR" sparse-checkout set notes
fi

echo "2/5  Installing Python packages"
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q --upgrade pip requests "urllib3<2"

echo "3/5  Saving your Substack cookie in the macOS Keychain"
echo "     Paste the value of the substack.sid cookie and press Return (it won't show):"
read -rs SID
echo
[ -n "$SID" ] || { echo "No cookie entered."; exit 1; }
security add-generic-password -U -a "$USER" -s aiq-substack-sid -w "$SID"
unset SID

echo "4/5  Checking the login and a test upload (nothing gets published)"
export SUBSTACK_SID="$(security find-generic-password -a "$USER" -s aiq-substack-sid -w)"
cd "$DIR/notes"
"$DIR/.venv/bin/python" post_due.py --verify 2>/dev/null || echo "     (profile lookup skipped; the upload test below is the real login check)"
"$DIR/.venv/bin/python" post_due.py --test-upload || { echo; echo "Upload test failed, so the login isn't working. Nothing was installed. Send Claude the error above."; exit 1; }
unset SUBSTACK_SID

echo "5/5  Setting up the background job (runs every 10 minutes while the Mac is awake)"
mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$DIR/notes/local/run.sh</string></array>
  <key>StartInterval</key><integer>600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DIR/logs/poster.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/poster.log</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo
echo "Done. Whenever this Mac is awake it queues the next 48 hours of notes in Substack,"
echo "and Substack publishes them on time even if the Mac is asleep or closed."
echo "Log:        $DIR/logs/poster.log"
echo "Stop:       launchctl unload $PLIST"
echo "New cookie: bash $DIR/notes/local/install_mac.sh   (just run it again)"
