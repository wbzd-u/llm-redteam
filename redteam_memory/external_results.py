"""Import normalized results from Inspect AI, Promptfoo, or manual evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Attempt, Evidence, Turn
from .store import MemoryStore


RESULT_SOURCES = {"inspect", "promptfoo", "manual"}


def load_result_package(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("result package must be a list or an object with a results list")
    if not all(isinstance(item, dict) for item in records):
        raise ValueError("each result must be an object")
    return [dict(item) for item in records]


def import_campaign_results(
    store: MemoryStore,
    *,
    campaign_id: str,
    source: str,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist externally evaluated Campaign results without inventing a judge.

    Each result requires ``step_id`` and may contain outcome, response,
    refusal, observed_effect and an optional externally verified evidence item.
    """
    if source not in RESULT_SOURCES:
        raise ValueError(f"source must be one of: {', '.join(sorted(RESULT_SOURCES))}")
    campaign = store.get_campaign(campaign_id)
    if campaign is None:
        raise KeyError(f"unknown campaign: {campaign_id}")
    plan = store.get_research_plan(str(campaign["plan_id"]))
    if plan is None:
        raise KeyError(f"campaign plan is missing: {campaign_id}")
    reviewed = {item["step_id"]: item for item in store.list_campaign_inputs(campaign_id)}
    steps = {str(item["id"]): item for item in plan["steps"]}
    recorded: list[dict[str, str]] = []
    for item in results:
        step_id = str(item.get("step_id", "")).strip()
        if step_id not in reviewed or step_id not in steps:
            raise ValueError(f"unknown reviewed step_id: {step_id or '<empty>'}")
        step = steps[step_id]
        outcome = str(item.get("outcome", "unknown")).strip() or "unknown"
        response = str(item.get("response", "")).strip()
        refusal = bool(item.get("refusal", False))
        observed_effect = str(item.get("observed_effect", "")).strip()
        response_turn = store.add_turn(Turn(
            case_id=str(campaign["case_id"]), role="assistant", content=response,
            provenance=f"{source}-import", observed_effect=observed_effect, refusal=refusal,
            metadata={"campaign_id": campaign_id, "step_id": step_id, "external_source": source},
        ))
        mechanism = str(step.get("variables", {}).get("mechanism") or f"plan:{step_id}")
        attempt = store.add_attempt(Attempt(
            case_id=str(campaign["case_id"]), mechanism=mechanism,
            input_text=str(reviewed[step_id]["input_text"]), outcome=outcome,
            first_refusal=refusal, notes=f"campaign={campaign_id}; source={source}; {observed_effect}",
        ))
        evidence_description = str(item.get("evidence_description", "")).strip()
        if evidence_description:
            verified = bool(item.get("evidence_verified", False))
            confirms = bool(item.get("confirms_impact", False))
            store.add_evidence(Evidence(
                case_id=str(campaign["case_id"]), turn_id=response_turn.turn_id,
                kind=str(item.get("evidence_kind", "external")).strip() or "external",
                description=evidence_description, source=f"{source}-import", verified=verified,
                metadata={"campaign_id": campaign_id, "step_id": step_id, "confirms_impact": confirms},
            ))
        recorded.append({"step_id": step_id, "attempt_id": attempt.attempt_id, "response_turn_id": response_turn.turn_id})
    return {"campaign_id": campaign_id, "source": source, "recorded": recorded}
