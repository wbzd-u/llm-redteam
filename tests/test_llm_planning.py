from redteam_memory.llm_planning import generate_reviewable_llm_plan, normalize_planner_profile
from redteam_memory.models import Case
from redteam_memory.store import MemoryStore


def test_llm_planner_dry_run_uses_local_brief_without_loading_credentials(tmp_path):
    profile = normalize_planner_profile({
        "endpoint": "http://local.test/v1/chat/completions", "model": "planner-test",
        "api_key_env": "MISSING_PLANNER_KEY", "timeout": 30,
    })
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="planner dry run", challenge="brief"))
        result = generate_reviewable_llm_plan(store, case_id=case.case_id, profile=profile, execute=False)
    assert result["dry_run"] is True
    assert result["credentials_loaded"] is False
    assert result["network_execution"] is False
