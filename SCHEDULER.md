> **Not needed any more.** The `market-loop` workflow now runs the 5-minute and hourly scans inside GitHub on the minute. Keep this only if you want an extra outside trigger; if you set up cron-job.org jobs, pause them to avoid duplicate runs.

# Run on the minute: trigger the workflow from outside GitHub

GitHub's own `schedule:` is best effort. Its docs say the schedule event can be delayed under load (the start of every hour is the worst), and runs are sometimes skipped. It cannot be made exact.
The fix is to let a real scheduler call GitHub's API at the exact minute. It is free and takes about 10 minutes.

## 1. Make a token (once)
GitHub > your profile picture > **Settings** > **Developer settings** > **Personal access tokens** > **Fine-grained tokens** > **Generate new token**.
- Repository access: **Only select repositories** > `stock-scanner-pssytyx`
- Permissions > Repository permissions > **Actions: Read and write** (nothing else)
- Expiration: 90 days (put a reminder to renew it)
Copy the token. Treat it like a password: never paste it into the repo or a chat. If it leaks, revoke it.

## 2. Create the jobs on cron-job.org (free)
Create an account at https://cron-job.org, then **Create cronjob** for each row. In every job set:
- **URL:** `https://api.github.com/repos/raishwarya431-droid/stock-scanner-pssytyx/actions/workflows/scan.yml/dispatches`
- **Request method:** POST (Advanced tab)
- **Headers:** `Accept: application/vnd.github+json`, `Authorization: Bearer YOUR_TOKEN`, `X-GitHub-Api-Version: 2022-11-28`, `Content-Type: application/json`
- **Request body:** as in the table
- **Time zone:** Asia/Kolkata
- Turn on "Save responses" so you can see the result. A good call returns **204**.

| Job | When (IST, Mon to Fri) | Request body |
|---|---|---|
| DS live | every 5 minutes, hours 9 to 15 (add one at 15:35) | `{"ref":"main","inputs":{"mode":"live"}}` |
| DS swing hourly | minute 25, hours 10 to 15 | `{"ref":"main","inputs":{"mode":"swing"}}` |
| DS swing pre-open and post-close | 08:35 and 16:15 | `{"ref":"main","inputs":{"mode":"swing"}}` |

Use "Test run" on each job once. A new run appears in the Actions tab within seconds, labelled "Manually run by ...".

## 3. What "sharp" means
The trigger fires on the minute. The scan itself then takes about 2 minutes (live) and 4 to 6 minutes (full Nifty 500 swing scan) to finish and publish, and Yahoo's own data can lag a little. If you want the page fresh at 10:25, trigger the swing job at about 10:20.

## 4. Keep the fallback
`scan.yml` still has a few GitHub crons as a fallback (every 30 minutes and the swing times). If the outside scheduler ever fails, you still get updates, just late. Runs are queued one at a time, so extra runs do no harm.

## Alternatives
A Cloudflare Worker with a Cron Trigger, AWS EventBridge Scheduler or any always-on machine can make the same POST. The request is identical.
