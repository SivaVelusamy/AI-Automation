# 01-send-daily-report — Example Workflow

File: 01-send-daily-report.json

## Description
Sends a daily summary report to a Slack channel by reading data from a Google Sheet, formatting a short message, and posting it to Slack on a schedule.

## Purpose / Use case
- Daily operational summary for the team.
- Scheduled at a specific time each day (e.g., 08:00 UTC).

## Nodes used
- Schedule Trigger — runs daily at the configured time.
- Google Sheets — reads a range with the day's metrics.
- Function / Set — formats the message text and aggregates values.
- Slack — posts the message to a channel.

## Required credentials
- Google Sheets: OAuth or Service Account with read access to the sheet.
- Slack: Bot token with chat:write scope.

## Environment variables (optional)
- REPORT_SHEET_ID — Google Sheet ID to read from.
- SLACK_CHANNEL — channel ID or name to post the report.

## How to import
1. Import `01-send-daily-report.json` into the n8n Editor (Workflow → Import from file).
2. Add the required credentials in n8n (Google Sheets, Slack).
3. Update any environment variables or node parameters (sheet ID, range, channel).

## How to test
1. In the Schedule Trigger node set the schedule to `Manual` or use a short test interval (e.g., every minute).
2. Manually execute the workflow or wait for the trigger.
3. Verify that the Google Sheets node returns rows and that the Slack node posts the expected message.

Example expected Slack message:
"Daily Report — 2026-08-15\n• New signups: 12\n• Errors: 0\n• Revenue: $1,250"

## Troubleshooting
- Google Sheets permissions error: ensure the credential has access to the sheet and the correct Sheet ID is used.
- Slack post fails: verify the bot token scopes and the channel ID.
- No data returned: check the sheet range and date filters in the Google Sheets node.

## Notes
- Adjust timezones in the Schedule Trigger or convert timestamps in a Function node.
- Consider adding retries and error reporting (e.g., send errors to a monitoring Slack channel).

---
This example README is intentionally generic — if you want, I can also:
- Create a minimal example JSON workflow file that implements this flow, or
- Update this example README to match an existing workflow JSON in the repo (tell me the filename).
