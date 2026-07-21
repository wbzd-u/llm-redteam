import csv
import json

import redteam_memory.cli as cli_module
from redteam_memory.analysis_export import case_markdown, write_attempt_csv
from redteam_memory.mechanisms import import_mechanisms
from redteam_memory.models import Attempt, Case
from redteam_memory.planner import build_hypothesis_matrix, build_planner_brief, deterministic_draft, validate_plan_payload
from redteam_memory.store import MemoryStore


def _mechanism():
    return {
        "mechanism_id": "mechanism-doc",
        "name": "Document boundary",
        "category": "indirect injection",
        "match_terms": ["document"],
        "tags": ["document-carrier"],
        "applicability_signals": ["external document is processed"],
        "preconditions": ["document enters context"],
        "negative_signals": ["document is isolated"],
        "confidence": "observed",
    }


def test_planner_brief_draft_and_persistence(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="Document task", challenge="Process a document", tags=["document-carrier"]))
        import_mechanisms(store, [_mechanism()])
        brief = build_planner_brief(store, case.case_id)
        matrix = build_hypothesis_matrix(store, case.case_id)
        plan = store.save_research_plan(deterministic_draft(store, case.case_id))
        bundle = store.get_case(case.case_id)

    assert brief["recommended_mechanisms"][0]["mechanism"]["mechanism_id"] == "mechanism-doc"
    assert plan.status == "draft"
    assert plan.steps[0]["approval_required"] is True
    assert matrix["hypotheses"][0]["mechanism"] == "Document boundary"
    assert bundle["plans"][0]["plan_id"] == plan.plan_id


def test_plan_validation_and_analysis_exports(tmp_path):
    payload = {
        "hypotheses": [{
            "id": "h1", "statement": "test", "basis": "evidence", "priority": "high",
            "positive_signal": "state", "negative_signal": "none",
        }],
        "steps": [{
            "id": "s1", "hypothesis_id": "h1", "objective": "compare", "variables": {},
            "expected_signal": "state", "stop_condition": "stop", "approval_required": True,
        }],
    }
    assert validate_plan_payload(payload)["status"] == "draft"
    payload["steps"][0]["approval_required"] = False
    try:
        validate_plan_payload(payload)
    except ValueError as exc:
        assert "approval" in str(exc)
    else:
        raise AssertionError("unapproved plan step must fail")
    payload["steps"][0]["approval_required"] = True
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="Export case", target="sandbox"))
        store.add_attempt(Attempt(case_id=case.case_id, mechanism="baseline", input_text="canary", outcome="unknown"))
        bundle = store.get_case(case.case_id)
    assert "# Export case" in case_markdown(bundle)
    csv_path = tmp_path / "attempts.csv"
    write_attempt_csv(bundle, csv_path)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["mechanism"] == "baseline"


def test_plan_import_cli_validates_and_records(tmp_path, capsys):
    db = tmp_path / "memory.sqlite3"
    with MemoryStore(db) as store:
        case = store.save_case(Case(title="plan import", challenge="brief"))
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps({
        "hypotheses": [{
            "id": "h1", "statement": "test", "basis": "brief", "priority": "high",
            "positive_signal": "signal", "negative_signal": "negative",
        }],
        "steps": [{
            "id": "s1", "hypothesis_id": "h1", "objective": "compare", "variables": {},
            "expected_signal": "signal", "stop_condition": "stop", "approval_required": True,
        }],
    }), encoding="utf-8")
    cli_module.main([
        "--db", str(db), "plan", "import", "--case-id", case.case_id,
        "--planner", "test-llm", "--json-file", str(plan_file),
    ])
    output = json.loads(capsys.readouterr().out)
    assert output["planner"] == "test-llm"
    assert output["hypotheses"][0]["id"] == "h1"
