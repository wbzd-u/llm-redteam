"""LLM-ready planning primitives with deterministic, reviewable fallbacks.

The module deliberately produces experiment *designs*, not an unbounded stream
of raw inputs. A later provider adapter can submit ``build_planner_brief`` to
an LLM and return the same validated plan schema.
"""

from __future__ import annotations

from typing import Any

from .mechanisms import recommend_mechanisms
from .models import ResearchPlan
from .store import MemoryStore


PLAN_STATUSES = {"draft", "approved", "superseded"}
REQUIRED_HYPOTHESIS_FIELDS = {"id", "statement", "basis", "priority", "positive_signal", "negative_signal"}
REQUIRED_STEP_FIELDS = {"id", "hypothesis_id", "objective", "variables", "expected_signal", "stop_condition", "approval_required"}


def build_planner_brief(store: MemoryStore, case_id: str, *, limit: int = 5) -> dict[str, Any]:
    """Build the minimum traceable context a planner needs for one Case."""
    bundle = store.get_case(case_id)
    if bundle is None:
        raise KeyError(f"unknown case: {case_id}")
    intake = bundle.get("intake") or {}
    return {
        "case": {
            key: bundle.get(key, "")
            for key in ("case_id", "title", "target", "challenge", "mechanism", "carrier", "impact", "status", "tags", "notes")
        },
        "authorization_scope": intake.get("authorization_scope", ""),
        "success_criteria": intake.get("success_criteria", []),
        "constraints": intake.get("constraints", []),
        "existing_attempts": [
            {key: attempt.get(key) for key in ("mechanism", "outcome", "first_refusal", "notes")}
            for attempt in bundle.get("attempts", [])
        ],
        "evidence": [
            {key: evidence.get(key) for key in ("kind", "description", "source", "verified")}
            for evidence in bundle.get("evidence", [])
        ],
        "recommended_mechanisms": recommend_mechanisms(store, case_id, limit=limit),
        "required_output_schema": {
            "status": "draft",
            "hypotheses": [{key: "..." for key in sorted(REQUIRED_HYPOTHESIS_FIELDS)}],
            "steps": [{key: "..." for key in sorted(REQUIRED_STEP_FIELDS)}],
            "notes": "...",
        },
        "planner_rules": [
            "Propose only a small number of distinct, falsifiable experiments.",
            "State the case evidence or mechanism-card evidence for every hypothesis.",
            "Do not claim impact is confirmed without platform, UI, or tool evidence.",
            "Each step must define a stop condition and require approval before target execution.",
        ],
    }


def validate_plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("plan payload must be a JSON object")
    status = str(payload.get("status", "draft"))
    if status not in PLAN_STATUSES:
        raise ValueError(f"plan status must be one of: {', '.join(sorted(PLAN_STATUSES))}")
    hypotheses = payload.get("hypotheses")
    steps = payload.get("steps")
    if not isinstance(hypotheses, list) or not hypotheses:
        raise ValueError("plan requires at least one hypothesis")
    if not isinstance(steps, list) or not steps:
        raise ValueError("plan requires at least one step")
    hypothesis_ids: set[str] = set()
    for item in hypotheses:
        if not isinstance(item, dict) or not REQUIRED_HYPOTHESIS_FIELDS.issubset(item):
            raise ValueError("each hypothesis must contain the required schema fields")
        if not all(isinstance(item[key], str) and item[key].strip() for key in REQUIRED_HYPOTHESIS_FIELDS):
            raise ValueError("hypothesis schema values must be non-empty strings")
        if item["id"] in hypothesis_ids:
            raise ValueError("hypothesis ids must be unique")
        hypothesis_ids.add(item["id"])
    step_ids: set[str] = set()
    for item in steps:
        if not isinstance(item, dict) or not REQUIRED_STEP_FIELDS.issubset(item):
            raise ValueError("each step must contain the required schema fields")
        if not isinstance(item["approval_required"], bool):
            raise ValueError("step approval_required must be boolean")
        if not isinstance(item["variables"], dict):
            raise ValueError("step variables must be an object")
        for key in REQUIRED_STEP_FIELDS - {"approval_required", "variables"}:
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError("step schema values must be non-empty strings")
        if item["id"] in step_ids:
            raise ValueError("step ids must be unique")
        if item["hypothesis_id"] not in hypothesis_ids:
            raise ValueError("each step must refer to a known hypothesis_id")
        step_ids.add(item["id"])
    notes = payload.get("notes", "")
    if not isinstance(notes, str):
        raise ValueError("plan notes must be a string")
    return {"status": status, "hypotheses": hypotheses, "steps": steps, "notes": notes}


def deterministic_draft(store: MemoryStore, case_id: str) -> ResearchPlan:
    """Create a conservative draft from the strongest retrieved mechanism card."""
    brief = build_planner_brief(store, case_id)
    recommendations = brief["recommended_mechanisms"]
    if recommendations:
        top = recommendations[0]
        card = top["mechanism"]
        basis = "; ".join(
            reason["kind"] for reason in top["reasons"]
        ) or "mechanism recommendation"
        mechanism_name = card["name"]
        positive = card["applicability_signals"][0] if card["applicability_signals"] else "observable behavior consistent with the mechanism"
        negative = card["negative_signals"][0] if card["negative_signals"] else "no observable change under the controlled comparison"
    else:
        mechanism_name = "baseline behavior"
        basis = "no sufficiently matched historical mechanism card"
        positive = "a stable baseline response is recorded"
        negative = "the baseline cannot be reproduced"
    payload = validate_plan_payload({
        "status": "draft",
        "hypotheses": [{
            "id": "h1",
            "statement": f"The Case is worth evaluating through the '{mechanism_name}' mechanism.",
            "basis": basis,
            "priority": "high",
            "positive_signal": positive,
            "negative_signal": negative,
        }],
        "steps": [{
            "id": "s1",
            "hypothesis_id": "h1",
            "objective": "Run one controlled baseline/comparison and record the observable result.",
            "variables": {"mechanism": mechanism_name, "comparison": "clean versus selected condition"},
            "expected_signal": positive,
            "stop_condition": "Stop after the planned comparison; do not infer confirmed impact without external evidence.",
            "approval_required": True,
        }],
        "notes": "Deterministic draft; review and approve before target execution.",
    })
    return ResearchPlan(
        case_id=case_id,
        planner="deterministic",
        status=payload["status"],
        hypotheses=payload["hypotheses"],
        steps=payload["steps"],
        context=brief,
        notes=payload["notes"],
    )
