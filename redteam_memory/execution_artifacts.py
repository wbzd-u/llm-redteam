"""Compile approved research plans into reviewable executor-neutral artifacts.

The compiler intentionally leaves every target input blank. It provides a
shared contract for PyRIT, Inspect AI, Promptfoo and replay work, but does not
turn a research hypothesis into an unreviewed payload or make a network call.
"""

from __future__ import annotations

from typing import Any

from .store import MemoryStore


def compile_execution_artifacts(store: MemoryStore, plan_id: str) -> dict[str, Any]:
    plan = store.get_research_plan(plan_id)
    if plan is None:
        raise KeyError(f"unknown plan: {plan_id}")
    bundle = store.get_case(plan["case_id"])
    if bundle is None:
        raise KeyError(f"unknown Case for plan: {plan_id}")
    steps = [
        {
            "step_id": str(step["id"]),
            "hypothesis_id": str(step["hypothesis_id"]),
            "objective": str(step["objective"]),
            "variables": dict(step.get("variables", {})),
            "expected_signal": str(step["expected_signal"]),
            "stop_condition": str(step["stop_condition"]),
            "approval_required": bool(step.get("approval_required", True)),
            "input": None,
            "input_status": "human_review_required",
        }
        for step in plan["steps"]
    ]
    metadata = {
        "case_id": bundle["case_id"],
        "title": bundle["title"],
        "target": bundle.get("target", ""),
        "carrier": bundle.get("carrier", ""),
        "authorization_scope": (bundle.get("intake") or {}).get("authorization_scope", ""),
        "success_criteria": (bundle.get("intake") or {}).get("success_criteria", []),
        "plan_id": plan_id,
        "plan_status": plan["status"],
    }
    return {
        "metadata": metadata,
        "ready_for_campaign": plan["status"] == "approved",
        "blocking_reason": "" if plan["status"] == "approved" else "计划必须先由人工审核并批准。",
        "steps": steps,
        "replay": {
            "target_kind": "replay",
            "inputs": [{"step_id": step["step_id"], "input": None} for step in steps],
            "note": "为每个已批准步骤提供审核后的输入后，才可用于离线重放。",
        },
        "pyrit": {
            "adapter": "PyRITHTTPTarget",
            "required_local_configuration": ["captured request stored locally", "{PROMPT} placeholder", "response extraction policy"],
            "steps": steps,
        },
        "inspect": {
            "task_metadata": metadata,
            "samples": [{"id": step["step_id"], "input": None, "metadata": {"objective": step["objective"], "variables": step["variables"]}} for step in steps],
            "note": "输入为空时不可执行 Inspect；先在任务工作台审核并记录实际测试输入。",
        },
        "promptfoo": {
            "description": f"Reviewed regression contract: {bundle['title']}",
            "prompts": ["{{prompt}}"],
            "providers": [],
            "tests": [{"description": step["objective"], "vars": {"prompt": None}, "metadata": {"step_id": step["step_id"], "variables": step["variables"]}} for step in steps],
            "note": "Provider 和 prompt 都保持空白，避免把未审核计划误当成可运行回归集。",
        },
    }
