"""Cross-case research summaries and dependency-free exports."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
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


def mechanism_research_matrix(store: MemoryStore, *, source: str | None = None) -> list[dict[str, Any]]:
    """Return paper-safe mechanism aggregates without exporting raw prompts or responses."""
    rows_by_case = {row["case_id"]: row for row in case_rows(store, source=source)}
    matrix: list[dict[str, Any]] = []
    linked_case_ids: set[str] = set()
    for card in store.list_mechanism_cards():
        links = store.list_mechanism_case_links(mechanism_id=card["mechanism_id"])
        scoped = [link for link in links if link["case_id"] in rows_by_case]
        linked_case_ids.update(link["case_id"] for link in scoped)
        linked_rows = [rows_by_case[link["case_id"]] for link in scoped]
        relation_counts = Counter(link["relation"] for link in scoped)
        outcomes = Counter(outcome for row in linked_rows for outcome in row["attempt_outcomes"])
        matrix.append({
            "mechanism_id": card["mechanism_id"],
            "name": card["name"],
            "category": card["category"],
            "summary": card["summary"],
            "confidence": card["confidence"],
            "tags": card["tags"],
            "case_count": len(linked_rows),
            "confirmed_cases": sum(row["status"] == "confirmed" for row in linked_rows),
            "negative_cases": sum(row["status"] in {"negative", "failed"} for row in linked_rows),
            "attempt_count": sum(row["attempt_count"] for row in linked_rows),
            "verified_evidence_count": sum(row["verified_evidence_count"] for row in linked_rows),
            "relations": dict(sorted(relation_counts.items())),
            "outcomes": dict(sorted(outcomes.items())),
            "applicability_signals": card["applicability_signals"],
            "negative_signals": card["negative_signals"],
            "preconditions": card["preconditions"],
        })

    # Historical records may not be linked to a card yet. Keep this visible as
    # a data-curation gap instead of silently dropping those cases from research.
    unlinked = [row for case_id, row in rows_by_case.items() if case_id not in linked_case_ids]
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unlinked:
        by_label[row["mechanism"] or "未分类"].append(row)
    for label, grouped in sorted(by_label.items()):
        if not grouped:
            continue
        matrix.append({
            "mechanism_id": f"unlinked:{label}",
            "name": label,
            "category": "待映射的历史机制",
            "summary": "该机制来自历史案例字段，尚未关联到结构化机制卡。",
            "confidence": "unclassified",
            "tags": [],
            "case_count": len(grouped),
            "confirmed_cases": sum(row["status"] == "confirmed" for row in grouped),
            "negative_cases": sum(row["status"] in {"negative", "failed"} for row in grouped),
            "attempt_count": sum(row["attempt_count"] for row in grouped),
            "verified_evidence_count": sum(row["verified_evidence_count"] for row in grouped),
            "relations": {},
            "outcomes": dict(sorted(Counter(outcome for row in grouped for outcome in row["attempt_outcomes"]).items())),
            "applicability_signals": [],
            "negative_signals": [],
            "preconditions": [],
        })
    return sorted(matrix, key=lambda item: (-item["case_count"], item["category"], item["name"]))


def paper_packet(store: MemoryStore, *, source: str | None = None) -> dict[str, Any]:
    """Build a transparent, evidence-aware packet for a research manuscript.

    This is deliberately a data-preparation artifact: it names missing
    controls and evidence instead of manufacturing statistical conclusions.
    """
    rows = case_rows(store, source=source)
    summary = research_summary(store, source=source)
    matrix = mechanism_research_matrix(store, source=source)
    total = len(rows)
    populated = {
        "目标模型或系统": sum(row["target"] != "unknown" for row in rows),
        "载体": sum(row["carrier"] != "unknown" for row in rows),
        "语言": sum(row["language"] != "und" for row in rows),
        "机制标签": sum(row["mechanism"] not in {"", "unclassified"} for row in rows),
        "尝试结果": sum(bool(row["attempt_outcomes"]) for row in rows),
        "运行时验证证据": sum(row["verified_evidence_count"] > 0 for row in rows),
    }
    gaps: list[str] = []
    if total == 0:
        gaps.append("尚无案例，不能形成数据集描述或比较结论。")
    if populated["运行时验证证据"] == 0:
        gaps.append("目前没有运行时验证证据；历史通关记录只能作为观察，不应写成可复现实验结论。")
    if populated["尝试结果"] < max(1, total):
        gaps.append("部分案例没有结构化尝试结果；需要补充对照条件、轮次和结果标签。")
    if len({row["target"] for row in rows if row["target"] != "unknown"}) < 2:
        gaps.append("目标覆盖不足，暂不适合声称跨模型或跨系统可迁移性。")
    if len({row["language"] for row in rows if row["language"] != "und"}) < 2:
        gaps.append("语言层级覆盖不足，暂不适合做跨语言对比。")
    if not any(item["case_count"] >= 2 for item in matrix):
        gaps.append("机制组内样本量不足；应优先为每个关键机制补充独立对照和重复实验。")

    data_dictionary = [
        {"field": "case_id", "meaning": "案例的稳定匿名标识", "unit": "字符串"},
        {"field": "mechanism", "meaning": "机制卡或历史机制标签", "unit": "分类变量"},
        {"field": "target", "meaning": "模型、系统或沙箱目标", "unit": "分类变量"},
        {"field": "carrier", "meaning": "文本、文档、工具、RAG 或其他载体", "unit": "分类变量"},
        {"field": "language", "meaning": "输入的语言标签", "unit": "语言代码"},
        {"field": "attempt_outcomes", "meaning": "每次受控尝试的结果标签", "unit": "分类变量"},
        {"field": "verified_evidence_count", "meaning": "经平台、工具或人工核验的证据数", "unit": "计数"},
        {"field": "campaign_turns", "meaning": "受预算约束的已执行轮数", "unit": "轮次"},
    ]
    methods = (
        f"本研究基于本地保存的 {total} 个授权案例开展机制导向分析。每个案例以 Case 为单位，"
        "记录目标、载体、语言、机制标签、尝试、会话轮次与证据；原始输入和响应不进入统计导出。"
        "机制由预先定义的机制卡描述，并通过 confirmed、observed、candidate 或 negative 关系与案例关联。"
        "结果仅在存在可追溯的运行时或平台证据时记为验证，不以模型自述替代外部证据。"
    )
    markdown_lines = [
        "# LLM 红队机制研究数据包", "",
        "## 可直接用于论文方法部分的描述", "", methods, "",
        "## 数据集快照", "",
        f"- 案例数：{total}",
        f"- 结构化尝试数：{summary['totals']['attempts']}",
        f"- 已验证运行时证据案例：{summary['totals']['confirmed_cases']}",
        f"- 已建立机制卡：{sum(1 for item in matrix if not item['mechanism_id'].startswith('unlinked:'))}",
        "", "## 当前不能直接宣称的结论", "",
    ]
    markdown_lines.extend(f"- {gap}" for gap in gaps) if gaps else markdown_lines.append("- 数据完整性满足当前基础描述性分析要求；仍需报告样本选择与外推边界。")
    markdown_lines.extend(["", "## 机制 × 证据概览", "", "| 机制 | 案例 | 历史通关 | 负例 | 已验证证据 |", "| --- | ---: | ---: | ---: | ---: |"])
    markdown_lines.extend(
        f"| {item['name']} | {item['case_count']} | {item['confirmed_cases']} | {item['negative_cases']} | {item['verified_evidence_count']} |"
        for item in matrix
    )
    return {
        "summary": summary,
        "mechanism_matrix": matrix,
        "data_dictionary": data_dictionary,
        "readiness": {
            "total_cases": total,
            "field_coverage": {label: {"filled": value, "total": total, "rate": round(value / total, 4) if total else 0.0} for label, value in populated.items()},
            "gaps": gaps,
        },
        "methods_draft": methods,
        "markdown": "\n".join(markdown_lines) + "\n",
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


def write_paper_packet(store: MemoryStore, path: str | Path, *, source: str | None = None) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(paper_packet(store, source=source)["markdown"], encoding="utf-8")


CHART_METRICS = {
    "cases-by-target": "cases_by_target",
    "cases-by-carrier": "cases_by_carrier",
    "cases-by-language": "cases_by_language",
    "cases-by-stage": "cases_by_stage",
    "attempts-by-outcome": "attempts_by_outcome",
    "campaigns-by-status": "campaigns_by_status",
    "mechanism-links-by-relation": "mechanism_links_by_relation",
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
