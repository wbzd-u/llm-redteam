from redteam_memory.execution_artifacts import compile_execution_artifacts
from redteam_memory.models import Case
from redteam_memory.planner import deterministic_draft
from redteam_memory.store import MemoryStore


def test_execution_artifacts_require_reviewed_inputs_and_approved_plan(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="artifact task", challenge="brief"))
        plan = store.save_research_plan(deterministic_draft(store, case.case_id))
        draft = compile_execution_artifacts(store, plan.plan_id)
        assert draft["ready_for_campaign"] is False
        assert draft["steps"][0]["input"] is None
        store.set_research_plan_status(plan.plan_id, "approved")
        approved = compile_execution_artifacts(store, plan.plan_id)
    assert approved["ready_for_campaign"] is True
    assert approved["pyrit"]["required_local_configuration"]
