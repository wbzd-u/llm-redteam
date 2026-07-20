from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

from .models import Attempt, Case
from .store import MemoryStore


DATASET_CAVEAT = (
    "IPI Arena seed only: the dataset README reports that these attacks succeeded "
    "on open-source models but did not transfer to closed-source models in that arena. "
    "Treat every imported item as unverified until runtime evidence exists."
)


def iter_ipi_records(path: str | Path) -> Iterator[dict[str, Any]]:
    """Read and validate the local IPI Arena JSONL dataset."""
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number} of {source}") from exc
            behavior_id = str(record.get("behavior_id", "")).strip()
            attack = record.get("attack")
            if not behavior_id or not isinstance(attack, str) or not attack.strip():
                raise ValueError(f"line {line_number} must contain non-empty behavior_id and attack")
            yield {
                "behavior_id": behavior_id,
                "attack": attack,
                "source_line": line_number,
            }


def ipi_case_id(behavior_id: str, attack: str) -> str:
    digest = hashlib.sha256(f"{behavior_id}\0{attack}".encode("utf-8")).hexdigest()[:16]
    return f"ipi-{digest}"


def import_ipi_dataset(
    store: MemoryStore,
    path: str | Path,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Import IPI attacks as deterministic seed cases and attempts."""
    imported_cases = 0
    imported_attempts = 0
    records_seen = 0
    behavior_ids: set[str] = set()
    for index, record in enumerate(iter_ipi_records(path)):
        if limit is not None and index >= limit:
            break
        records_seen += 1
        behavior_id = record["behavior_id"]
        attack = record["attack"]
        case_id = ipi_case_id(behavior_id, attack)
        case = Case(
            case_id=case_id,
            title=f"IPI Arena seed: {behavior_id}",
            target=behavior_id,
            challenge="IPI Arena",
            mechanism="indirect prompt injection",
            carrier="untrusted document or tool content",
            impact="agent behavior or tool action",
            status="seed",
            tags=["ipi", "dataset", "source:ipi_arena_attacks"],
            notes=DATASET_CAVEAT,
        )
        existed = store.get_case(case_id) is not None
        store.save_case(case)
        if not existed:
            imported_cases += 1
        attempt_id = f"{case_id}-attempt"
        if not store.has_attempt(attempt_id):
            store.add_attempt(Attempt(
                attempt_id=attempt_id,
                case_id=case_id,
                mechanism="indirect prompt injection",
                input_text=attack,
                outcome="unknown",
                notes=(
                    f"Dataset behavior_id={behavior_id}; source line={record['source_line']}. "
                    "Seed input is not evidence of a successful break."
                ),
            ))
            imported_attempts += 1
        behavior_ids.add(behavior_id)
    return {
        "cases_created": imported_cases,
        "attempts_created": imported_attempts,
        "records_seen": records_seen,
        "behavior_ids": sorted(behavior_ids),
        "source": str(Path(path).resolve()),
    }
