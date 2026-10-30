# Substack unsubscribe tracker

A Google Apps Script that replaces the two Zapier zaps. It reads Substack's
unsubscribe emails in Gmail and adds each person to the
[Unsubscribed Emails from Newsletter](https://docs.google.com/spreadsheets/d/1C2mtCYPkjowMRqoqcK6i5i7Oj-QYEbDXtw8bPrfuU7k/edit)
sheet:

| Email from `no-reply@substack.com` | Tab |
| --- | --- |
| **Unsubscription for American Inequality** with `Prior status: Paid Subscriber` | `Paid` |
| **Email disabled for American Inequality** (free subscribers) | `Sheet1` |

Each row is written as `Email | Email from American Inequality | Gmail link | Date (UTC)`,
the same format the zaps used.

**Timing:** the script runs every minute, which is the fastest schedule Apps
Script allows. It also searches Trash, so an email you deleted right away still
gets picked up (Gmail keeps Trash for 30 days). The only email it can miss is
one you permanently delete within about a minute of it arriving.

It runs in your own Google account, so there is nothing to pay for or host.

## Setup (about 5 minutes)

1. Turn off both Zaps in Zapier.
2. Go to <https://script.google.com>, click **New project**, and name it "Unsubscribe tracker".
3. Replace the contents of `Code.gs` with [`Code.gs`](Code.gs) from this folder.
4. Optional: under **Project Settings**, check *Show "appsscript.json" manifest file*,
   then paste in [`appsscript.json`](appsscript.json). This keeps the
   permissions to read-only Gmail.
5. Choose `setup` in the function dropdown and click **Run**. Approve the
   permissions prompt. On the "Google hasn't verified this app" screen, click
   **Advanced → Go to Unsubscribe tracker**. This is your own script.
6. Done. Under **Triggers** (the clock icon) you should see `checkUnsubscribes`
   set to run every minute.

`setup()` starts tracking from the moment you run it. To pick up emails from
before that, run `backfillSince('2026-10-29T16:00:00Z')` with a UTC time. It
re-reads every unsubscribe email since then, so choose a time after the last
row already in the sheet to avoid duplicates.

If rows stop showing up, run `diagnose()` and check the log. It lists recent
unsubscribe emails and what the script reads from each one.

## Maintenance

- **Errors:** Google emails you if a run fails. Past runs are under **Executions**.
- **Pause:** delete the trigger under **Triggers**. To resume, run `setup()` again.
- **Quotas:** a free Gmail account allows 90 minutes of trigger runtime per day,
  and each run takes about 1 second, so it stays well within the limit.
