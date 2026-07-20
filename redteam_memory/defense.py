"""Defense-aware, evidence-first evaluation helpers.

This module analyzes manually observed allow/block decisions.  It does not
generate evasions, alter inputs, or infer proprietary defensive internals.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


DISPOSITIONS = {"allow", "block", "unknown"}


def validate_disposition(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in DISPOSITIONS:
        raise ValueError("disposition must be one of: allow, block, unknown")
    return normalized


def observation_verdict(observation: dict[str, Any]) -> str:
    """Classify a detector decision against a reviewer-supplied expectation."""
    expected = validate_disposition(str(observation.get("expected_disposition", "unknown")))
    observed = validate_disposition(str(observation.get("observed_disposition", "unknown")))
    if "unknown" in {expected, observed}:
        return "needs_review"
    if expected == observed:
        return "aligned"
    if expected == "allow" and observed == "block":
        return "over_block"
    return "under_block"


def coverage_matrix(observations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate coverage by profile, language, carrier and expected outcome."""
    rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in observations:
        key = (
            str(item.get("profile_id", "")),
            str(item.get("language", "und")),
            str(item.get("carrier", "text")),
            validate_disposition(str(item.get("expected_disposition", "unknown"))),
        )
        row = rows.setdefault(key, {
            "profile_id": key[0], "language": key[1], "carrier": key[2],
            "expected_disposition": key[3], "total": 0, "aligned": 0,
            "over_block": 0, "under_block": 0, "needs_review": 0,
            "verified": 0, "latency_samples": [],
        })
        verdict = observation_verdict(item)
        row["total"] += 1
        row[verdict] += 1
        if item.get("verified"):
            row["verified"] += 1
        latency = item.get("latency_ms")
        if isinstance(latency, (int, float)):
            row["latency_samples"].append(float(latency))

    result: list[dict[str, Any]] = []
    for row in rows.values():
        latencies = row.pop("latency_samples")
        row["latency_avg_ms"] = round(sum(latencies) / len(latencies), 2) if latencies else None
        result.append(row)
    return sorted(result, key=lambda item: (
        item["profile_id"], item["language"], item["carrier"], item["expected_disposition"]
    ))


def regression_gate(
    baseline: Iterable[dict[str, Any]], candidate: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Compare two runs without treating any result as a confirmed vulnerability."""
    baseline_by_key = {
        (str(item.get("case_id", "")), str(item.get("profile_id", ""))): item
        for item in baseline
    }
    candidate_by_key = {
        (str(item.get("case_id", "")), str(item.get("profile_id", ""))): item
        for item in candidate
    }
    changes: list[dict[str, Any]] = []
    for key in sorted(set(baseline_by_key) | set(candidate_by_key)):
        before = baseline_by_key.get(key)
        after = candidate_by_key.get(key)
        if before is None or after is None:
            changes.append({
                "case_id": key[0], "profile_id": key[1], "classification": "coverage_changed",
                "baseline": before.get("observed_disposition") if before else None,
                "candidate": after.get("observed_disposition") if after else None,
            })
            continue
        old = validate_disposition(str(before.get("observed_disposition", "unknown")))
        new = validate_disposition(str(after.get("observed_disposition", "unknown")))
        expected = validate_disposition(str(after.get("expected_disposition", before.get("expected_disposition", "unknown"))))
        if old == new:
            continue
        if expected == "block" and old == "block" and new == "allow":
            classification = "critical_under_block_regression"
        elif expected == "allow" and old == "allow" and new == "block":
            classification = "over_block_regression"
        else:
            classification = "behavior_changed"
        changes.append({
            "case_id": key[0], "profile_id": key[1], "classification": classification,
            "expected_disposition": expected, "baseline": old, "candidate": new,
        })
    critical = [item for item in changes if item["classification"] == "critical_under_block_regression"]
    return {
        "pass": not critical,
        "requires_human_review": bool(changes),
        "critical_regressions": len(critical),
        "changes": changes,
    }
