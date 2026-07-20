from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class NextAction:
    action: str
    mechanism: str
    rationale: str
    confidence: str = "medium"
    requires_human_review: bool = False
    stage: str = "baseline"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _evidence_confirms_impact(item: dict[str, Any]) -> bool:
    if not item.get("verified") or item.get("kind") not in {"runtime", "backend", "ui", "tool"}:
        return False
    metadata = item.get("metadata")
    if isinstance(metadata, dict) and "confirms_impact" in metadata:
        return metadata.get("confirms_impact") is True
    return True


def derive_stage(bundle: dict[str, Any]) -> str:
    """Derive a conservative session stage from externally observable records."""
    evidence = bundle.get("evidence", [])
    attempts = bundle.get("attempts", [])
    if any(_evidence_confirms_impact(item) for item in evidence):
        return "confirmed"
    if evidence:
        return "verification"
    if not attempts:
        return "baseline"
    latest = attempts[-1]
    mechanism = latest.get("mechanism")
    same_mechanism = [a for a in attempts if a.get("mechanism") == mechanism]
    if len(same_mechanism) >= 2 and all(
        a.get("outcome") in {"refused", "no_change", "unclear", "unknown"}
        for a in same_mechanism[-2:]
    ):
        return "halted"
    if latest.get("first_refusal"):
        return "first_refusal"
    return "probing"


def recommend_next(bundle: dict[str, Any]) -> NextAction:
    """Choose a conservative next experiment from observed evidence.

    This is deliberately a decision aid, not a payload generator. It favors
    verification and controlled resets over escalating a story with no state
    change.
    """
    evidence = bundle.get("evidence", [])
    attempts = bundle.get("attempts", [])
    stage = derive_stage(bundle)
    verified = [item for item in evidence if item.get("verified")]
    if any(_evidence_confirms_impact(item) for item in evidence):
        return NextAction(
            action="stop_and_record",
            mechanism=bundle.get("mechanism", ""),
            rationale="Verified runtime evidence exists; preserve the shortest chain before any further probing.",
            confidence="high",
            requires_human_review=True,
            stage=stage,
        )

    if evidence:
        rationale = (
            "Verified observations exist, but none explicitly confirm the claimed impact; "
            "review the evaluator result before classifying the case."
            if verified
            else "Only unverified or narrative evidence is present; check the tool, scorer, UI, or backend state."
        )
        return NextAction(
            action="verify_evidence",
            mechanism=bundle.get("mechanism", ""),
            rationale=rationale,
            confidence="high",
            requires_human_review=True,
            stage=stage,
        )

    if not attempts:
        return NextAction(
            action="run_clean_baseline",
            mechanism="baseline",
            rationale="No attempt is recorded; establish a clean-session baseline before changing variables.",
            confidence="high",
            stage=stage,
        )

    latest = attempts[-1]
    mechanism = str(latest.get("mechanism") or bundle.get("mechanism", ""))
    same_mechanism = [a for a in attempts if a.get("mechanism") == mechanism]
    no_change = {"refused", "no_change", "unclear", "unknown"}
    if len(same_mechanism) >= 2 and all(a.get("outcome") in no_change for a in same_mechanism[-2:]):
        return NextAction(
            action="switch_mechanism",
            mechanism=mechanism,
            rationale="The same mechanism produced no state change twice; switch mechanism or carrier instead of repeating it.",
            confidence="high",
            stage=stage,
        )

    if latest.get("first_refusal"):
        return NextAction(
            action="controlled_variant",
            mechanism=mechanism,
            rationale="A first refusal was observed; change one contextual variable in a clean session and record the transition.",
            confidence="medium",
            stage=stage,
        )

    return NextAction(
        action="observe_and_log",
        mechanism=mechanism,
        rationale="The latest attempt is not yet conclusive; capture the raw response and externally observable effect.",
        confidence="medium",
        stage=stage,
    )


def minimize_bundle(bundle: dict[str, Any], max_chars: int = 240) -> dict[str, Any]:
    """Return an audit-friendly compact view with sensitive values redacted.

    The full bundle remains in the local SQLite store. This representation is
    intended for reports, model context, or handoff between agents.
    """
    def excerpt(value: str) -> str:
        value = value or ""
        return value if len(value) <= max_chars else value[:max_chars] + "..."

    def digest(value: str) -> str:
        return sha256((value or "").encode("utf-8")).hexdigest()[:16]

    compact_turns = []
    for turn in bundle.get("turns", []):
        content = str(turn.get("content", ""))
        compact_turns.append({
            "turn_id": turn.get("turn_id"),
            "role": turn.get("role"),
            "provenance": turn.get("provenance"),
            "refusal": bool(turn.get("refusal")),
            "observed_effect": excerpt(str(turn.get("observed_effect", ""))),
            "content_sha256_16": digest(content),
            "content_excerpt": excerpt(content),
        })

    compact_evidence = []
    for item in bundle.get("evidence", []):
        value = str(item.get("value", ""))
        compact_evidence.append({
            "evidence_id": item.get("evidence_id"),
            "turn_id": item.get("turn_id"),
            "kind": item.get("kind"),
            "description": excerpt(str(item.get("description", ""))),
            "source": item.get("source"),
            "verified": bool(item.get("verified")),
            "confirms_impact": _evidence_confirms_impact(item),
            "value_sha256_16": digest(value),
            "value_redacted": bool(value),
        })

    return {
        "case_id": bundle.get("case_id"),
        "title": bundle.get("title"),
        "target": bundle.get("target"),
        "challenge": bundle.get("challenge"),
        "mechanism": bundle.get("mechanism"),
        "carrier": bundle.get("carrier"),
        "impact": bundle.get("impact"),
        "status": bundle.get("status"),
        "tags": bundle.get("tags", []),
        "attempts": [
            {
                "attempt_id": a.get("attempt_id"),
                "mechanism": a.get("mechanism"),
                "outcome": a.get("outcome"),
                "first_refusal": bool(a.get("first_refusal")),
                "score": a.get("score"),
                "input_sha256_16": digest(str(a.get("input_text", ""))),
            }
            for a in bundle.get("attempts", [])
        ],
        "turns": compact_turns,
        "evidence": compact_evidence,
        "next_action": recommend_next(bundle).to_dict(),
    }
