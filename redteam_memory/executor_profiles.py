"""Non-secret executor profiles and readiness checks for reviewed Campaigns.

Profiles deliberately contain only labels and execution settings. Request
templates, cookies and headers remain external local files and are never read
or returned by this module.
"""

from __future__ import annotations

from typing import Any

from .store import MemoryStore


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
    pending = [item for item in bundle.get("campaigns", []) if item.get("status") == "pending"]
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
