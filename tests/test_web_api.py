import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from redteam_memory.models import Case
from redteam_memory.store import MemoryStore
from redteam_memory.web_api import create_app


def test_local_dashboard_api_exposes_read_only_case_and_research_data(tmp_path):
    db = tmp_path / "memory.sqlite3"
    with MemoryStore(db) as store:
        case = store.save_case(Case(title="dashboard case", target="sandbox", challenge="brief"))

    client = TestClient(create_app(db))
    assert client.get("/api/health").json()["status"] == "ok"
    overview = client.get("/api/overview")
    assert overview.status_code == 200
    assert overview.json()["summary"]["totals"]["cases"] == 1
    assert client.get("/api/cases").json()[0]["case_id"] == case.case_id
    assert client.get(f"/api/cases/{case.case_id}").json()["title"] == "dashboard case"
    assert client.get("/api/cases/unknown").status_code == 404
    assert client.get("/api/research/summary").status_code == 200
    assert "methods_draft" in client.get("/api/research/paper-packet").json()
    assert "mechanism_by_status" in client.get("/api/research/cross-tabs").json()
    filtered = client.get("/api/overview?source=user-kb").json()
    assert filtered["summary"]["totals"]["cases"] == 0


def test_task_workspace_creates_task_draft_and_observation(tmp_path):
    db = tmp_path / "memory.sqlite3"
    client = TestClient(create_app(db))
    created = client.post("/api/tasks", json={
        "title": "authorized task", "target": "sandbox", "challenge": "brief",
        "authorization_scope": "local sandbox", "success_criteria": ["visible test result"],
    })
    assert created.status_code == 200
    case_id = created.json()["case_id"]
    workspace = client.get(f"/api/tasks/{case_id}/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["next_action"]["action"] == "run_clean_baseline"
    draft = client.post(f"/api/tasks/{case_id}/plan/draft")
    assert draft.status_code == 200
    approved = client.post(f"/api/tasks/{case_id}/plans/{draft.json()['plan_id']}/approve")
    assert approved.json()["status"] == "approved"
    artifacts = client.get(f"/api/tasks/{case_id}/plans/{draft.json()['plan_id']}/artifacts")
    assert artifacts.json()["ready_for_campaign"] is True
    campaign = client.post(f"/api/tasks/{case_id}/plans/{draft.json()['plan_id']}/campaigns", json={
        "target_kind": "replay", "max_turns": 1, "max_seconds": 30, "max_cost": 0,
        "inputs": [{"step_id": draft.json()["steps"][0]["id"], "input": "reviewed baseline"}],
    })
    assert campaign.status_code == 200
    assert campaign.json()["campaign"]["status"] == "pending"
    assert campaign.json()["reviewed_input_count"] == 1
    observation = client.post(f"/api/tasks/{case_id}/observation", json={
        "input_text": "baseline", "response_text": "observed response", "mechanism": "baseline",
        "outcome": "unknown", "observed_effect": "no external effect",
    })
    assert observation.status_code == 200
    assert observation.json()["attempt_id"]
