"""Export reviewed local Campaign inputs to reproducible experiment manifests."""

from __future__ import annotations

from typing import Any

from .store import MemoryStore


def build_campaign_manifest(store: MemoryStore, campaign_id: str, *, format: str) -> dict[str, Any]:
    """Return an Inspect AI or Promptfoo manifest without executing a provider.

    The artifact is local and contains only inputs which the user already
    reviewed for the linked Campaign. It does not choose a model, credentials,
    an automatic success judge, or a network provider.
    """
    campaign = store.get_campaign(campaign_id)
    if campaign is None:
        raise KeyError(f"unknown campaign: {campaign_id}")
    plan = store.get_research_plan(str(campaign["plan_id"]))
    bundle = store.get_case(str(campaign["case_id"]))
    if plan is None or bundle is None:
        raise KeyError(f"campaign is missing its linked plan or case: {campaign_id}")
    inputs = store.list_campaign_inputs(campaign_id)
    if not inputs:
        raise ValueError("campaign has no reviewed inputs")
    step_by_id = {str(step["id"]): step for step in plan["steps"]}
    common = {
        "case_id": bundle["case_id"],
        "campaign_id": campaign_id,
        "plan_id": plan["plan_id"],
        "target": bundle.get("target", ""),
        "success_criteria": (bundle.get("intake") or {}).get("success_criteria", []),
        "execution_limits": {
            "max_turns": campaign["max_turns"],
            "max_seconds": campaign["max_seconds"],
            "max_cost": campaign["max_cost"],
        },
        "review_scope": "inputs were manually reviewed in the local workbench",
    }
    samples = []
    for item in inputs:
        step = step_by_id.get(str(item["step_id"]), {})
        samples.append({
            "id": f"{campaign_id}:{item['step_id']}",
            "input": item["input_text"],
            "metadata": {
                **common,
                "step_id": item["step_id"],
                "objective": step.get("objective", ""),
                "variables": step.get("variables", {}),
                "review_note": item.get("review_note", ""),
            },
        })
    if format == "inspect":
        return {
            "format": "inspect-ai-campaign-manifest/v1",
            "task": {"name": "reviewed_campaign", "solver": "generate", "scorer": None},
            "samples": samples,
            "instructions": [
                "Select an authorized model/provider in Inspect AI before running.",
                "Add a deployment-specific scorer; a generic text judge is intentionally omitted.",
            ],
        }
    if format == "promptfoo":
        return {
            "description": f"Reviewed campaign regression: {bundle['title']}",
            "providers": [],
            "prompts": ["{{prompt}}"],
            "tests": [
                {"description": sample["metadata"]["objective"] or sample["id"], "vars": {"prompt": sample["input"]}, "metadata": sample["metadata"]}
                for sample in samples
            ],
            "instructions": [
                "Configure an authorized provider locally before running.",
                "Add task-specific assertions backed by runtime evidence.",
            ],
        }
    raise ValueError("format must be inspect or promptfoo")
