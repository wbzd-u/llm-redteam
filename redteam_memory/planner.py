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


def _comparison_variables(card: dict[str, Any]) -> dict[str, str]:
    """Choose a safe, mechanism-specific comparison axis for an experiment design."""
    text = f"{card.get('name', '')} {card.get('category', '')} {' '.join(card.get('tags', []))}".casefold()
    if any(term in text for term in ("multi-turn", "会话", "身份", "state", "memory")):
        return {"comparison": "clean / persisted / reset session", "controlled_variable": "session state", "record": "conversation id, turn number, reset state"}
    if any(term in text for term in ("language", "translation", "跨语言", "多语言")):
        return {"comparison": "semantic-equivalent language variants", "controlled_variable": "language", "record": "language, translation provenance, semantic review"}
    if any(term in text for term in ("document", "rag", "检索", "carrier", "载体", "context")):
        return {"comparison": "trusted structured data / untrusted external context", "controlled_variable": "content provenance", "record": "carrier, source label, retrieval or parsing path"}
    if any(term in text for term in ("tool", "schema", "regex", "validator", "评分", "语义")):
        return {"comparison": "format-valid / meaning-valid control", "controlled_variable": "validator binding", "record": "parser result, tool state, external success criterion"}
    return {"comparison": "clean baseline / one selected condition", "controlled_variable": "single mechanism variable", "record": "target version, session state, observable result"}


def _historical_support(store: MemoryStore, mechanism_id: str, current_case_id: str) -> dict[str, Any]:
    links = [link for link in store.list_mechanism_case_links(mechanism_id=mechanism_id) if link["case_id"] != current_case_id]
    samples: list[dict[str, str]] = []
    for link in links[:3]:
        bundle = store.get_case(link["case_id"])
        if bundle is not None:
            samples.append({"case_id": bundle["case_id"], "title": bundle["title"], "relation": link["relation"], "status": bundle["status"]})
    counts: dict[str, int] = {}
    for link in links:
        counts[link["relation"]] = counts.get(link["relation"], 0) + 1
    return {"relation_counts": counts, "samples": samples}


def build_hypothesis_matrix(store: MemoryStore, case_id: str, *, limit: int = 3) -> dict[str, Any]:
    """Create multiple distinct, traceable research hypotheses for a Case.

    This is a deterministic research aid: cards, match reasons and historical
    links are surfaced verbatim, while each proposed experiment changes one
    controlled variable and includes a non-escalating stop condition.
    """
    bundle = store.get_case(case_id)
    if bundle is None:
        raise KeyError(f"unknown case: {case_id}")
    recommendations = recommend_mechanisms(store, case_id, limit=limit)
    hypotheses: list[dict[str, Any]] = []
    for index, recommendation in enumerate(recommendations):
        card = recommendation["mechanism"]
        support = _historical_support(store, card["mechanism_id"], case_id)
        reasons = recommendation["reasons"]
        basis_parts = [
            f"当前任务匹配：{', '.join(reason['kind'] for reason in reasons) or 'mechanism recommendation'}",
            f"历史关系：{support['relation_counts'] or '暂无直接关联'}",
        ]
        hypotheses.append({
            "id": f"h{index + 1}",
            "mechanism_id": card["mechanism_id"],
            "mechanism": card["name"],
            "statement": f"当前任务值得以“{card['name']}”作为一个可证伪的研究机制进行对照评估。",
            "basis": "；".join(basis_parts),
            "priority": "high" if index == 0 else "medium",
            "positive_signal": card["applicability_signals"][0] if card["applicability_signals"] else "出现与该机制一致的可观察行为变化",
            "negative_signal": card["negative_signals"][0] if card["negative_signals"] else "受控比较下没有可观察行为变化",
            "variables": _comparison_variables(card),
            "preconditions": card["preconditions"],
            "historical_support": support,
            "stop_condition": "完成预定对照后停止；没有外部证据时不得把结果升级为已确认影响。",
            "next_if_negative": recommendations[index + 1]["mechanism"]["name"] if index + 1 < len(recommendations) else "补充基线、判据或目标信息后重新匹配机制",
        })
    if not hypotheses:
        hypotheses.append({
            "id": "h1", "mechanism_id": "baseline", "mechanism": "基础行为基线",
            "statement": "当前信息不足以支持具体机制判断，应先建立可复现的基础行为基线。",
            "basis": "没有充分匹配的历史机制卡。", "priority": "high",
            "positive_signal": "在相同条件下获得稳定、可记录的基础响应",
            "negative_signal": "基础响应无法复现或成功判据不明确",
            "variables": {"comparison": "repeat baseline", "controlled_variable": "none", "record": "target version, session state, observable result"},
            "preconditions": ["明确题目、目标和成功判据"], "historical_support": {"relation_counts": {}, "samples": []},
            "stop_condition": "完成一次基础对照后停止并补全任务事实。", "next_if_negative": "补充任务信息",
        })
    return {"case_id": case_id, "method": "transparent-rule-based-v1", "hypotheses": hypotheses}


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
        "hypothesis_matrix": build_hypothesis_matrix(store, case_id, limit=min(limit, 3)),
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
        if item["approval_required"] is not True:
            raise ValueError("each plan step must require explicit approval")
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
    """Create a conservative multi-hypothesis draft from the research matrix."""
    brief = build_planner_brief(store, case_id)
    matrix = brief["hypothesis_matrix"]["hypotheses"]
    payload = validate_plan_payload({
        "status": "draft",
        "hypotheses": [{key: item[key] for key in REQUIRED_HYPOTHESIS_FIELDS} for item in matrix],
        "steps": [{
            "id": f"s{index + 1}", "hypothesis_id": item["id"],
            "objective": f"为“{item['mechanism']}”运行一次受控比较并记录外部可观察结果。",
            "variables": item["variables"], "expected_signal": item["positive_signal"],
            "stop_condition": item["stop_condition"], "approval_required": True,
        } for index, item in enumerate(matrix)],
        "notes": "确定性多假设草稿；每一步均需人工审核后才能进入执行层。",
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
