/**
 * Substack unsubscribe tracker (replaces the two Zapier zaps).
 *
 * Watches Gmail for Substack's unsubscribe notifications and appends one row
 * per unsubscriber to the "Unsubscribed Emails from Newsletter" spreadsheet:
 *
 *   "Unsubscription for American Inequality" + Prior status: Paid  -> Paid tab
 *   "Email disabled for American Inequality" (free subscribers)    -> Sheet1 tab
 *
 * Runs every minute. It searches `in:anywhere`, so an email you have already
 * moved to Trash is still picked up (Gmail keeps Trash for 30 days).
 *
 * Setup: paste into an Apps Script project, run setup() once, approve access.
 */

const SPREADSHEET_ID = '1C2mtCYPkjowMRqoqcK6i5i7Oj-QYEbDXtw8bPrfuU7k';
const REGULAR_SHEET_GID = 0;          // "Sheet1" tab
const PAID_SHEET_GID = 1260698282;    // "Paid" tab

const ROW_SUBJECT = 'Email from American Inequality';  // what the zaps wrote in column B
const SEARCH_QUERY =
  'in:anywhere from:no-reply@substack.com ' +
  'subject:("Unsubscription for American Inequality" OR "Email disabled for American Inequality")';
const DAY_MS = 24 * 60 * 60 * 1000;

const OVERLAP_MS = 60 * 60 * 1000;            // re-scan the last hour to catch late arrivals
const SEEN_RETENTION_MS = 3 * 24 * 60 * 60 * 1000;
const PROP_CURSOR = 'cursorMs';
const PROP_SEEN = 'seenIds';


/** Run once by hand: starts tracking from now and installs the 1-minute trigger. */
function setup() {
  const props = PropertiesService.getScriptProperties();
  props.setProperty(PROP_CURSOR, String(Date.now()));
  props.setProperty(PROP_SEEN, '{}');

  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'checkUnsubscribes')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('checkUnsubscribes').timeBased().everyMinutes(1).create();

  checkUnsubscribes();
}

/**
 * Optional: re-process notifications received since the given date, e.g.
 * backfillSince('2026-10-29 12:00') to cover a gap between turning off
 * Zapier and running setup(). Rows already added by this script are skipped,
 * rows Zapier added are not, so pick the date with that in mind.
 */
function backfillSince(dateString) {
  const sinceMs = new Date(dateString).getTime();
  if (isNaN(sinceMs)) throw new Error('Could not parse date: ' + dateString);
  const props = PropertiesService.getScriptProperties();
  props.setProperty(PROP_CURSOR, String(sinceMs + OVERLAP_MS));
  props.setProperty(PROP_SEEN, '{}');
  checkUnsubscribes();
}

/** Trigger handler. */
function checkUnsubscribes() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) return;  // previous run still going
  try {
    const props = PropertiesService.getScriptProperties();
    const cursorMs = Number(props.getProperty(PROP_CURSOR) || Date.now());
    const seen = JSON.parse(props.getProperty(PROP_SEEN) || '{}');
    const sinceMs = cursorMs - OVERLAP_MS;

    // Search by whole days and filter to the exact time below.
    const days = Math.ceil((Date.now() - sinceMs) / DAY_MS) + 1;
    const threads = GmailApp.search(SEARCH_QUERY + ' newer_than:' + days + 'd', 0, 100);

    const found = [];
    threads.forEach(thread => {
      // Substack threads these notifications, so one thread can hold many.
      thread.getMessages().forEach(msg => {
        const id = msg.getId();
        const dateMs = msg.getDate().getTime();
        if (dateMs < sinceMs || seen[id]) return;
        // Substack sends these as HTML only, so read the HTML body.
        const parsed = parseNotification(msg.getSubject(), htmlToText(msg.getBody()));
        if (parsed) found.push({ id, dateMs, threadId: thread.getId(), parsed });
        else console.warn('Could not read unsubscribe email ' + id + ': ' + msg.getSubject());
      });
    });

    if (found.length) {
      found.sort((a, b) => a.dateMs - b.dateMs);
      const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
      const regular = sheetByGid(ss, REGULAR_SHEET_GID);
      const paid = sheetByGid(ss, PAID_SHEET_GID);
      const rows = { regular: [], paid: [] };

      found.forEach(f => {
        rows[f.parsed.tab].push([
          f.parsed.email,
          ROW_SUBJECT,
          'https://mail.google.com/mail/u/0/#inbox/' + f.threadId,
          Utilities.formatDate(new Date(f.dateMs), 'UTC', 'yyyy-MM-dd H:mm:ss'),
        ]);
      });
      appendRows(regular, rows.regular);
      appendRows(paid, rows.paid);
      SpreadsheetApp.flush();

      found.forEach(f => { seen[f.id] = f.dateMs; });
    }

    const newest = Math.max(cursorMs, ...found.map(f => f.dateMs));
    Object.keys(seen).forEach(id => {
      if (seen[id] < newest - SEEN_RETENTION_MS) delete seen[id];
    });
    props.setProperty(PROP_CURSOR, String(newest));
    props.setProperty(PROP_SEEN, JSON.stringify(seen));
  } finally {
    lock.releaseLock();
  }
}

/**
 * Pulls the subscriber email and routes it to a tab.
 * Returns {email, status, tab} or null if the message isn't an unsubscribe notice.
 */
function parseNotification(subject, body) {
  const isUnsubscription = /Unsubscription for American Inequality/i.test(subject);
  const isDisabled = /Email disabled for American Inequality/i.test(subject);
  if (!isUnsubscription && !isDisabled) return null;

  const emailMatch = /Email:\s*([A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})/i.exec(body || '');
  if (!emailMatch) return null;
  const statusMatch = /Prior status:\s*([A-Za-z ]+?Subscriber)/i.exec(body || '');
  const status = statusMatch ? statusMatch[1].trim() : '';

  // A paid cancellation goes to Paid; anything else (free unsubscribes) to Sheet1.
  const tab = isUnsubscription && /paid/i.test(status) ? 'paid' : 'regular';
  return { email: emailMatch[1], status, tab };
}

/** Turns an HTML email body into text, one line per <br>/<p>. */
function htmlToText(html) {
  return (html || '')
    .replace(/<(style|script)[^>]*>[\s\S]*?<\/\1>/gi, '')
    .replace(/<br\s*\/?>|<\/(p|div|tr|li|h\d)>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)));
}

/** Run by hand to see what the script finds in Gmail right now (View > Logs). */
function diagnose() {
  const props = PropertiesService.getScriptProperties();
  console.log('Cursor: ' + new Date(Number(props.getProperty(PROP_CURSOR))).toISOString());
  console.log('Triggers: ' + ScriptApp.getProjectTriggers().map(t => t.getHandlerFunction()).join(', '));
  GmailApp.search(SEARCH_QUERY + ' newer_than:2d', 0, 20).forEach(thread => {
    thread.getMessages().slice(-10).forEach(msg => {
      const parsed = parseNotification(msg.getSubject(), htmlToText(msg.getBody()));
      console.log(msg.getDate().toISOString() + '  ' + msg.getSubject() + '  ->  ' + JSON.stringify(parsed));
    });
  });
}

function sheetByGid(ss, gid) {
  const sheet = ss.getSheets().find(s => s.getSheetId() === gid);
  if (!sheet) throw new Error('No tab with gid ' + gid + ' in spreadsheet');
  return sheet;
}

/** Writes below the last row that has an email in column A. */
function appendRows(sheet, rows) {
  if (!rows.length) return;
  const colA = sheet.getRange('A:A').getValues();
  let last = colA.length;
  while (last > 0 && colA[last - 1][0] === '') last--;
  const needed = last + rows.length - sheet.getMaxRows();
  if (needed > 0) sheet.insertRowsAfter(sheet.getMaxRows(), needed);
  sheet.getRange(last + 1, 1, rows.length, rows[0].length).setValues(rows);
}

// Lets parseNotification be unit-tested under Node; ignored by Apps Script.
if (typeof module !== 'undefined') module.exports = { parseNotification, htmlToText };
