import json

import redteam_memory.cli as cli_module
from redteam_memory.adapters import build_inspect_sample, build_promptfoo_config
from redteam_memory.markdown_import import parse_break_log_text
from redteam_memory.models import Attempt, Case, Evidence, Turn
from redteam_memory.ipi_import import import_ipi_dataset, ipi_case_id, iter_ipi_records
from redteam_memory.runner import run_once
from redteam_memory.state import derive_stage, minimize_bundle, recommend_next
from redteam_memory.store import MemoryStore
from redteam_memory.targets import PyRITHTTPTarget, ReplayTarget
from redteam_memory.grayswan import GraySwanTarget, parse_grayswan_stream


def test_case_bundle_round_trip(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(
            title="test case",
            target="sandbox",
            mechanism="context poisoning",
            tags=["test"],
        ))
        turn = store.add_turn(Turn(
            case_id=case.case_id,
            role="assistant",
            content="I will not disclose the protected value.",
            provenance="target",
            refusal=True,
        ))
        store.add_evidence(Evidence(
            case_id=case.case_id,
            turn_id=turn.turn_id,
            kind="runtime",
            description="No protected field returned",
            source="manual",
            verified=True,
        ))
        store.add_attempt(Attempt(
            case_id=case.case_id,
            mechanism="context poisoning",
            input_text="controlled test input",
            outcome="refused",
            first_refusal=True,
        ))
        bundle = store.get_case(case.case_id)
        recommendation = recommend_next(bundle)
        compact = minimize_bundle(bundle)

    assert bundle is not None
    assert bundle["tags"] == ["test"]
    assert len(bundle["turns"]) == 1
    assert bundle["turns"][0]["refusal"] is True
    assert bundle["evidence"][0]["verified"] is True
    assert bundle["attempts"][0]["outcome"] == "refused"
    assert recommendation.action == "stop_and_record"
    assert recommendation.stage == "confirmed"
    assert derive_stage(bundle) == "confirmed"
    assert compact["evidence"][0]["value_redacted"] is False


def test_search_and_exports(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(
            title="Lamp route",
            target="Lamp",
            mechanism="tool binding",
            impact="permit action",
        ))
        store.add_turn(Turn(case_id=case.case_id, role="user", content="controlled canary"))
        store.add_attempt(Attempt(
            case_id=case.case_id,
            mechanism="tool binding",
            input_text="controlled canary",
            outcome="refused",
        ))
        bundle = store.get_case(case.case_id)
        assert bundle is not None
        assert len(store.search("Lamp")) == 1
        inspect_sample = build_inspect_sample(bundle)
        promptfoo = build_promptfoo_config([bundle])

    assert inspect_sample["id"] == case.case_id
    assert inspect_sample["input"] == "controlled canary"
    assert promptfoo["tests"][0]["vars"]["prompt"] == "controlled canary"
    json.dumps(promptfoo)


def test_empty_cases_are_skipped_from_promptfoo():
    bundle = Case(title="metadata only").to_dict()
    config = build_promptfoo_config([bundle])
    assert config["tests"] == []
    assert len(build_promptfoo_config([bundle], include_empty=True)["tests"]) == 1


def test_replay_runner_persists_both_sides(tmp_path):
    import asyncio

    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="runner case"))
        target = ReplayTarget("controlled response", metadata={"adapter": "replay"})
        result = asyncio.run(run_once(
            store,
            case_id=case.case_id,
            target=target,
            prompt="controlled input",
            mechanism="baseline",
            conversation_id="session-1",
            outcome="unclear",
        ))
        bundle = store.get_case(case.case_id)

    assert result.response == "controlled response"
    assert [turn["role"] for turn in bundle["turns"]] == ["user", "assistant"]
    assert bundle["turns"][0]["metadata"]["conversation_id"] == "session-1"
    assert bundle["attempts"][0]["outcome"] == "unclear"
    assert target.prompts == [("controlled input", "session-1")]


def test_pyrit_target_is_lazy_and_validates_placeholder():
    target = PyRITHTTPTarget(
        raw_http_request="POST / HTTP/1.1\nHost: example.test\n\n{\"prompt\": \"{PROMPT}\"}",
        prompt_encoding="json",
    )
    assert target.response_key is None
    assert target.prompt_encoding == "json"
    try:
        PyRITHTTPTarget(raw_http_request="POST / HTTP/1.1\nHost: example.test\n\n{}")
    except ValueError as exc:
        assert "placeholder" in str(exc)
    else:
        raise AssertionError("missing placeholder should fail early")


def test_grayswan_sse_parser_reconstructs_text_and_runtime_fields():
    response = parse_grayswan_stream([
        'metadata:{"messageId":"assistant-1","chatId":"chat-1"}\n',
        '0:"Hello"\n',
        '0:" world"\n',
        'd:{"finishReason":"stop","success":false,"score":0}\n',
    ])
    assert response.text == "Hello world"
    assert response.metadata["messageId"] == "assistant-1"
    assert response.metadata["finish"]["finishReason"] == "stop"
    assert len(response.evidence) == 2
    assert all(item["verified"] for item in response.evidence)
    assert not any(item["metadata"]["confirms_impact"] for item in response.evidence)
    bundle = {"evidence": response.evidence, "attempts": []}
    assert derive_stage(bundle) == "verification"
    assert recommend_next(bundle).action == "verify_evidence"

    success = parse_grayswan_stream(['d:{"success":true,"score":1}\n'])
    success_bundle = {"evidence": success.evidence, "attempts": []}
    assert derive_stage(success_bundle) == "confirmed"
    assert recommend_next(success_bundle).action == "stop_and_record"


def test_grayswan_payload_preserves_existing_chat_id():
    target = GraySwanTarget(
        model="model-1",
        association_id="association-1",
        behavior_id="behavior-1",
        challenge_id="challenge-1",
        headers={"Cookie": "local-only"},
        chat_id="chat-1",
        parent_id="assistant-1",
    )
    payload = target._payload("controlled canary")
    assert payload["id"] == "chat-1"
    assert payload["message"]["parentId"] == "assistant-1"
    assert payload["message"]["content"] == "controlled canary"


def test_grayswan_cli_defaults_to_dry_run_without_loading_headers(tmp_path, capsys):
    headers_file = tmp_path / "missing.headers.json"
    cli_module.main([
        "--db", str(tmp_path / "memory.sqlite3"),
        "run", "grayswan",
        "--case-id", "case-1",
        "--mechanism", "baseline",
        "--input", "controlled canary",
        "--model", "model-1",
        "--association-id", "association-1",
        "--behavior-id", "behavior-1",
        "--challenge-id", "challenge-1",
        "--headers-file", str(headers_file),
    ])
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True
    assert output["headers_loaded"] is False
    assert not headers_file.exists()


def test_grayswan_cli_execute_loads_headers_without_printing_them(tmp_path, capsys, monkeypatch):
    headers_file = tmp_path / "session.headers.json"
    secret = "Bearer controlled-secret"
    headers_file.write_text(json.dumps({"Authorization": secret}), encoding="utf-8")
    captured = {}

    class FakeTarget:
        def __init__(self, **kwargs):
            captured["target"] = kwargs

    class FakeResult:
        def to_dict(self):
            return {"status": "recorded"}

    async def fake_run_once(store, **kwargs):
        captured["run"] = kwargs
        return FakeResult()

    monkeypatch.setattr(cli_module, "GraySwanTarget", FakeTarget)
    monkeypatch.setattr(cli_module, "run_once", fake_run_once)
    cli_module.main([
        "--db", str(tmp_path / "memory.sqlite3"),
        "run", "grayswan",
        "--case-id", "case-1",
        "--mechanism", "baseline",
        "--input", "controlled canary",
        "--model", "model-1",
        "--association-id", "association-1",
        "--behavior-id", "behavior-1",
        "--challenge-id", "challenge-1",
        "--headers-file", str(headers_file),
        "--execute",
    ])
    output = capsys.readouterr().out
    assert captured["target"]["headers"] == {"Authorization": secret}
    assert captured["run"]["prompt"] == "controlled canary"
    assert secret not in output


def test_state_machine_halts_repeated_no_change(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="halt case"))
        store.add_attempt(Attempt(
            case_id=case.case_id,
            mechanism="same-mechanism",
            input_text="one",
            outcome="refused",
        ))
        store.add_attempt(Attempt(
            case_id=case.case_id,
            mechanism="same-mechanism",
            input_text="two",
            outcome="no_change",
        ))
        bundle = store.get_case(case.case_id)

    assert derive_stage(bundle) == "halted"
    assert recommend_next(bundle).action == "switch_mechanism"


def test_markdown_import_extracts_id_sections_and_preserves_status(tmp_path):
    text = """
### B-20260714-001 - Lamp Standing-Order Exception
The tool call changed the evaluator state.

### A-20260716-001 - Guard Replay Failed
The stronger model refused and no state changed.
"""
    records = parse_break_log_text(text, source="knowledge-base")
    assert [record["case_id"] for record in records] == ["B-20260714-001", "A-20260716-001"]
    assert records[0]["target"] == "Lamp"
    assert records[0]["status"] == "reported"
    assert records[1]["status"] == "negative"

    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        existing = store.save_case(Case(case_id="B-20260714-001", title="existing", status="confirmed"))
        imported = store.import_cases(records)

    assert existing.status == "confirmed"
    assert imported[0].status == "confirmed"


def test_ipi_import_is_deterministic_and_idempotent(tmp_path):
    dataset = tmp_path / "attacks.jsonl"
    dataset.write_text(
        '{"behavior_id":"book-hotel","attack":"untrusted note"}\n'
        '{"behavior_id":"book-hotel","attack":"second note"}\n',
        encoding="utf-8",
    )
    assert list(iter_ipi_records(dataset))[0]["behavior_id"] == "book-hotel"
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        first = import_ipi_dataset(store, dataset)
        second = import_ipi_dataset(store, dataset)
        cases = store.list_cases()
        attempts = [store.get_case(case["case_id"])["attempts"] for case in cases]
        first_case = store.get_case(cases[0]["case_id"])
        first_attempt_id = first_case["attempts"][0]["attempt_id"]
        first_attempt = store.get_attempt(first_attempt_id)

    assert first["records_seen"] == 2
    assert first["cases_created"] == 2
    assert first["attempts_created"] == 2
    assert second["cases_created"] == 0
    assert second["attempts_created"] == 0
    assert len(cases) == 2
    assert sum(len(items) for items in attempts) == 2
    assert first_attempt["case_id"] == cases[0]["case_id"]
    assert ipi_case_id("book-hotel", "untrusted note").startswith("ipi-")
