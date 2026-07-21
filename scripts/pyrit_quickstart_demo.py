"""Run one safe, offline PyRIT native attack and print a compact JSON result.

This intentionally uses TextTarget: it writes the transformed prompt to memory
instead of calling a model or network endpoint. It is a learning aid for the
PyRIT execution contract, not a target adapter.
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from typing import Any


if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    from pyrit.converter import Base64Converter
    from pyrit.executor.attack import AttackConverterConfig, PromptSendingAttack
    from pyrit.prompt_normalizer import ConverterConfiguration
    from pyrit.prompt_target import TextTarget
    from pyrit.setup import IN_MEMORY, initialize_pyrit_async

    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("prompt is required")
    if len(prompt) > 2000:
        raise ValueError("prompt is too long for the quickstart demo")
    converter = str(payload.get("converter", "raw"))
    if converter not in {"raw", "base64"}:
        raise ValueError("converter must be raw or base64")

    await initialize_pyrit_async(memory_db_type=IN_MEMORY, load_defaults=False, silent=True)
    output = io.StringIO()
    config = None
    if converter == "base64":
        config = AttackConverterConfig(
            request_converters=ConverterConfiguration.from_converters(converters=[Base64Converter()])
        )
    attack = PromptSendingAttack(
        objective_target=TextTarget(text_stream=output),
        attack_converter_config=config,
    )
    result = await attack.execute_async(
        objective=prompt,
        memory_labels={"mode": "offline-quickstart", "converter": converter},
    )
    return {
        "strategy": "PromptSendingAttack",
        "target": "TextTarget (offline)",
        "converter": converter,
        "sent_to_target": output.getvalue().strip(),
        "attack_result": {
            "attack_result_id": result.attack_result_id,
            "conversation_id": result.conversation_id,
            "objective": result.objective,
            "executed_turns": result.executed_turns,
            "outcome": result.outcome.value,
            "outcome_reason": result.outcome_reason,
            "execution_time_ms": result.execution_time_ms,
            "labels": result.labels,
            "metadata": result.metadata,
        },
    }


def main() -> None:
    payload = json.load(sys.stdin)
    try:
        print(json.dumps(asyncio.run(run(payload)), ensure_ascii=False))
    except Exception as exc:  # pragma: no cover - surfaced by parent process
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
