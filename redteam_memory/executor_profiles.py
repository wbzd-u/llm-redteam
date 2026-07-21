"""Non-secret executor profiles and readiness checks for reviewed Campaigns.

Profiles deliberately contain only labels and execution settings. Request
templates, cookies and headers remain external local files and are never read
or returned by this module.
"""

from __future__ import annotations

from typing import Any

from .store import MemoryStore


PYRIT_STRATEGY_CATALOG = [
    {"id": "prompt_sending", "name": "单轮受控发送", "stage": "现在可用", "kind": "single_turn", "requires": ["已审核输入", "HTTP 模板"], "purpose": "建立基线、比较 Converter 或 Scorer 结果。"},
    {"id": "converter_pipeline", "name": "Converter 管线", "stage": "下一步接入", "kind": "transformation", "requires": ["机制选择", "转换链审核"], "purpose": "将同一受控输入按不同编码、格式或载体条件进行可追溯比较。"},
    {"id": "multi_prompt", "name": "固定多轮", "stage": "下一步接入", "kind": "multi_turn", "requires": ["会话状态", "轮次预算"], "purpose": "复现和比较人工审核的多步对话序列。"},
    {"id": "red_teaming", "name": "自适应 Red Teaming", "stage": "需配置", "kind": "adaptive", "requires": ["目标模型", "attacker 模型", "过程 Scorer"], "purpose": "由 attacker model 根据目标响应提出下一步候选。"},
    {"id": "crescendo", "name": "Crescendo", "stage": "需配置", "kind": "adaptive", "requires": ["目标模型", "attacker 模型", "过程 Scorer", "回退预算"], "purpose": "在受控轮数内逐步推进并根据反馈调整。"},
    {"id": "pair_tap", "name": "PAIR / TAP 搜索", "stage": "高级", "kind": "tree_search", "requires": ["目标模型", "attacker 模型", "Scorer", "树宽/深预算"], "purpose": "对候选分支进行评分、剪枝和预算控制。"},
]


def normalize_pyrit_profile(payload: dict[str, Any]) -> dict[str, Any]:
    encoding = str(payload.get("prompt_encoding", "raw")).strip() or "raw"
    if encoding not in {"raw", "json", "url"}:
        raise ValueError("prompt_encoding must be raw, json, or url")
    timeout = float(payload.get("timeout", 30))
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    return {
        "profile_name": str(payload.get("profile_name", "PyRIT HTTP profile")).strip() or "PyRIT HTTP profile",
        "request_reference": str(payload.get("request_reference", "")).strip(),
        "placeholder": str(payload.get("placeholder", "{PROMPT}")).strip() or "{PROMPT}",
        "response_key": str(payload.get("response_key", "")).strip(),
        "prompt_encoding": encoding,
        "model_name": str(payload.get("model_name", "")).strip(),
        "timeout": timeout,
        "captured_request_reviewed": bool(payload.get("captured_request_reviewed", False)),
        "credentials_managed_externally": bool(payload.get("credentials_managed_externally", True)),
    }


def pyrit_readiness(store: MemoryStore, case_id: str) -> dict[str, Any]:
    bundle = store.get_case(case_id)
    if bundle is None:
        raise KeyError(f"unknown case: {case_id}")
    profile = dict((bundle.get("intake") or {}).get("target_config", {}).get("pyrit_profile", {}))
    approved_plan = next((item for item in bundle.get("plans", []) if item.get("status") == "approved"), None)
    pending = [item for item in bundle.get("campaigns", []) if item.get("status") == "pending" and item.get("target_kind") == "pyrit-http"]
    checks = [
        {"id": "approved_plan", "label": "存在已批准的实验计划", "ready": approved_plan is not None},
        {"id": "reviewed_campaign", "label": "存在包含人工审核输入的待执行 Campaign", "ready": bool(pending)},
        {"id": "request_reference", "label": "已记录本地请求模板的非敏感引用", "ready": bool(profile.get("request_reference"))},
        {"id": "template_review", "label": "已人工确认模板包含占位符", "ready": bool(profile.get("captured_request_reviewed"))},
        {"id": "credentials_external", "label": "凭据保留在外部本地文件中", "ready": bool(profile.get("credentials_managed_externally"))},
    ]
    return {
        "profile": profile,
        "ready": all(item["ready"] for item in checks),
        "checks": checks,
        "approved_plan_id": approved_plan.get("plan_id") if approved_plan else None,
        "pending_campaign_count": len(pending),
        "handoff": {
            "runner": "PyRITHTTPTarget",
            "request_template": "<local-captured-request-file>",
            "headers": "<external-local-headers-file>",
            "placeholder": profile.get("placeholder", "{PROMPT}"),
            "response_key": profile.get("response_key", ""),
            "network_execution": "disabled until an explicit local CLI --execute invocation",
        },
    }


def pyrit_workbench_summary(store: MemoryStore) -> dict[str, Any]:
    """Provide a dashboard-safe view of PyRIT capability and task readiness."""
    tasks = []
    for row in store.list_cases():
        bundle = store.get_case(row["case_id"])
        if bundle is None:
            continue
        readiness = pyrit_readiness(store, bundle["case_id"])
        profile = readiness["profile"]
        tasks.append({
            "case_id": bundle["case_id"],
            "title": bundle["title"],
            "target": bundle.get("target", ""),
            "ready": readiness["ready"],
            "pending_campaign_count": readiness["pending_campaign_count"],
            "profile_configured": bool(profile),
            "missing_checks": [item["label"] for item in readiness["checks"] if not item["ready"]],
        })
    return {
        "catalog": PYRIT_STRATEGY_CATALOG,
        "tasks": sorted(tasks, key=lambda item: (not item["ready"], item["title"])),
        "totals": {
            "tasks": len(tasks),
            "profile_configured": sum(item["profile_configured"] for item in tasks),
            "ready": sum(item["ready"] for item in tasks),
            "pending_pyrit_campaigns": sum(item["pending_campaign_count"] for item in tasks),
        },
    }
