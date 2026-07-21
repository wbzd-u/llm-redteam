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
    filtered = client.get("/api/overview?source=user-kb").json()
    assert filtered["summary"]["totals"]["cases"] == 0
