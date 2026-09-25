# Every eval run appends one line to eval/history.jsonl: when, which code, what scores.
import json
import subprocess
from datetime import datetime

HISTORY_PATH = "eval/history.jsonl"


def log_run(kind, metrics):
    """Append one run's scores to the history file."""
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True
    ).stdout.strip()

    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "kind": kind,
        "git_commit": commit,
        "metrics": metrics,
    }
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")