import sys

from redteam_memory.llm_guard_adapter import LLMGuardAdapter, record_llm_guard_observation
from redteam_memory.models import Case, DefenseProfile
from redteam_memory.store import MemoryStore


def _fake_bridge(tmp_path):
    bridge = tmp_path / "fake_llm_guard_bridge.py"
    bridge.write_text(
        """import json, sys
request = json.loads(sys.stdin.read())
prompt = request['prompt']
print(json.dumps({
    'ok': True,
    'scanner': request['scanner'],
    'prompt': prompt,
    'sanitized_prompt': prompt,
    'valid': prompt != 'blocked canary',
    'risk_score': 0.9 if prompt == 'blocked canary' else 0.1,
    'latency_ms': 3.5,
}))
""",
        encoding="utf-8",
    )
    return bridge


def test_llm_guard_adapter_runs_isolated_json_bridge(tmp_path):
    repo = tmp_path / "llm-guard"
    repo.mkdir()
    adapter = LLMGuardAdapter(
        repo=repo,
        python_executable=sys.executable,
        bridge_script=_fake_bridge(tmp_path),
    )

    allowed = adapter.scan("safe canary")
    blocked = adapter.scan("blocked canary")

    assert allowed["valid"] is True
    assert allowed["scanner"] == "PromptInjection"
    assert blocked["valid"] is False
    assert blocked["risk_score"] == 0.9


def test_llm_guard_result_records_common_defense_observation(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="authorized scanner check"))
        profile = store.save_defense_profile(DefenseProfile(name="LLM Guard PromptInjection"))
        observation = record_llm_guard_observation(
            store,
            case_id=case.case_id,
            profile_id=profile.profile_id,
            run_id="llm-guard-0.3.16",
            expected_disposition="allow",
            result={
                "prompt": "safe canary",
                "sanitized_prompt": "safe canary",
                "valid": False,
                "scanner": "PromptInjection",
                "risk_score": 0.8,
                "latency_ms": 4.2,
            },
            language="en",
            verified=True,
        )
        stored = store.list_defense_observations(run_id="llm-guard-0.3.16")

    assert observation.observed_disposition == "block"
    assert stored[0]["metadata"]["adapter"] == "llm_guard"
    assert stored[0]["metadata"]["risk_score"] == 0.8
