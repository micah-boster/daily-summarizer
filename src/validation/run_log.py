"""JSONL validation log reader/writer.

Maintains an append-only log of validation run results at
output/validation/validation_log.jsonl. Each line is a JSON object
with at minimum: timestamp, status ("pass" or "fail").
"""

import json
from pathlib import Path

VALIDATION_LOG = Path("output/validation/validation_log.jsonl")


def append_to_log(entry: dict) -> None:
    """Append a validation result entry to the JSONL log.

    Creates parent directories if they do not exist.
    """
    VALIDATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with VALIDATION_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def count_passes() -> int:
    """Count the number of successful validation runs in the log."""
    if not VALIDATION_LOG.exists():
        return 0
    count = 0
    for line in VALIDATION_LOG.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("status") == "pass":
            count += 1
    return count


def get_recent_entries(n: int = 10) -> list[dict]:
    """Return the last N log entries for quick review."""
    if not VALIDATION_LOG.exists():
        return []
    entries = []
    for line in VALIDATION_LOG.read_text().splitlines():
        if not line.strip():
            continue
        entries.append(json.loads(line))
    return entries[-n:]
