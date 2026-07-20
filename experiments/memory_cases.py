from __future__ import annotations

import os
from pathlib import Path

from inspect_ai import task

from redteam_memory.inspect_integration import task_from_memory


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "redteam_memory.sqlite3"


@task
def memory_cases():
    """Run recorded cases through an Inspect-configured model."""
    db_path = Path(os.environ.get("REDTEAM_MEMORY_DB", str(DEFAULT_DB)))
    raw_case_ids = os.environ.get("REDTEAM_CASE_IDS", "")
    case_ids = [item.strip() for item in raw_case_ids.split(",") if item.strip()] or None
    return task_from_memory(db_path, case_ids=case_ids)
