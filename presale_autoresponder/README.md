# Presale bonus auto-responder

A Google Apps Script that runs in your Gmail account. Every 5 minutes it looks for these Wix form notifications:

| From | Subject |
|---|---|
| `jeremybney@wix-forms.com` | Receipt-submission-personal-site got a new submission |
| `notifications@wix-forms.com` | Pre-sale confirmation got a new submission |

It reads the `Name` / `First name` and `Email` fields from the submission summary. Then it sends the buyer the "Your bonus content for The Opportunity Map presale" email from your Gmail. Each submission is answered only once. Handled threads get the Gmail label **Presale bonus sent**.

## Setup (about 5 minutes)

1. While signed in as jeremybney@gmail.com, go to https://script.google.com and click **New project**. Name it "Presale auto-responder".
2. Delete the sample code in `Code.gs` and paste in the contents of [`Code.gs`](Code.gs). Save.
3. Choose `sendTestEmail` from the function dropdown and click **Run**. Google will ask you to authorize Gmail access. Click through ("Advanced → Go to project" if it warns that the app is unverified, because it's your own script). Check your inbox for the preview.
4. Choose `installTrigger` and click **Run**. The responder is now live.

## Notes

- **Existing submissions:** the script checks messages from the last 7 days. Your two test submissions from Oct 4 (Jane Test2 / John Test) will therefore get a reply on the first run. Both go to your own address, which makes a handy end-to-end test.
- **Greeting** uses the first word of the name ("Jane Test2" → "Hi Jane,"). If no name is found, it says "Hi there,".
- **Logs:** in the Apps Script editor, open **Executions** to see who was emailed.
- **Limits:** a free Gmail account can send about 100 Apps Script emails per day. Google Workspace accounts can send about 1,500.
- **To stop it:** open **Triggers** (the clock icon) and delete the `processSubmissions` trigger.
- **To edit the copy or links:** change `LINKS`, `buildHtmlBody` and `buildPlainBody` in `Code.gs`.
