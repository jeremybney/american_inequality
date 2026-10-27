/**
 * The Opportunity Map — donor thank-you email (Google Apps Script).
 *
 * Checks the "Book Sale Overview" tab of the OPM Fulfillment Breakdown sheet.
 * For each Shopify Worthy order from SW36 on (the first order on row 111 when
 * this was set up) whose copy count (column D) is 5 to 9 (inclusive), it emails the donor once with the Opportunity Mapping
 * Playbook.
 *
 * Runs in its own Apps Script project, separate from the presale auto-responder.
 */

var DONOR_SHEET_ID = '1oGdXnUso53Kzq0PLFV__A0ynOT7nZl5g7EitIKV6yfc';
var DONOR_SHEET_TAB = 'Book Sale Overview';
// Orders SW1-SW35 (rows 61-110) came before this was set up and are skipped.
// Going by order number rather than row means inserted rows can't pull them in.
var DONOR_FIRST_ORDER = 36;
var DONOR_MIN_COPIES = 5;  // inclusive
var DONOR_MAX_COPIES = 9;  // inclusive
var DONOR_SUBJECT = 'Thank you for donating copies of The Opportunity Map';
var DONOR_PLAYBOOK_URL = 'https://cultureof.one/peer-places/';

/** Entry point for the time-driven trigger. */
function donorCheckSheet() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    donorProcessRows();
  } finally {
    lock.releaseLock();
  }
}

function donorProcessRows() {
  var props = PropertiesService.getScriptProperties();
  donorMatchingRows().forEach(function (m) {
    if (props.getProperty(m.key)) return;
    donorSendEmail(m.email, m.firstName, m.copies);
    props.setProperty(m.key, new Date().toISOString());
    console.log('Row ' + m.row + ' (' + m.order + '): sent donor thank-you to ' + m.email);
  });
}

/** Order rows from SW36 on with 5-9 copies and an email in column B. */
function donorMatchingRows() {
  var sheet = SpreadsheetApp.openById(DONOR_SHEET_ID).getSheetByName(DONOR_SHEET_TAB);
  // Columns A (order), B (name + email), D (total books).
  var rows = sheet.getRange(1, 1, sheet.getLastRow(), 4).getValues();
  var matches = [];
  rows.forEach(function (r, i) {
    var order = String(r[0]).trim();
    // Shopify Worthy order rows look like "SW36-Shopify Order 1448" (or "SW-20-...").
    var num = order.match(/^SW-?(\d+)/i);
    if (!num || Number(num[1]) < DONOR_FIRST_ORDER) return;

    var copies = Number(String(r[3]).replace(/,/g, ''));
    if (!(copies >= DONOR_MIN_COPIES && copies <= DONOR_MAX_COPIES)) return;

    var contact = donorParseContact(String(r[1]));
    if (!contact.email) return;  // Email not filled in yet; try again next run.

    matches.push({
      row: i + 1, order: order, copies: copies, email: contact.email, firstName: contact.firstName,
      key: 'donor_' + order + '|' + contact.email.toLowerCase()
    });
  });
  return matches;
}

/** Column B looks like "Seth Harper\nseth.t.harper@gmail.com". */
function donorParseContact(cell) {
  var emailMatch = cell.match(/[^\s@]+@[^\s@]+\.[^\s@]+/);
  var firstLine = cell.split('\n')[0].trim();
  var firstName = /@/.test(firstLine) ? '' : firstLine.split(/\s+/)[0];
  return { email: emailMatch ? emailMatch[0] : '', firstName: firstName };
}

function donorSendEmail(to, firstName, copies) {
  var greeting = firstName ? 'Hi ' + firstName + ',' : 'Hi there,';
  GmailApp.sendEmail(to, DONOR_SUBJECT, donorPlainBody(greeting, copies), {
    htmlBody: donorHtmlBody(donorEscapeHtml(greeting), copies),
    name: 'Jeremy Ney'
  });
}

function donorHtmlBody(greeting, copies) {
  return [
    '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.5;color:#222;">',
    '<p>' + greeting + '</p>',
    '<p>Thank you for donating ' + copies + ' copies of <i>The Opportunity Map</i> to help fill struggling public libraries across the country. Your support makes an incredible difference in addressing our reading crisis in the US and ensuring communities know we are investing in them.</p>',
    '<p>Enjoy this sneak peek at the <a href="' + DONOR_PLAYBOOK_URL + '">Opportunity Mapping Playbook</a>, which highlights similar communities that have figured out how to learn from each other and the blueprints they followed for upward mobility.</p>',
    '<p>Each section lays out why those places are similar, how they connected, and the blue bar details the playbook they pursued.</p>',
    '<p>Enjoy the playbook and add your community at the bottom if you think you fit the mold for getting added.</p>',
    '<p>Most sincerely,<br>Jeremy</p>',
    '</div>'
  ].join('\n');
}

// Fallback for email clients that don't render HTML.
function donorPlainBody(greeting, copies) {
  return [
    greeting,
    '',
    'Thank you for donating ' + copies + ' copies of The Opportunity Map to help fill struggling public libraries across the country. Your support makes an incredible difference in addressing our reading crisis in the US and ensuring communities know we are investing in them.',
    '',
    'Enjoy this sneak peek at the Opportunity Mapping Playbook (' + DONOR_PLAYBOOK_URL + '), which highlights similar communities that have figured out how to learn from each other and the blueprints they followed for upward mobility.',
    '',
    'Each section lays out why those places are similar, how they connected, and the blue bar details the playbook they pursued.',
    '',
    'Enjoy the playbook and add your community at the bottom if you think you fit the mold for getting added.',
    '',
    'Most sincerely,',
    'Jeremy'
  ].join('\n');
}

function donorEscapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Run once from the editor: checks the sheet every 10 minutes. */
function donorInstallTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'donorCheckSheet') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('donorCheckSheet').timeBased().everyMinutes(10).create();
}

/**
 * Run from the editor before installing the trigger. Emails nobody: it logs
 * which rows would get an email right now (see the Execution log).
 */
function donorDryRun() {
  var props = PropertiesService.getScriptProperties();
  var matches = donorMatchingRows();
  matches.forEach(function (m) {
    console.log('Row ' + m.row + ': ' + m.order + ', ' + m.email + ', ' + m.copies + ' copies' +
      (props.getProperty(m.key) ? ' (already sent)' : ' -> WOULD SEND'));
  });
  console.log(matches.length + ' matching order(s) from SW' + DONOR_FIRST_ORDER + ' on.');
}

/** Run from the editor to email yourself a preview (uses 5 copies as the example). */
function donorSendTestEmail() {
  donorSendEmail(Session.getActiveUser().getEmail(), 'Jeremy', 5);
}
