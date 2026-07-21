import asyncio
import json

import redteam_memory.cli as cli_module
from redteam_memory.campaign import create_campaign, create_reviewed_campaign, load_campaign_inputs, run_campaign
from redteam_memory.models import Case, ResearchPlan
from redteam_memory.store import MemoryStore
from redteam_memory.targets import ReplayTarget, TargetResponse


def _approved_plan(store, case_id):
    plan = store.save_research_plan(ResearchPlan(
        case_id=case_id, status="approved",
        hypotheses=[{
            "id": "h1", "statement": "test", "basis": "brief", "priority": "high",
            "positive_signal": "signal", "negative_signal": "negative",
        }],
        steps=[{
            "id": "s1", "hypothesis_id": "h1", "objective": "compare", "variables": {},
            "expected_signal": "signal", "stop_condition": "stop", "approval_required": True,
        }, {
            "id": "s2", "hypothesis_id": "h1", "objective": "compare two", "variables": {},
            "expected_signal": "signal", "stop_condition": "stop", "approval_required": True,
        }],
    ))
    return plan


def test_campaign_requires_approved_plan_and_stops_at_turn_budget(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="campaign", challenge="brief"))
        plan = _approved_plan(store, case.case_id)
        campaign = create_campaign(
            store, plan_id=plan.plan_id, target_kind="replay", max_turns=1, max_seconds=60, max_cost=None,
        )
        target = ReplayTarget(["one", "two"])
        result = asyncio.run(run_campaign(store, campaign_id=campaign.campaign_id, target=target, inputs=[
            {"step_id": "s1", "input": "first"}, {"step_id": "s2", "input": "second"},
        ]))

    assert result["campaign"]["status"] == "budget_exhausted"
    assert result["campaign"]["executed_turns"] == 1
    assert target.prompts == [("first", None)]


def test_campaign_stops_when_verified_runtime_evidence_confirms(tmp_path):
    class ConfirmingTarget:
        async def send(self, prompt, *, conversation_id=None):
            return TargetResponse(text="recorded", evidence=[{
                "kind": "runtime", "description": "platform passed", "source": "test",
                "verified": True, "metadata": {"confirms_impact": True},
            }])

    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="confirmed campaign", challenge="brief"))
        plan = _approved_plan(store, case.case_id)
        campaign = create_campaign(
            store, plan_id=plan.plan_id, target_kind="replay", max_turns=2, max_seconds=60, max_cost=None,
        )
        result = asyncio.run(run_campaign(
            store, campaign_id=campaign.campaign_id, target=ConfirmingTarget(),
            inputs=[{"step_id": "s1", "input": "first"}, {"step_id": "s2", "input": "second"}],
        ))

    assert result["campaign"]["status"] == "confirmed"
    assert len(result["results"]) == 1


def test_campaign_input_file_and_plan_approval_cli(tmp_path, capsys):
    db = tmp_path / "memory.sqlite3"
    with MemoryStore(db) as store:
        case = store.save_case(Case(title="approval", challenge="brief"))
        plan = store.save_research_plan(ResearchPlan(case_id=case.case_id))
    cli_module.main(["--db", str(db), "plan", "approve", plan.plan_id])
    assert json.loads(capsys.readouterr().out)["status"] == "approved"
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text(json.dumps([{"step_id": "s1", "input": "controlled"}]), encoding="utf-8")
    assert load_campaign_inputs(inputs_file) == [{"step_id": "s1", "input": "controlled"}]


def test_reviewed_campaign_persists_local_inputs_without_execution(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="reviewed campaign", challenge="brief"))
        plan = _approved_plan(store, case.case_id)
        campaign = create_reviewed_campaign(
            store, plan_id=plan.plan_id, target_kind="replay", max_turns=1,
            max_seconds=60, max_cost=0, inputs=[{
                "step_id": "s1", "input": "reviewed local test", "review_note": "baseline only",
            }],
        )
        inputs = store.list_campaign_inputs(campaign.campaign_id)
    assert campaign.status == "pending"
    assert inputs[0]["input_text"] == "reviewed local test"
