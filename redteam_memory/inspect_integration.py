from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .store import MemoryStore


def _sample_input(bundle: dict[str, Any]) -> str:
    user_turns = [turn for turn in bundle.get("turns", []) if turn.get("role") == "user"]
    if user_turns:
        return str(user_turns[-1].get("content", ""))
    attempts = bundle.get("attempts", [])
    if attempts:
        return str(attempts[-1].get("input_text", ""))
    return ""


def load_inspect_samples(
    db_path: str | Path,
    *,
    case_ids: Iterable[str] | None = None,
    include_empty: bool = False,
) -> list[Any]:
    """Load stored cases as Inspect AI ``Sample`` objects.

    Cases without an observed input are skipped by default. This prevents a
    metadata-only seed record from silently becoming an empty experiment.
    """
    try:
        from inspect_ai.dataset import Sample
    except ImportError as exc:
        raise RuntimeError(
            "Inspect AI is not importable in this Python environment. "
            "Run with the Inspect project venv or install Inspect AI."
        ) from exc

    wanted = set(case_ids) if case_ids is not None else None
    samples: list[Any] = []
    with MemoryStore(db_path) as store:
        bundles = [store.get_case(case_id) for case_id in wanted] if wanted else [
            store.get_case(item["case_id"]) for item in store.list_cases()
        ]
    for bundle in bundles:
        if bundle is None:
            continue
        input_text = _sample_input(bundle)
        if not input_text and not include_empty:
            continue
        samples.append(Sample(
            input=input_text,
            target=str(bundle.get("impact", "")),
            metadata={
                "case_id": bundle.get("case_id", ""),
                "title": bundle.get("title", ""),
                "target": bundle.get("target", ""),
                "mechanism": bundle.get("mechanism", ""),
                "carrier": bundle.get("carrier", ""),
                "status": bundle.get("status", ""),
            },
        ))
    return samples


def task_from_memory(
    db_path: str | Path,
    *,
    case_ids: Iterable[str] | None = None,
    model: str | None = None,
    include_empty: bool = False,
) -> Any:
    """Create a minimal Inspect task using stored inputs.

    No generic scorer is installed: whether a run is a real break must remain
    tied to the deployment's runtime evidence and evaluator. Callers can add a
    task-specific scorer when those criteria are known.
    """
    try:
        from inspect_ai import Task
        from inspect_ai.solver import generate
    except ImportError as exc:
        raise RuntimeError(
            "Inspect AI is not importable in this Python environment. "
            "Run with the Inspect project venv or install Inspect AI."
        ) from exc
    samples = load_inspect_samples(db_path, case_ids=case_ids, include_empty=include_empty)
    if not samples:
        raise ValueError(
            "No stored inputs are available for Inspect AI. Record at least one user turn "
            "or attempt first, or pass include_empty=True for a metadata-only task."
        )
    return Task(
        dataset=samples,
        solver=generate(),
        model=model,
        metadata={"source": "ai_redteam_agent", "db_path": str(Path(db_path).resolve())},
    )
