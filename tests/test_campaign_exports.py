from redteam_memory.campaign import create_reviewed_campaign
from redteam_memory.campaign_exports import build_campaign_manifest
import redteam_memory.cli as cli_module
from redteam_memory.models import Case, ResearchPlan
from redteam_memory.store import MemoryStore


def test_campaign_exports_reuse_only_reviewed_campaign_inputs(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="export campaign", challenge="brief"))
        plan = store.save_research_plan(ResearchPlan(case_id=case.case_id, status="approved", steps=[{
            "id": "s1", "hypothesis_id": "h1", "objective": "baseline", "variables": {"mechanism": "baseline"},
            "expected_signal": "signal", "stop_condition": "stop", "approval_required": True,
        }]))
        campaign = create_reviewed_campaign(
            store, plan_id=plan.plan_id, target_kind="replay", max_turns=1, max_seconds=30,
            max_cost=None, inputs=[{"step_id": "s1", "input": "reviewed input", "review_note": "safe scope"}],
        )
        inspect = build_campaign_manifest(store, campaign.campaign_id, format="inspect")
        promptfoo = build_campaign_manifest(store, campaign.campaign_id, format="promptfoo")
    assert inspect["samples"][0]["input"] == "reviewed input"
    assert inspect["task"]["scorer"] is None
    assert promptfoo["providers"] == []
    assert promptfoo["tests"][0]["vars"]["prompt"] == "reviewed input"


def test_campaign_export_cli_writes_provider_free_promptfoo_manifest(tmp_path, capsys):
    db = tmp_path / "memory.sqlite3"
    with MemoryStore(db) as store:
        case = store.save_case(Case(title="cli export", challenge="brief"))
        plan = store.save_research_plan(ResearchPlan(case_id=case.case_id, status="approved", steps=[{
            "id": "s1", "hypothesis_id": "h1", "objective": "baseline", "variables": {},
            "expected_signal": "signal", "stop_condition": "stop", "approval_required": True,
        }]))
        campaign = create_reviewed_campaign(
            store, plan_id=plan.plan_id, target_kind="replay", max_turns=1, max_seconds=30,
            max_cost=None, inputs=[{"step_id": "s1", "input": "reviewed input"}],
        )
    output = tmp_path / "campaign.promptfoo.json"
    cli_module.main([
        "--db", str(db), "campaign", "export", "--campaign-id", campaign.campaign_id,
        "--format", "promptfoo", "--out", str(output),
    ])
    assert output.exists()
    assert '"providers": []' in output.read_text(encoding="utf-8")
