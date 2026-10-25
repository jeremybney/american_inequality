# Presale bonus auto-responder

A Google Apps Script that runs in your Gmail account. Every 5 minutes it looks for these Wix form notifications:

| From | Subject |
|---|---|
| `jeremybney@wix-forms.com` | Receipt-submission-personal-site got a new submission |
| `notifications@wix-forms.com` | Pre-sale confirmation got a new submission |

It reads the `Name` / `First name` and `Email` fields from the submission summary. Then it sends the buyer the "Your bonus content for The Opportunity Map presale" email from your Gmail. Each submission is answered only once. Handled threads get the Gmail label **Presale bonus sent**.

Every submission is also added to the [Opportunity Map Presale Submissions](https://docs.google.com/spreadsheets/d/1clGrdE3eQo0bbi8AEn_sJKtatPHCKawqBaSkl7vuJUc/edit) sheet. Each row has the submission time, form, name, email, order number, the time the bonus email went out, and the Gmail message ID.

## Setup (about 5 minutes)

1. While signed in as jeremybney@gmail.com, go to https://script.google.com and click **New project**. Name it "Presale auto-responder".
2. Delete the sample code in `Code.gs` and paste in the contents of [`Code.gs`](Code.gs). Save.
3. Choose `sendTestEmail` from the function dropdown and click **Run**. Google will ask you to authorize Gmail access. Click through ("Advanced → Go to project" if it warns that the app is unverified, because it's your own script). Check your inbox for the preview.
4. Choose `installTrigger` and click **Run**. The responder is now live.

## Updating the script

Paste the new `Code.gs` over the old one and save. If the update uses a new Google service (the sheet logging added Google Sheets), run `sendTestEmail` once so Google asks you to approve the new access. Until you approve it, the trigger fails. The trigger itself stays in place.

## Notes

- **Existing submissions:** the script checks messages from the last 7 days, and skips any submission it has already answered.
- **Greeting** uses the first word of the name ("Jane Test2" → "Hi Jane,"). If no name is found, it says "Hi there,".
- **Logs:** in the Apps Script editor, open **Executions** to see who was emailed.
- **Limits:** a free Gmail account can send about 100 Apps Script emails per day. Google Workspace accounts can send about 1,500.
- **To stop it:** open **Triggers** (the clock icon) and delete the `processSubmissions` trigger.
- **To edit the copy or links:** edit the [Presale Bonus Email](https://claude.ai/artifact/Tr9u1y6GZiu1UjGU5jAfxY) doc and ask Claude to update the script, or change `LINKS`, `buildHtmlBody` and `buildPlainBody` in `Code.gs` directly.

# Donor thank-you email (`DonorThankYou.gs`)

A separate Apps Script project, independent of the presale auto-responder. Every 10 minutes it reads the **Book Sale Overview** tab of the [OPM Fulfillment Breakdown](https://docs.google.com/spreadsheets/d/1oGdXnUso53Kzq0PLFV__A0ynOT7nZl5g7EitIKV6yfc/edit?gid=572641840) sheet, from row 111 down. If a Shopify Worthy order row (column A starts with "SW") has 5 to 9 copies (inclusive) in column D, it emails the donor once. The email thanks them for the copies and links the Opportunity Mapping Playbook. The donor's name and email come from column B.

The script only reads that sheet; it never writes to it.

## Setup

1. Go to https://script.google.com and click **New project**. Name it "Donor thank-you". Replace the sample code in `Code.gs` with [`DonorThankYou.gs`](DonorThankYou.gs) and save.
2. Run `donorDryRun`. Google asks you to approve Gmail and Sheets access the first time.
   It sends nothing and lists the rows that would get an email in the Execution log.
3. Run `donorSendTestEmail` to get a preview in your own inbox.
4. Run `donorInstallTrigger`. It's now live.

To stop it, delete the `donorCheckSheet` trigger on the Triggers page.
