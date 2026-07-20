import json

import redteam_memory.cli as cli_module
from redteam_memory.intake import normalize_intake_record
from redteam_memory.store import MemoryStore


def test_intake_import_creates_case_brief_and_turns(tmp_path, capsys):
    intake_file = tmp_path / "challenge.json"
    intake_file.write_text(json.dumps({
        "title": "Authorized test",
        "target": "sandbox",
        "challenge": "Verify a harmless baseline.",
        "authorization_scope": "local CTF only",
        "success_criteria": ["platform state changes"],
        "constraints": ["maximum 3 turns"],
        "target_config": {"adapter": "replay"},
        "tags": ["authorized", "baseline"],
        "turns": [
            {"role": "user", "content": "controlled canary"},
            {"role": "assistant", "content": "controlled response", "refusal": False},
        ],
    }), encoding="utf-8")
    db = tmp_path / "memory.sqlite3"

    cli_module.main(["--db", str(db), "intake", "import", str(intake_file)])
    output = json.loads(capsys.readouterr().out)
    case_id = output["case"]["case_id"]

    with MemoryStore(db) as store:
        bundle = store.get_case(case_id)

    assert output["turns_imported"] == 2
    assert bundle["intake"]["authorization_scope"] == "local CTF only"
    assert bundle["intake"]["success_criteria"] == ["platform state changes"]
    assert bundle["intake"]["target_config"] == {"adapter": "replay"}
    assert [turn["content"] for turn in bundle["turns"]] == ["controlled canary", "controlled response"]


def test_intake_normalization_rejects_missing_challenge():
    try:
        normalize_intake_record({"title": "missing brief"})
    except ValueError as exc:
        assert "challenge" in str(exc)
    else:
        raise AssertionError("missing challenge must fail")
