#!/bin/bash
# Called by launchd every 10 minutes while the Mac is awake. Pulls calendar changes and queues
# the next 48 hours of notes in Substack's own scheduler, so they publish even if the Mac is asleep.
DIR="$HOME/aiq-notes"
export GIT_TERMINAL_PROMPT=0   # never hang waiting for a password in the background
cd "$DIR" || exit 1
echo "--- $(date '+%Y-%m-%d %H:%M:%S')"
git pull -q --rebase --autostash 2>&1 | tail -2
export SUBSTACK_SID="$(security find-generic-password -a "$USER" -s aiq-substack-sid -w 2>/dev/null)"
cd notes && "$DIR/.venv/bin/python" post_due.py --ahead 48
cd "$DIR"
if ! git diff --quiet -- notes/state 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard notes/state)" ]; then
  git add notes/state && git commit -q -m "notes: update posted state" && (git push -q 2>&1 | tail -1 || true)
fi
