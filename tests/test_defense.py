import json

import redteam_memory.cli as cli_module
from redteam_memory.defense import coverage_matrix, observation_verdict, regression_gate
from redteam_memory.models import Case, DefenseObservation, DefenseProfile
from redteam_memory.store import MemoryStore


def _observation(
    case_id: str,
    profile_id: str,
    run_id: str,
    expected: str,
    observed: str,
    **extra,
):
    return DefenseObservation(
        case_id=case_id,
        profile_id=profile_id,
        run_id=run_id,
        expected_disposition=expected,
        observed_disposition=observed,
        **extra,
    )


def test_defense_profiles_and_observations_round_trip(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="safe technical query"))
        profile = store.save_defense_profile(DefenseProfile(
            name="Local policy classifier",
            version="1.0",
            kind="classifier",
            source="internal documentation",
            scopes=["text input"],
            assumptions=["documented English coverage"],
            limitations=["multilingual behavior requires measurement"],
        ))
        stored = store.add_defense_observation(_observation(
            case.case_id,
            profile.profile_id,
            "baseline-v1",
            "allow",
            "block",
            language="en",
            carrier="text",
            latency_ms=12.5,
            verified=True,
        ))
        profiles = store.list_defense_profiles()
        observations = store.list_defense_observations(
            profile_id=profile.profile_id, run_id="baseline-v1"
        )

    assert stored.verified is True
    assert profiles[0]["scopes"] == ["text input"]
    assert observations[0]["verified"] is True
    assert observation_verdict(observations[0]) == "over_block"


def test_coverage_matrix_groups_language_carrier_and_latency():
    observations = [
        _observation("case-1", "defense-1", "run-1", "allow", "allow", language="en", latency_ms=10).to_dict(),
        _observation("case-2", "defense-1", "run-1", "allow", "block", language="en", latency_ms=20).to_dict(),
        _observation("case-3", "defense-1", "run-1", "block", "allow", language="zh").to_dict(),
    ]
    matrix = coverage_matrix(observations)
    english = next(row for row in matrix if row["language"] == "en")
    chinese = next(row for row in matrix if row["language"] == "zh")

    assert english["total"] == 2
    assert english["aligned"] == 1
    assert english["over_block"] == 1
    assert english["latency_avg_ms"] == 15.0
    assert chinese["under_block"] == 1


def test_regression_gate_flags_under_block_and_over_block_changes():
    baseline = [
        _observation("unsafe-case", "defense-1", "v1", "block", "block").to_dict(),
        _observation("safe-case", "defense-1", "v1", "allow", "allow").to_dict(),
    ]
    candidate = [
        _observation("unsafe-case", "defense-1", "v2", "block", "allow").to_dict(),
        _observation("safe-case", "defense-1", "v2", "allow", "block").to_dict(),
    ]
    report = regression_gate(baseline, candidate)

    assert report["pass"] is False
    assert report["requires_human_review"] is True
    assert report["critical_regressions"] == 1
    assert {item["classification"] for item in report["changes"]} == {
        "critical_under_block_regression",
        "over_block_regression",
    }


def test_defense_cli_records_and_aggregates_observations(tmp_path, capsys):
    db = tmp_path / "memory.sqlite3"
    cli_module.main(["--db", str(db), "case", "add", "--title", "safe check"])
    case_id = json.loads(capsys.readouterr().out)["case_id"]
    cli_module.main([
        "--db", str(db), "defense", "profile", "add", "--name", "Documented guard",
        "--kind", "classifier", "--scope", "text input",
    ])
    profile_id = json.loads(capsys.readouterr().out)["profile_id"]
    cli_module.main([
        "--db", str(db), "defense", "observe", "add", "--case-id", case_id,
        "--profile-id", profile_id, "--run-id", "v1", "--expected", "allow",
        "--observed", "block", "--verified",
    ])
    capsys.readouterr()
    cli_module.main([
        "--db", str(db), "defense", "matrix", "--profile-id", profile_id,
    ])
    matrix = json.loads(capsys.readouterr().out)

    assert matrix[0]["over_block"] == 1
    assert matrix[0]["verified"] == 1
