from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from .models import Attempt, Evidence, Turn
from .store import MemoryStore
from .targets import AsyncTarget, TargetResponse


@dataclass
class RunResult:
    case_id: str
    attempt_id: str
    user_turn_id: str
    assistant_turn_id: str
    response: str
    outcome: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def run_once(
    store: MemoryStore,
    *,
    case_id: str,
    target: AsyncTarget,
    prompt: str,
    mechanism: str,
    conversation_id: str | None = None,
    outcome: str = "unknown",
    refusal: bool = False,
    observed_effect: str = "",
    attempt_notes: str = "",
) -> RunResult:
    """Send one controlled input and persist both sides of the exchange."""
    started = time.perf_counter()
    user_turn = store.add_turn(
        Turn(
            case_id=case_id,
            role="user",
            content=prompt,
            channel="chat",
            provenance="runner",
            metadata={"conversation_id": conversation_id or ""},
        )
    )
    try:
        response = await target.send(prompt, conversation_id=conversation_id)
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        error_text = f"{type(exc).__name__}: {exc}"
        assistant_turn = store.add_turn(
            Turn(
                case_id=case_id,
                role="evaluator",
                content=error_text,
                channel="runner",
                provenance="runner",
                observed_effect="target_error",
                metadata={"elapsed_ms": elapsed_ms},
            )
        )
        attempt = store.add_attempt(
            Attempt(
                case_id=case_id,
                mechanism=mechanism,
                input_text=prompt,
                outcome="error",
                notes=attempt_notes or error_text,
            )
        )
        raise RuntimeError(error_text) from exc

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    metadata = {**response.metadata, "elapsed_ms": elapsed_ms}
    assistant_turn = store.add_turn(
        Turn(
            case_id=case_id,
            role="assistant",
            content=response.text,
            channel="chat",
            provenance=str(response.metadata.get("adapter", "target")),
            observed_effect=observed_effect,
            refusal=refusal,
            metadata=metadata,
        )
    )

    for item in response.evidence:
        store.add_evidence(
            Evidence(
                case_id=case_id,
                turn_id=str(item.get("turn_id") or assistant_turn.turn_id),
                kind=str(item.get("kind", "runtime")),
                description=str(item.get("description", "target evidence")),
                value=str(item.get("value", "")),
                source=str(item.get("source", "target")),
                verified=bool(item.get("verified", False)),
                metadata=dict(item.get("metadata", {})),
            )
        )

    attempt = store.add_attempt(
        Attempt(
            case_id=case_id,
            mechanism=mechanism,
            input_text=prompt,
            outcome=outcome,
            notes=attempt_notes,
        )
    )
    return RunResult(
        case_id=case_id,
        attempt_id=attempt.attempt_id,
        user_turn_id=user_turn.turn_id,
        assistant_turn_id=assistant_turn.turn_id,
        response=response.text,
        outcome=outcome,
        metadata=metadata,
    )

