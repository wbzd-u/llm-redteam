import json

import redteam_memory.cli as cli_module
from redteam_memory.mechanisms import normalize_mechanism_record, recommend_mechanisms
from redteam_memory.models import Case
from redteam_memory.store import MemoryStore


def _card_record():
    return {
        "mechanism_id": "mechanism-doc",
        "name": "Document context boundary",
        "category": "indirect injection",
        "match_terms": ["resume", "document"],
        "tags": ["document-carrier"],
        "applicability_signals": ["external document"],
        "preconditions": ["document reaches context"],
        "negative_signals": ["strict parser"],
        "confidence": "observed",
    }


def test_mechanism_import_link_and_recommendation(tmp_path, capsys):
    mechanism_file = tmp_path / "mechanisms.json"
    mechanism_file.write_text(json.dumps([_card_record()]), encoding="utf-8")
    db = tmp_path / "memory.sqlite3"
    with MemoryStore(db) as store:
        case = store.save_case(Case(
            title="Resume document screening",
            challenge="Process a supplied document.",
            tags=["document-carrier"],
        ))

    cli_module.main(["--db", str(db), "mechanism", "import", str(mechanism_file)])
    imported = json.loads(capsys.readouterr().out)
    assert imported[0]["mechanism_id"] == "mechanism-doc"

    cli_module.main([
        "--db", str(db), "mechanism", "link", "--mechanism-id", "mechanism-doc",
        "--case-id", case.case_id, "--relation", "observed",
    ])
    linked = json.loads(capsys.readouterr().out)
    assert linked["relation"] == "observed"

    with MemoryStore(db) as store:
        recommendations = recommend_mechanisms(store, case.case_id)
        bundle = store.get_case(case.case_id)

    assert recommendations[0]["mechanism"]["mechanism_id"] == "mechanism-doc"
    assert recommendations[0]["score"] >= 5
    assert bundle["mechanism_links"][0]["mechanism_id"] == "mechanism-doc"


def test_mechanism_normalization_rejects_bad_confidence():
    record = _card_record()
    record["confidence"] = "certain"
    try:
        normalize_mechanism_record(record)
    except ValueError as exc:
        assert "confidence" in str(exc)
    else:
        raise AssertionError("invalid confidence must fail")
