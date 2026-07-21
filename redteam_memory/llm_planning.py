"""Optional, explicitly invoked LLM planning over the local research brief."""

from __future__ import annotations

from typing import Any

from .llm_provider import OpenAICompatiblePlanner
from .models import ResearchPlan
from .planner import build_planner_brief, validate_plan_payload
from .store import MemoryStore


def normalize_planner_profile(payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = str(payload.get("endpoint", "")).strip()
    model = str(payload.get("model", "")).strip()
    timeout = float(payload.get("timeout", 60))
    if not endpoint or not model:
        raise ValueError("endpoint and model are required")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    return {
        "endpoint": endpoint,
        "model": model,
        "api_key_env": str(payload.get("api_key_env", "OPENAI_API_KEY")).strip() or "OPENAI_API_KEY",
        "timeout": timeout,
    }


def generate_reviewable_llm_plan(
    store: MemoryStore,
    *,
    case_id: str,
    profile: dict[str, Any],
    execute: bool = False,
) -> dict[str, Any]:
    """Generate a validated draft only when the caller explicitly opts in."""
    profile = normalize_planner_profile(profile)
    brief = build_planner_brief(store, case_id)
    provider = OpenAICompatiblePlanner(**profile)
    if not execute:
        return {**provider.dry_run(brief), "network_execution": False}
    payload = validate_plan_payload(provider.generate(brief))
    plan = store.save_research_plan(ResearchPlan(
        case_id=case_id, planner=f"openai-compatible:{profile['model']}",
        status="draft", hypotheses=payload["hypotheses"], steps=payload["steps"],
        context=brief, notes=payload["notes"],
    ))
    return {"dry_run": False, "network_execution": True, "plan": plan.to_dict()}
