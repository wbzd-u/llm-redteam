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
class ChallengeIntake:
    """Structured, user-supplied context for an authorized challenge.

    This stays separate from ``Case`` so an imported or historical case can
    retain its original metadata while its challenge brief is updated.
    """

    case_id: str
    authorization_scope: str = ""
    success_criteria: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    target_config: dict[str, Any] = field(default_factory=dict)
    source: str = "manual"
    intake_id: str = field(default_factory=lambda: new_id("intake"))
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MechanismCard:
    """A reusable, evidence-linked red-team mechanism observation."""

    name: str
    category: str
    summary: str = ""
    match_terms: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    applicability_signals: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)
    confidence: str = "hypothesis"
    notes: str = ""
    mechanism_id: str = field(default_factory=lambda: new_id("mechanism"))
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchPlan:
    """A versioned, reviewable test plan proposed by a user or planner."""

    case_id: str
    planner: str = "deterministic"
    status: str = "draft"
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    plan_id: str = field(default_factory=lambda: new_id("plan"))
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Campaign:
    """One budgeted execution of an approved research plan."""

    case_id: str
    plan_id: str
    target_kind: str
    max_turns: int = 1
    max_seconds: float = 60.0
    max_cost: float | None = None
    status: str = "pending"
    executed_turns: int = 0
    observed_cost: float = 0.0
    conversation_id: str = ""
    stop_reason: str = ""
    campaign_id: str = field(default_factory=lambda: new_id("campaign"))
    created_at: str = field(default_factory=utc_now)
    started_at: str = ""
    completed_at: str = ""
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CampaignInput:
    """One locally stored, human-reviewed input for a pending Campaign."""

    campaign_id: str
    step_id: str
    input_text: str
    review_note: str = ""
    input_id: str = field(default_factory=lambda: new_id("campaign-input"))
    created_at: str = field(default_factory=utc_now)
    approved_at: str = field(default_factory=utc_now)

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


@dataclass
class DefenseProfile:
    """Publicly documented properties of a defensive control.

    A profile records claims and uncertainty; it is not a reverse-engineered
    model of a third-party service.
    """

    name: str
    version: str = ""
    kind: str = "other"
    source: str = ""
    scopes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    notes: str = ""
    profile_id: str = field(default_factory=lambda: new_id("defense"))
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DefenseObservation:
    """One authorized, manually supplied defense decision observation."""

    case_id: str
    profile_id: str
    run_id: str
    expected_disposition: str
    observed_disposition: str
    language: str = "und"
    carrier: str = "text"
    latency_ms: float | None = None
    verified: bool = False
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    observation_id: str = field(default_factory=lambda: new_id("defobs"))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
