from redteam_memory.campaign import create_reviewed_campaign
from redteam_memory.external_results import import_campaign_results
from redteam_memory.models import Case, ResearchPlan
from redteam_memory.store import MemoryStore
from redteam_memory.state import derive_stage


def test_imported_external_results_feed_attempts_without_auto_confirming_impact(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="external results", challenge="brief"))
        plan = store.save_research_plan(ResearchPlan(case_id=case.case_id, status="approved", steps=[{
            "id": "s1", "hypothesis_id": "h1", "objective": "baseline", "variables": {"mechanism": "baseline"},
            "expected_signal": "signal", "stop_condition": "stop", "approval_required": True,
        }]))
        campaign = create_reviewed_campaign(
            store, plan_id=plan.plan_id, target_kind="replay", max_turns=1, max_seconds=30,
            max_cost=None, inputs=[{"step_id": "s1", "input": "reviewed"}],
        )
        result = import_campaign_results(store, campaign_id=campaign.campaign_id, source="inspect", results=[{
            "step_id": "s1", "outcome": "no_change", "response": "observed", "refusal": True,
            "observed_effect": "no external state change", "evidence_description": "judge trace",
            "evidence_verified": True, "confirms_impact": True,
        }])
        bundle = store.get_case(case.case_id)
    assert result["recorded"][0]["step_id"] == "s1"
    assert bundle["attempts"][-1]["outcome"] == "no_change"
    assert bundle["evidence"][-1]["kind"] == "external"
    assert derive_stage(bundle) == "verification"
