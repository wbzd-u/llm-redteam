"""Budgeted execution for explicitly approved plan steps."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from .models import Campaign, utc_now
from .runner import run_once
from .state import derive_stage
from .store import MemoryStore
from .targets import AsyncTarget


CAMPAIGN_TERMINAL = {"completed", "confirmed", "budget_exhausted", "failed", "halted"}


def load_campaign_inputs(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"campaign inputs file does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"campaign inputs file is not valid JSON: {source}") from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError("campaign inputs must be a non-empty JSON list")
    normalized: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each campaign input must be an object")
        step_id, prompt = item.get("step_id"), item.get("input")
        if not isinstance(step_id, str) or not step_id.strip() or not isinstance(prompt, str) or not prompt:
            raise ValueError("each campaign input requires non-empty string step_id and input")
        normalized.append({"step_id": step_id, "input": prompt})
    return normalized


def create_campaign(
    store: MemoryStore,
    *,
    plan_id: str,
    target_kind: str,
    max_turns: int,
    max_seconds: float,
    max_cost: float | None,
    conversation_id: str = "",
) -> Campaign:
    plan = store.get_research_plan(plan_id)
    if plan is None:
        raise KeyError(f"unknown plan: {plan_id}")
    if max_turns < 1 or max_seconds <= 0 or (max_cost is not None and max_cost < 0):
        raise ValueError("campaign budgets must be positive (max_cost may be zero)")
    return store.save_campaign(Campaign(
        case_id=plan["case_id"], plan_id=plan_id, target_kind=target_kind,
        max_turns=max_turns, max_seconds=max_seconds, max_cost=max_cost,
        conversation_id=conversation_id,
    ))


async def run_campaign(
    store: MemoryStore,
    *,
    campaign_id: str,
    target: AsyncTarget,
    inputs: list[dict[str, str]],
) -> dict[str, Any]:
    record = store.get_campaign(campaign_id)
    if record is None:
        raise KeyError(f"unknown campaign: {campaign_id}")
    campaign = Campaign(**record)
    if campaign.status in CAMPAIGN_TERMINAL:
        raise ValueError(f"campaign is already terminal: {campaign.status}")
    plan = store.get_research_plan(campaign.plan_id)
    if plan is None:
        raise KeyError(f"unknown plan: {campaign.plan_id}")
    if plan["status"] != "approved":
        raise ValueError("campaign execution requires a plan with status=approved")
    if campaign.target_kind not in {"replay", "grayswan"}:
        raise ValueError(f"unsupported campaign target kind: {campaign.target_kind}")
    step_by_id = {step["id"]: step for step in plan["steps"]}
    if len({item["step_id"] for item in inputs}) != len(inputs):
        raise ValueError("campaign input step_id values must be unique")
    if any(item["step_id"] not in step_by_id for item in inputs):
        raise ValueError("campaign inputs reference an unknown plan step")

    campaign.status = "running"
    campaign.started_at = utc_now()
    campaign.stop_reason = ""
    store.save_campaign(campaign)
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    for item in inputs:
        if campaign.executed_turns >= campaign.max_turns:
            campaign.status, campaign.stop_reason = "budget_exhausted", "max_turns reached"
            break
        if time.monotonic() - started >= campaign.max_seconds:
            campaign.status, campaign.stop_reason = "budget_exhausted", "max_seconds reached"
            break
        if campaign.max_cost is not None and campaign.observed_cost >= campaign.max_cost:
            campaign.status, campaign.stop_reason = "budget_exhausted", "max_cost reached"
            break
        step = step_by_id[item["step_id"]]
        mechanism = str(step.get("variables", {}).get("mechanism") or f"plan:{item['step_id']}")
        try:
            result = await run_once(
                store,
                case_id=campaign.case_id,
                target=target,
                prompt=item["input"],
                mechanism=mechanism,
                conversation_id=campaign.conversation_id or None,
                attempt_notes=f"campaign={campaign.campaign_id}; step={item['step_id']}",
            )
        except RuntimeError as exc:
            campaign.status, campaign.stop_reason = "failed", str(exc)
            break
        campaign.executed_turns += 1
        response_cost = result.metadata.get("cost_usd", 0)
        if isinstance(response_cost, (int, float)) and response_cost >= 0:
            campaign.observed_cost += float(response_cost)
        results.append({"step_id": item["step_id"], **result.to_dict()})
        bundle = store.get_case(campaign.case_id)
        if bundle is not None and derive_stage(bundle) == "confirmed":
            campaign.status, campaign.stop_reason = "confirmed", "verified runtime evidence confirmed impact"
            break
        store.save_campaign(campaign)
        await asyncio.sleep(0)
    else:
        campaign.status, campaign.stop_reason = "completed", "all supplied approved inputs executed"

    if campaign.status == "running":
        campaign.status, campaign.stop_reason = "completed", "no inputs remaining"
    campaign.completed_at = utc_now()
    store.save_campaign(campaign)
    return {"campaign": campaign.to_dict(), "results": results}
