"""Cross-case research summaries and dependency-free exports."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .state import derive_stage
from .store import MemoryStore


def _language(tags: list[str]) -> str:
    for tag in tags:
        if tag.lower().startswith("lang:"):
            value = tag.split(":", 1)[1].strip()
            if value:
                return value
    return "und"


def _source(tags: list[str]) -> str:
    for tag in tags:
        if tag.lower().startswith("source:"):
            return tag.split(":", 1)[1].strip() or "unknown"
    if any("ipi" in tag.lower() for tag in tags):
        return "ipi-arena"
    if any("jailbreak" in tag.lower() for tag in tags):
        return "jailbreaker-ce"
    return "unknown"


def case_rows(store: MemoryStore, *, source: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in store.list_cases():
        bundle = store.get_case(summary["case_id"])
        if bundle is None:
            continue
        attempts = bundle.get("attempts", [])
        campaigns = bundle.get("campaigns", [])
        row = {
            "case_id": bundle["case_id"],
            "title": bundle["title"],
            "target": bundle["target"] or "unknown",
            "carrier": bundle["carrier"] or "unknown",
            "mechanism": bundle["mechanism"] or "unclassified",
            "status": bundle["status"],
            "stage": derive_stage(bundle),
            "language": _language(bundle.get("tags", [])),
            "source": _source(bundle.get("tags", [])),
            "tags": bundle.get("tags", []),
            "attempt_count": len(attempts),
            "turn_count": len(bundle.get("turns", [])),
            "evidence_count": len(bundle.get("evidence", [])),
            "verified_evidence_count": sum(bool(item.get("verified")) for item in bundle.get("evidence", [])),
            "plan_count": len(bundle.get("plans", [])),
            "campaign_count": len(campaigns),
            "campaign_turns": sum(int(item.get("executed_turns", 0)) for item in campaigns),
            "observed_cost": round(sum(float(item.get("observed_cost", 0) or 0) for item in campaigns), 6),
            "confirmed": derive_stage(bundle) == "confirmed",
            "reproduced": sum(item.get("status") == "confirmed" for item in campaigns) >= 2,
            "attempt_outcomes": [str(item.get("outcome", "unknown")) for item in attempts],
            "campaign_statuses": [str(item.get("status", "pending")) for item in campaigns],
            "mechanism_relations": [str(item.get("relation", "candidate")) for item in bundle.get("mechanism_links", [])],
        }
        if source is None or row["source"] == source:
            rows.append(row)
    return rows


def _counts(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def research_summary(store: MemoryStore, *, source: str | None = None) -> dict[str, Any]:
    rows = case_rows(store, source=source)
    attempt_outcomes = [outcome for row in rows for outcome in row["attempt_outcomes"]]
    campaign_statuses = [status for row in rows for status in row["campaign_statuses"]]
    mechanism_relations = [relation for row in rows for relation in row["mechanism_relations"]]
    confirmed = sum(row["confirmed"] for row in rows)
    reproducible = sum(row["reproduced"] for row in rows)
    historical_confirmed = sum(row["source"] == "user-kb" and row["status"] == "confirmed" for row in rows)
    user_kb_cases = sum(row["source"] == "user-kb" for row in rows)
    total_attempts = sum(row["attempt_count"] for row in rows)
    total_campaigns = sum(row["campaign_count"] for row in rows)
    return {
        "totals": {
            "cases": len(rows),
            "attempts": total_attempts,
            "campaigns": total_campaigns,
            "confirmed_cases": confirmed,
            "confirmed_case_rate": round(confirmed / len(rows), 4) if rows else 0.0,
            "historical_confirmed_cases": historical_confirmed,
            "historical_confirmed_rate": round(historical_confirmed / user_kb_cases, 4) if user_kb_cases else 0.0,
            "user_kb_cases": user_kb_cases,
            "reproduced_cases": reproducible,
            "reproduced_case_rate": round(reproducible / confirmed, 4) if confirmed else 0.0,
            "observed_cost": round(sum(row["observed_cost"] for row in rows), 6),
        },
        "cases_by_target": _counts([row["target"] for row in rows]),
        "cases_by_carrier": _counts([row["carrier"] for row in rows]),
        "cases_by_language": _counts([row["language"] for row in rows]),
        "cases_by_source": _counts([row["source"] for row in rows]),
        "cases_by_stage": _counts([row["stage"] for row in rows]),
        "attempts_by_outcome": _counts(attempt_outcomes),
        "campaigns_by_status": _counts(campaign_statuses),
        "mechanism_links_by_relation": _counts(mechanism_relations),
    }


def write_case_csv(store: MemoryStore, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = case_rows(store)
    fields = [
        "case_id", "title", "target", "carrier", "mechanism", "status", "stage", "language",
        "tags", "attempt_count", "turn_count", "evidence_count", "verified_evidence_count",
        "plan_count", "campaign_count", "campaign_turns", "observed_cost", "confirmed", "reproduced",
        "attempt_outcomes", "campaign_statuses", "mechanism_relations",
    ]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(row[key], ensure_ascii=False) if isinstance(row[key], list) else row[key]
                for key in fields
            })


def write_summary_json(store: MemoryStore, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(research_summary(store), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


CHART_METRICS = {
    "cases-by-target": "cases_by_target",
    "cases-by-carrier": "cases_by_carrier",
    "cases-by-language": "cases_by_language",
    "cases-by-stage": "cases_by_stage",
    "attempts-by-outcome": "attempts_by_outcome",
    "campaigns-by-status": "campaigns_by_status",
}


def write_summary_svg(store: MemoryStore, *, metric: str, path: str | Path) -> None:
    if metric not in CHART_METRICS:
        raise ValueError(f"unknown chart metric: {metric}")
    series = research_summary(store)[CHART_METRICS[metric]]
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    items = list(series.items()) or [("no data", 0)]
    width, margin_left, margin_right, row_height = 900, 230, 80, 44
    height = max(150, 80 + len(items) * row_height)
    max_value = max(series.values(), default=1) or 1
    bars: list[str] = []
    for index, (label, value) in enumerate(items):
        y = 45 + index * row_height
        bar_width = round((width - margin_left - margin_right) * value / max_value, 2)
        bars.append(
            f'<text x="{margin_left - 12}" y="{y + 17}" text-anchor="end">{html.escape(str(label))}</text>'
            f'<rect x="{margin_left}" y="{y}" width="{bar_width}" height="24" fill="#2563eb" rx="3"/>'
            f'<text x="{margin_left + bar_width + 8}" y="{y + 17}">{value}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<style>text{font-family:Segoe UI,Arial,sans-serif;font-size:14px;fill:#1f2937}.title{font-size:20px;font-weight:600}</style>'
        f'<text class="title" x="24" y="28">{html.escape(metric)}</text>'
        + "".join(bars)
        + "</svg>"
    )
    destination.write_text(svg, encoding="utf-8")
