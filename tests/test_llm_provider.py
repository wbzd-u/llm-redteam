import json

import redteam_memory.cli as cli_module
from redteam_memory.llm_provider import OpenAICompatiblePlanner, ProviderError
from redteam_memory.models import Case
from redteam_memory.store import MemoryStore


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _valid_plan():
    return {
        "hypotheses": [{
            "id": "h1", "statement": "test", "basis": "brief", "priority": "high",
            "positive_signal": "signal", "negative_signal": "negative",
        }],
        "steps": [{
            "id": "s1", "hypothesis_id": "h1", "objective": "compare", "variables": {},
            "expected_signal": "signal", "stop_condition": "stop", "approval_required": True,
        }],
    }


def test_openai_compatible_provider_reads_key_only_when_generating(monkeypatch):
    calls = {}

    def transport(request, timeout):
        calls["authorization"] = request.get_header("Authorization")
        calls["timeout"] = timeout
        return _Response({"choices": [{"message": {"content": json.dumps(_valid_plan())}}]})

    provider = OpenAICompatiblePlanner(
        endpoint="http://local.test/v1/chat/completions", model="test-model", api_key_env="TEST_PLAN_KEY", transport=transport,
    )
    assert provider.dry_run({"case": {}})["credentials_loaded"] is False
    try:
        provider.generate({"case": {}})
    except ProviderError as exc:
        assert "TEST_PLAN_KEY" in str(exc)
    else:
        raise AssertionError("missing key must fail")

    monkeypatch.setenv("TEST_PLAN_KEY", "local-test-secret")
    result = provider.generate({"case": {}})
    assert result["hypotheses"][0]["id"] == "h1"
    assert calls["authorization"] == "Bearer local-test-secret"


def test_plan_generate_cli_dry_run_does_not_require_key(tmp_path, capsys):
    db = tmp_path / "memory.sqlite3"
    with MemoryStore(db) as store:
        case = store.save_case(Case(title="dry run", challenge="brief"))
    cli_module.main([
        "--db", str(db), "plan", "generate", "--case-id", case.case_id,
        "--endpoint", "http://local.test/v1/chat/completions", "--model", "test-model",
    ])
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True
    assert output["credentials_loaded"] is False
