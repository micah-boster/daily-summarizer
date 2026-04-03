# Cowork Scheduled Task Setup Guide

## Overview

The Daily Summarizer validation script needs to run once per day to prove the execution model works. Cowork (Claude Desktop's scheduling feature) handles this by running the script automatically at a configured time.

## What the Scheduled Task Does

Each run executes the validation script, which:

1. Loads Google OAuth credentials and auto-refreshes if expired
2. Fetches today's calendar events via the Google Calendar API
3. Writes a timestamped JSON output file to `output/validation/`
4. Appends a pass/fail entry to `output/validation/validation_log.jsonl`
5. Sends a Slack DM notification with the result
6. On failure: retries once after 15 minutes, then sends a failure notification

## Cowork Configuration

### Task Settings

| Setting | Value |
|---------|-------|
| **Task name** | Daily Summarizer Validation |
| **Schedule** | Daily |
| **Time** | 5:00 PM ET |
| **Days** | Every day (including weekends) |

### Task Instruction

Use this as the Cowork task instruction/prompt:

```
cd "/Users/micah/Desktop/CODE/DAILY SUMMARIZER" && uv run python -m src.validation.daily_check
```

### Setup Steps

1. Open **Claude Desktop** (Cowork)
2. Navigate to **Scheduled Tasks** (or the task scheduling interface)
3. Create a new scheduled task with the settings from the table above
4. Paste the task instruction from above
5. Save and enable the task

## Machine Requirements

- **Machine must be awake** at task time (5:00 PM ET). Cowork Desktop tasks only run while the machine is awake and Claude Desktop is open.
- **If the machine is asleep** at the scheduled time, Cowork will auto-run the skipped task when the machine wakes up. The output timestamp will reflect the actual run time, not the scheduled time.
- **Recommended:** Set a macOS energy schedule to prevent sleep during 5-6 PM ET:
  - System Settings > Energy (or Battery) > Schedule
  - Prevent sleep during 5:00 PM - 6:00 PM

## Expected Behavior

After each scheduled run, you should see:

1. **New file** in `output/validation/` named `YYYY-MM-DD_HH-MM.json` containing today's calendar events
2. **New line** appended to `output/validation/validation_log.jsonl` with pass/fail status
3. **Slack DM** notification with the result (e.g., "Validation PASSED: 8 calendar events found. Output: 2026-04-03_21-00.json | Total passes: 3/5")

## How to Monitor

### Quick pass count

```bash
cd "/Users/micah/Desktop/CODE/DAILY SUMMARIZER"
uv run python -c "from src.validation.run_log import count_passes; print(f'Passes: {count_passes()}')"
```

### View recent log entries

```bash
cd "/Users/micah/Desktop/CODE/DAILY SUMMARIZER"
uv run python -c "from src.validation.run_log import get_recent_entries; [print(e) for e in get_recent_entries(5)]"
```

### View the full validation log

```bash
cat output/validation/validation_log.jsonl
```

### List all output files

```bash
ls -la output/validation/*.json
```

## Success Criteria

Phase 0 validation is complete when:

- **5 total pass entries** exist in `output/validation/validation_log.jsonl` (not necessarily consecutive days)
- Each pass entry contains real calendar event data (event titles, times, attendees)
- Slack DM notifications were received for each run
- No manual OAuth intervention was needed during the run period (tokens auto-refreshed)

Check completion:

```bash
cd "/Users/micah/Desktop/CODE/DAILY SUMMARIZER"
uv run python -c "from src.validation.run_log import count_passes; p = count_passes(); print(f'Passes: {p}/5 -- {\"PHASE 0 COMPLETE\" if p >= 5 else \"Keep running\"}')"
```

## Troubleshooting

### Task didn't run at scheduled time

- Was the machine awake? Check if an output file appeared later (Cowork auto-runs on wake)
- Was Claude Desktop open? The app must be running for Cowork tasks to fire

### Slack notification says credentials failed

- Follow the [Re-Authentication Procedure](re-auth-procedure.md) to refresh OAuth tokens
- After re-auth, the next scheduled run should succeed automatically

### Output file has 0 events

- This is a valid pass -- it means the Calendar API returned successfully but no events were on the calendar that day
- The validation proves the auth and API pipeline works, even with 0 events
