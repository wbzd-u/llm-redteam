from redteam_memory.campaign import create_reviewed_campaign
from redteam_memory.executor_profiles import normalize_pyrit_profile, pyrit_readiness, pyrit_workbench_summary
from redteam_memory.models import Case, ChallengeIntake, ResearchPlan
from redteam_memory.store import MemoryStore


def test_pyrit_profile_only_keeps_non_secret_metadata_and_checks_readiness(tmp_path):
    profile = normalize_pyrit_profile({
        "profile_name": "local capture", "request_reference": "browser capture A",
        "placeholder": "{PROMPT}", "prompt_encoding": "json", "timeout": 45,
        "captured_request_reviewed": True, "credentials_managed_externally": True,
    })
    assert "cookie" not in profile
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="profile task", challenge="brief"))
        intake = ChallengeIntake(case_id=case.case_id, target_config={"pyrit_profile": profile})
        store.save_challenge_intake(intake)
        plan = store.save_research_plan(ResearchPlan(case_id=case.case_id, status="approved", steps=[{
            "id": "s1", "hypothesis_id": "h1", "objective": "baseline", "variables": {},
            "expected_signal": "signal", "stop_condition": "stop", "approval_required": True,
        }]))
        create_reviewed_campaign(
            store, plan_id=plan.plan_id, target_kind="pyrit-http", max_turns=1, max_seconds=30,
            max_cost=None, inputs=[{"step_id": "s1", "input": "controlled"}],
        )
        readiness = pyrit_readiness(store, case.case_id)
    assert readiness["ready"] is True
    assert readiness["handoff"]["request_template"] == "<local-captured-request-file>"


def test_pyrit_workbench_summarizes_capabilities_and_task_gaps(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="workbench task", target="sandbox", challenge="brief"))
        summary = pyrit_workbench_summary(store)

    assert len(summary["catalog"]) >= 6
    assert summary["totals"]["tasks"] == 1
    assert summary["totals"]["ready"] == 0
    assert summary["tasks"][0]["case_id"] == case.case_id
    assert summary["tasks"][0]["missing_checks"]
