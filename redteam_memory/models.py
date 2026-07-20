from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@dataclass
class Case:
    title: str
    target: str = ""
    challenge: str = ""
    mechanism: str = ""
    carrier: str = ""
    impact: str = ""
    status: str = "open"
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    case_id: str = field(default_factory=lambda: new_id("case"))
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Turn:
    case_id: str
    role: str
    content: str
    channel: str = "chat"
    provenance: str = "unknown"
    observed_effect: str = ""
    refusal: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    turn_id: str = field(default_factory=lambda: new_id("turn"))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    case_id: str
    kind: str
    description: str
    value: str = ""
    source: str = ""
    verified: bool = False
    turn_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence_id: str = field(default_factory=lambda: new_id("ev"))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Attempt:
    case_id: str
    mechanism: str
    input_text: str
    outcome: str = "unknown"
    first_refusal: bool = False
    score: float | None = None
    notes: str = ""
    attempt_id: str = field(default_factory=lambda: new_id("attempt"))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

