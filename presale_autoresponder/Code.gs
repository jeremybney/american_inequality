/**
 * The Opportunity Map — presale bonus auto-responder (Google Apps Script).
 *
 * Watches Gmail for Wix form notifications and emails the buyer their bonus
 * content. See README.md in this folder for setup.
 */

// Wix notifications that should trigger the bonus email.
var WATCHED_FORMS = [
  { from: 'jeremybney@wix-forms.com', subject: 'Receipt-submission-personal-site got a new submission' },
  { from: 'notifications@wix-forms.com', subject: 'Pre-sale confirmation got a new submission' }
];

var REPLY_SUBJECT = 'Your bonus content for The Opportunity Map presale';
var SENDER_NAME = 'Jeremy Ney';
var DONE_LABEL = 'Presale bonus sent';
// "Opportunity Map Presale Submissions" sheet; every submission is logged to its Submissions tab.
var SHEET_ID = '1clGrdE3eQo0bbi8AEn_sJKtatPHCKawqBaSkl7vuJUc';
var SHEET_TAB = 'Submissions';
var LINKS = {
  whatsapp: 'https://chat.whatsapp.com/GpBoiUrRk7OHWcHrvsV7v0',
  bonus: 'https://youtube.com/playlist?list=PLUryKyLf39gI&si=eZ_IxPmutjR0cLZ1',
  album: 'https://myalbum.com/album/SPz2zopRhSdxyi/?invite=a4b14aca-bd6d-4752-b26c-0513b5435a65',
  amazon: 'https://www.amazon.com/dp/1541705874',
  donate: 'https://www.worthybooks.org/the-opportunity-map'
};

/** Entry point for the time-driven trigger. */
function processSubmissions() {
  var props = PropertiesService.getScriptProperties();
  var label = GmailApp.getUserLabelByName(DONE_LABEL) || GmailApp.createLabel(DONE_LABEL);

  WATCHED_FORMS.forEach(function (form) {
    var query = 'from:' + form.from + ' subject:"' + form.subject + '" newer_than:7d';
    GmailApp.search(query, 0, 50).forEach(function (thread) {
      thread.getMessages().forEach(function (message) {
        var key = 'done_' + message.getId();
        if (props.getProperty(key)) return;
        if (message.getFrom().toLowerCase().indexOf(form.from) === -1) return;
        if (message.getSubject().trim() !== form.subject) return;

        var fields = parseSubmission(message.getPlainBody());
        if (!fields.email) {
          console.warn('No valid email found in message ' + message.getId() + '; skipping.');
          logSubmission(message, form, fields, 'Not sent: no valid email');
          props.setProperty(key, 'skipped');
          return;
        }

        sendBonusEmail(fields.email, fields.name);
        var sentAt = new Date();
        props.setProperty(key, sentAt.toISOString());
        logSubmission(message, form, fields, sentAt);
        thread.addLabel(label);
        console.log('Sent bonus email to ' + fields.email);
      });
    });
  });
}

/**
 * Pulls the name and email out of a Wix "Submission summary", which looks like:
 *   First name : John      (or "Name : Jane Smith")
 *   Email : john@example.com
 */
function parseSubmission(body) {
  var name = matchField(body, /^\s*(?:first\s+name|full\s+name|name)\s*:\s*(.+?)\s*$/im);
  var email = matchField(body, /^\s*e-?mail\s*:\s*(\S+@\S+?)\s*$/im);
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) email = '';
  var order = matchField(body, /^\s*order\s+number\s*:\s*(.+?)\s*$/im);
  return { name: name, email: email, order: order };
}

/**
 * Adds the submission to the sheet, or fills in "Bonus email sent" if a row
 * with the same Gmail message ID is already there.
 * Columns: Submitted | Form | Name | Email | Order number | Bonus email sent | Gmail message ID
 */
function logSubmission(message, form, fields, sent) {
  try {
    var sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_TAB);
    var ids = sheet.getRange('G:G').getValues().map(function (r) { return String(r[0]); });
    var row = ids.indexOf(message.getId());
    if (row > -1) {
      sheet.getRange(row + 1, 6).setValue(sent);
      return;
    }
    sheet.appendRow([
      message.getDate(),
      form.subject.replace(' got a new submission', ''),
      fields.name,
      fields.email,
      fields.order,
      sent,
      message.getId()
    ]);
  } catch (e) {
    // A logging problem should never stop buyers from getting their email.
    console.error('Could not log submission ' + message.getId() + ': ' + e);
  }
}

function matchField(body, regex) {
  var m = body.match(regex);
  return m ? m[1].trim() : '';
}

function sendBonusEmail(to, fullName) {
  var firstName = (fullName || '').split(/\s+/)[0];
  var greeting = firstName ? 'Hi ' + firstName + ',' : 'Hi there,';
  GmailApp.sendEmail(to, REPLY_SUBJECT, buildPlainBody(greeting), {
    htmlBody: buildHtmlBody(escapeHtml(greeting)),
    name: SENDER_NAME
  });
}

function buildHtmlBody(greeting) {
  return [
    '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.5;color:#222;">',
    '<p>' + greeting + '</p>',
    '<p>Thank you for purchasing your copy of <i>The Opportunity Map</i>! We\'ve got some bonuses for you:</p>',
    '<ul>',
    '<li><a href="' + LINKS.whatsapp + '">Join our WhatsApp Street Team</a>, where we\'ll be sharing information about events, book updates, and ways to connect with others.</li>',
    '<li>You\'ve unlocked access to <a href="' + LINKS.bonus + '">all our bonus content for the book</a>, which I\'ll update every 2 weeks in the lead up to launch.</li>',
    '<li>I\'m sharing a <a href="' + LINKS.album + '">behind-the-scenes album of all my travels for the book</a> to give you a deeper sense of what these communities are like.</li>',
    '</ul>',
    '<p>In the meantime, please <a href="' + LINKS.amazon + '">share the book with a friend</a> or ',
    '<a href="' + LINKS.donate + '">donate a copy</a> to help fill a struggling library in one of the left-behind places profiled in <i>The Opportunity Map</i>.</p>',
    '<p>Most sincerely,<br>Jeremy</p>',
    '</div>'
  ].join('\n');
}

// Fallback for email clients that don't render HTML.
function buildPlainBody(greeting) {
  return [
    greeting,
    '',
    'Thank you for purchasing your copy of The Opportunity Map! We\'ve got some bonuses for you:',
    '',
    '* Join our WhatsApp Street Team, where we\'ll be sharing information about events, book updates, and ways to connect with others: ' + LINKS.whatsapp,
    '* You\'ve unlocked access to all our bonus content for the book, which I\'ll update every 2 weeks in the lead up to launch: ' + LINKS.bonus,
    '* I\'m sharing a behind-the-scenes album of all my travels for the book to give you a deeper sense of what these communities are like: ' + LINKS.album,
    '',
    'In the meantime, please share the book with a friend (' + LINKS.amazon + ') or donate a copy (' + LINKS.donate + ') to help fill a struggling library in one of the left-behind places profiled in The Opportunity Map.',
    '',
    'Most sincerely,',
    'Jeremy'
  ].join('\n');
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Run once from the editor: creates a trigger that checks Gmail every 5 minutes. */
function installTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'processSubmissions') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('processSubmissions').timeBased().everyMinutes(5).create();
}

/** Run from the editor to email yourself a preview without touching any submissions. */
function sendTestEmail() {
  sendBonusEmail(Session.getActiveUser().getEmail(), 'Jeremy Ney');
}
