"""Portable, evidence-linked exports for case review and simple research analysis."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def case_markdown(bundle: dict[str, Any]) -> str:
    intake = bundle.get("intake") or {}
    lines = [f"# {bundle['title']}", "", "## Case", ""]
    for label, key in (("Case ID", "case_id"), ("Target", "target"), ("Status", "status"), ("Carrier", "carrier"), ("Impact", "impact")):
        lines.append(f"- {label}: {bundle.get(key, '')}")
    lines.extend(["", "## Challenge", "", bundle.get("challenge", "") or "(not recorded)", "", "## Authorization and success criteria", ""])
    lines.append(f"- Scope: {intake.get('authorization_scope', '') or '(not recorded)'}")
    for item in intake.get("success_criteria", []):
        lines.append(f"- Success criterion: {item}")
    for item in intake.get("constraints", []):
        lines.append(f"- Constraint: {item}")
    lines.extend(["", "## Mechanism links", ""])
    for link in bundle.get("mechanism_links", []):
        lines.append(f"- `{link['mechanism_id']}` — {link['relation']}: {link['notes']}")
    if not bundle.get("mechanism_links"):
        lines.append("- None")
    lines.extend(["", "## Attempts", ""])
    for attempt in bundle.get("attempts", []):
        lines.append(f"- {attempt['mechanism']} → {attempt['outcome']} (first_refusal={attempt['first_refusal']})")
    if not bundle.get("attempts"):
        lines.append("- None")
    lines.extend(["", "## Evidence", ""])
    for evidence in bundle.get("evidence", []):
        verified = "verified" if evidence["verified"] else "unverified"
        lines.append(f"- [{verified}] {evidence['kind']}: {evidence['description']} ({evidence['source']})")
    if not bundle.get("evidence"):
        lines.append("- None")
    lines.extend(["", "## Plans", ""])
    for plan in bundle.get("plans", []):
        lines.append(f"- `{plan['plan_id']}` — {plan['planner']} / {plan['status']} / {len(plan['steps'])} step(s)")
    if not bundle.get("plans"):
        lines.append("- None")
    lines.extend(["", "## Campaigns", ""])
    for campaign in bundle.get("campaigns", []):
        lines.append(
            f"- `{campaign['campaign_id']}` — {campaign['target_kind']} / {campaign['status']} / "
            f"{campaign['executed_turns']} turn(s): {campaign['stop_reason']}"
        )
    if not bundle.get("campaigns"):
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_attempt_csv(bundle: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = ["case_id", "title", "target", "carrier", "mechanism", "outcome", "first_refusal", "score", "notes", "created_at"]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for attempt in bundle.get("attempts", []):
            writer.writerow({
                "case_id": bundle["case_id"], "title": bundle["title"], "target": bundle["target"],
                "carrier": bundle["carrier"], **{field: attempt.get(field, "") for field in fields[4:]},
            })
