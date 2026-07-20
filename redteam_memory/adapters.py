from __future__ import annotations

from typing import Any, Iterable

from .models import Attempt, Evidence, Turn
from .store import MemoryStore


def record_pyrit_result(store: MemoryStore, case_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Record a normalized subset of a PyRIT result without importing PyRIT.

    PyRIT result shapes vary by version and target. The adapter deliberately
    accepts a plain mapping so logs can be replayed even when PyRIT changes.
    """
    content = str(result.get("response") or result.get("output") or result.get("content") or "")
    turn = store.add_turn(
        Turn(
            case_id=case_id,
            role=str(result.get("role", "assistant")),
            content=content,
            channel=str(result.get("channel", "chat")),
            provenance=str(result.get("provenance", "pyrit")),
            observed_effect=str(result.get("observed_effect", "")),
            refusal=bool(result.get("refusal", False)),
            metadata=dict(result.get("metadata", {})),
        )
    )
    if result.get("verified") or result.get("evidence"):
        evidence_value = result.get("evidence")
        if isinstance(evidence_value, (dict, list)):
            evidence_value = str(evidence_value)
        store.add_evidence(
            Evidence(
                case_id=case_id,
                turn_id=turn.turn_id,
                kind=str(result.get("evidence_kind", "runtime")),
                description=str(result.get("evidence_description", "PyRIT result")),
                value=str(evidence_value or ""),
                source=str(result.get("evidence_source", "pyrit")),
                verified=bool(result.get("verified", False)),
            )
        )
    return turn.to_dict()


def build_inspect_sample(bundle: dict[str, Any]) -> dict[str, Any]:
    """Build a provider-neutral sample that can be mapped to an Inspect task."""
    user_turns = [t for t in bundle.get("turns", []) if t.get("role") == "user"]
    attempts = bundle.get("attempts", [])
    input_text = user_turns[-1]["content"] if user_turns else ""
    if not input_text and attempts:
        input_text = str(attempts[-1].get("input_text", ""))
    return {
        "id": bundle["case_id"],
        "input": input_text,
        "target": bundle.get("impact", ""),
        "metadata": {
            "title": bundle.get("title", ""),
            "mechanism": bundle.get("mechanism", ""),
            "carrier": bundle.get("carrier", ""),
            "status": bundle.get("status", ""),
        },
    }


def build_promptfoo_config(
    bundles: Iterable[dict[str, Any]],
    providers: list[str] | None = None,
    *,
    include_empty: bool = False,
) -> dict[str, Any]:
    """Create a minimal Promptfoo regression config from stored cases."""
    tests = []
    for bundle in bundles:
        sample = build_inspect_sample(bundle)
        if not sample["input"] and not include_empty:
            continue
        tests.append(
            {
                "description": bundle.get("title", bundle["case_id"]),
                "vars": {"prompt": sample["input"]},
                "metadata": sample["metadata"],
            }
        )
    return {
        "description": "Evidence-backed LLM red-team regression cases",
        "prompts": ["{{prompt}}"],
        "providers": providers or [],
        "tests": tests,
    }


def record_attempt(
    store: MemoryStore,
    case_id: str,
    mechanism: str,
    input_text: str,
    outcome: str,
    **kwargs: Any,
) -> dict[str, Any]:
    return store.add_attempt(
        Attempt(
            case_id=case_id,
            mechanism=mechanism,
            input_text=input_text,
            outcome=outcome,
            first_refusal=bool(kwargs.get("first_refusal", False)),
            score=kwargs.get("score"),
            notes=str(kwargs.get("notes", "")),
        )
    ).to_dict()
