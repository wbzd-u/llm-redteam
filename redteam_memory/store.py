from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .models import (
    Attempt,
    Case,
    ChallengeIntake,
    DefenseObservation,
    DefenseProfile,
    Evidence,
    MechanismCard,
    ResearchPlan,
    Turn,
    new_id,
    utc_now,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    target TEXT NOT NULL,
    challenge TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    carrier TEXT NOT NULL,
    impact TEXT NOT NULL,
    status TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS turns (
    turn_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    channel TEXT NOT NULL,
    provenance TEXT NOT NULL,
    observed_effect TEXT NOT NULL,
    refusal INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    turn_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    description TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    verified INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    mechanism TEXT NOT NULL,
    input_text TEXT NOT NULL,
    outcome TEXT NOT NULL,
    first_refusal INTEGER NOT NULL,
    score REAL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_target ON cases(target);
CREATE INDEX IF NOT EXISTS idx_cases_mechanism ON cases(mechanism);
CREATE INDEX IF NOT EXISTS idx_turns_case ON turns(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_attempts_case ON attempts(case_id);
CREATE TABLE IF NOT EXISTS challenge_intakes (
    intake_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL UNIQUE REFERENCES cases(case_id),
    authorization_scope TEXT NOT NULL,
    success_criteria_json TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    target_config_json TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_challenge_intakes_case ON challenge_intakes(case_id);
CREATE TABLE IF NOT EXISTS mechanism_cards (
    mechanism_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    match_terms_json TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    applicability_signals_json TEXT NOT NULL,
    preconditions_json TEXT NOT NULL,
    negative_signals_json TEXT NOT NULL,
    confidence TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mechanism_cards_category ON mechanism_cards(category);
CREATE TABLE IF NOT EXISTS mechanism_case_links (
    mechanism_id TEXT NOT NULL REFERENCES mechanism_cards(mechanism_id),
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    relation TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(mechanism_id, case_id)
);
CREATE INDEX IF NOT EXISTS idx_mechanism_case_links_case ON mechanism_case_links(case_id);
CREATE TABLE IF NOT EXISTS research_plans (
    plan_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    planner TEXT NOT NULL,
    status TEXT NOT NULL,
    hypotheses_json TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    context_json TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_research_plans_case ON research_plans(case_id);
CREATE TABLE IF NOT EXISTS defense_profiles (
    profile_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    scopes_json TEXT NOT NULL,
    assumptions_json TEXT NOT NULL,
    limitations_json TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS defense_observations (
    observation_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    profile_id TEXT NOT NULL REFERENCES defense_profiles(profile_id),
    run_id TEXT NOT NULL,
    expected_disposition TEXT NOT NULL,
    observed_disposition TEXT NOT NULL,
    language TEXT NOT NULL,
    carrier TEXT NOT NULL,
    latency_ms REAL,
    verified INTEGER NOT NULL,
    notes TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_defense_observations_profile ON defense_observations(profile_id);
CREATE INDEX IF NOT EXISTS idx_defense_observations_run ON defense_observations(run_id);
CREATE INDEX IF NOT EXISTS idx_defense_observations_case ON defense_observations(case_id);
"""


class MemoryStore:
    """Small SQLite-backed store for cases, conversation turns and evidence."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.db_path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def save_case(self, case: Case) -> Case:
        case.updated_at = utc_now()
        self._db.execute(
            """INSERT INTO cases
            (case_id,title,target,challenge,mechanism,carrier,impact,status,
             tags_json,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(case_id) DO UPDATE SET
              title=excluded.title, target=excluded.target,
              challenge=excluded.challenge, mechanism=excluded.mechanism,
              carrier=excluded.carrier, impact=excluded.impact,
              status=excluded.status, tags_json=excluded.tags_json,
              notes=excluded.notes, updated_at=excluded.updated_at""",
            (
                case.case_id,
                case.title,
                case.target,
                case.challenge,
                case.mechanism,
                case.carrier,
                case.impact,
                case.status,
                json.dumps(case.tags),
                case.notes,
                case.created_at,
                case.updated_at,
            ),
        )
        self._db.commit()
        return case

    def add_turn(self, turn: Turn) -> Turn:
        self._require_case(turn.case_id)
        self._db.execute(
            """INSERT INTO turns
            (turn_id,case_id,role,content,channel,provenance,observed_effect,
             refusal,metadata_json,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                turn.turn_id,
                turn.case_id,
                turn.role,
                turn.content,
                turn.channel,
                turn.provenance,
                turn.observed_effect,
                int(turn.refusal),
                json.dumps(turn.metadata, ensure_ascii=True),
                turn.created_at,
            ),
        )
        self._db.commit()
        return turn

    def add_evidence(self, evidence: Evidence) -> Evidence:
        self._require_case(evidence.case_id)
        self._db.execute(
            """INSERT INTO evidence
            (evidence_id,case_id,turn_id,kind,description,value,source,verified,
             metadata_json,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                evidence.evidence_id,
                evidence.case_id,
                evidence.turn_id,
                evidence.kind,
                evidence.description,
                evidence.value,
                evidence.source,
                int(evidence.verified),
                json.dumps(evidence.metadata, ensure_ascii=True),
                evidence.created_at,
            ),
        )
        self._db.commit()
        return evidence

    def add_attempt(self, attempt: Attempt) -> Attempt:
        self._require_case(attempt.case_id)
        self._db.execute(
            """INSERT INTO attempts
            (attempt_id,case_id,mechanism,input_text,outcome,first_refusal,score,
             notes,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                attempt.attempt_id,
                attempt.case_id,
                attempt.mechanism,
                attempt.input_text,
                attempt.outcome,
                int(attempt.first_refusal),
                attempt.score,
                attempt.notes,
                attempt.created_at,
            ),
        )
        self._db.commit()
        return attempt

    def save_challenge_intake(self, intake: ChallengeIntake) -> ChallengeIntake:
        """Create or replace the current structured brief for a Case."""
        self._require_case(intake.case_id)
        existing = self._db.execute(
            "SELECT intake_id, created_at FROM challenge_intakes WHERE case_id=?",
            (intake.case_id,),
        ).fetchone()
        if existing is not None:
            intake.intake_id = str(existing["intake_id"])
            intake.created_at = str(existing["created_at"])
        intake.updated_at = utc_now()
        self._db.execute(
            """INSERT INTO challenge_intakes
            (intake_id,case_id,authorization_scope,success_criteria_json,
             constraints_json,target_config_json,source,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(case_id) DO UPDATE SET
              authorization_scope=excluded.authorization_scope,
              success_criteria_json=excluded.success_criteria_json,
              constraints_json=excluded.constraints_json,
              target_config_json=excluded.target_config_json,
              source=excluded.source, updated_at=excluded.updated_at""",
            (
                intake.intake_id,
                intake.case_id,
                intake.authorization_scope,
                json.dumps(intake.success_criteria, ensure_ascii=True),
                json.dumps(intake.constraints, ensure_ascii=True),
                json.dumps(intake.target_config, ensure_ascii=True),
                intake.source,
                intake.created_at,
                intake.updated_at,
            ),
        )
        self._db.commit()
        return intake

    def get_challenge_intake(self, case_id: str) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT * FROM challenge_intakes WHERE case_id=?", (case_id,)
        ).fetchone()
        return self._decode_challenge_intake(row) if row is not None else None

    def save_mechanism_card(self, card: MechanismCard) -> MechanismCard:
        card.updated_at = utc_now()
        self._db.execute(
            """INSERT INTO mechanism_cards
            (mechanism_id,name,category,summary,match_terms_json,tags_json,
             applicability_signals_json,preconditions_json,negative_signals_json,
             confidence,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(mechanism_id) DO UPDATE SET
              name=excluded.name, category=excluded.category, summary=excluded.summary,
              match_terms_json=excluded.match_terms_json, tags_json=excluded.tags_json,
              applicability_signals_json=excluded.applicability_signals_json,
              preconditions_json=excluded.preconditions_json,
              negative_signals_json=excluded.negative_signals_json,
              confidence=excluded.confidence, notes=excluded.notes,
              updated_at=excluded.updated_at""",
            (
                card.mechanism_id, card.name, card.category, card.summary,
                json.dumps(card.match_terms, ensure_ascii=True), json.dumps(card.tags, ensure_ascii=True),
                json.dumps(card.applicability_signals, ensure_ascii=True),
                json.dumps(card.preconditions, ensure_ascii=True),
                json.dumps(card.negative_signals, ensure_ascii=True),
                card.confidence, card.notes, card.created_at, card.updated_at,
            ),
        )
        self._db.commit()
        return card

    def get_mechanism_card(self, mechanism_id: str) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT * FROM mechanism_cards WHERE mechanism_id=?", (mechanism_id,)
        ).fetchone()
        return self._decode_mechanism_card(row) if row is not None else None

    def list_mechanism_cards(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM mechanism_cards ORDER BY updated_at DESC"
        ).fetchall()
        return [self._decode_mechanism_card(row) for row in rows]

    def link_mechanism_case(
        self, mechanism_id: str, case_id: str, *, relation: str, notes: str = ""
    ) -> dict[str, Any]:
        if self.get_mechanism_card(mechanism_id) is None:
            raise KeyError(f"unknown mechanism: {mechanism_id}")
        self._require_case(case_id)
        self._db.execute(
            """INSERT INTO mechanism_case_links
            (mechanism_id,case_id,relation,notes,created_at) VALUES (?,?,?,?,?)
            ON CONFLICT(mechanism_id,case_id) DO UPDATE SET
              relation=excluded.relation, notes=excluded.notes,
              created_at=excluded.created_at""",
            (mechanism_id, case_id, relation, notes, utc_now()),
        )
        self._db.commit()
        return self.get_mechanism_case_link(mechanism_id, case_id)

    def get_mechanism_case_link(self, mechanism_id: str, case_id: str) -> dict[str, Any]:
        row = self._db.execute(
            """SELECT mechanism_id,case_id,relation,notes,created_at
            FROM mechanism_case_links WHERE mechanism_id=? AND case_id=?""",
            (mechanism_id, case_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"mechanism/case link not found: {mechanism_id} / {case_id}")
        return dict(row)

    def list_mechanism_case_links(
        self, *, mechanism_id: str | None = None, case_id: str | None = None
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[str] = []
        if mechanism_id:
            clauses.append("mechanism_id=?")
            values.append(mechanism_id)
        if case_id:
            clauses.append("case_id=?")
            values.append(case_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._db.execute(
            f"SELECT mechanism_id,case_id,relation,notes,created_at FROM mechanism_case_links{where} ORDER BY created_at DESC",
            values,
        ).fetchall()
        return [dict(row) for row in rows]

    def save_research_plan(self, plan: ResearchPlan) -> ResearchPlan:
        self._require_case(plan.case_id)
        plan.updated_at = utc_now()
        self._db.execute(
            """INSERT INTO research_plans
            (plan_id,case_id,planner,status,hypotheses_json,steps_json,context_json,
             notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(plan_id) DO UPDATE SET
              planner=excluded.planner, status=excluded.status,
              hypotheses_json=excluded.hypotheses_json, steps_json=excluded.steps_json,
              context_json=excluded.context_json, notes=excluded.notes,
              updated_at=excluded.updated_at""",
            (
                plan.plan_id, plan.case_id, plan.planner, plan.status,
                json.dumps(plan.hypotheses, ensure_ascii=True), json.dumps(plan.steps, ensure_ascii=True),
                json.dumps(plan.context, ensure_ascii=True), plan.notes,
                plan.created_at, plan.updated_at,
            ),
        )
        self._db.commit()
        return plan

    def get_research_plan(self, plan_id: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT * FROM research_plans WHERE plan_id=?", (plan_id,)).fetchone()
        return self._decode_research_plan(row) if row is not None else None

    def list_research_plans(self, case_id: str) -> list[dict[str, Any]]:
        self._require_case(case_id)
        rows = self._db.execute(
            "SELECT * FROM research_plans WHERE case_id=? ORDER BY updated_at DESC", (case_id,)
        ).fetchall()
        return [self._decode_research_plan(row) for row in rows]

    def save_defense_profile(self, profile: DefenseProfile) -> DefenseProfile:
        profile.updated_at = utc_now()
        self._db.execute(
            """INSERT INTO defense_profiles
            (profile_id,name,version,kind,source,scopes_json,assumptions_json,
             limitations_json,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(profile_id) DO UPDATE SET
              name=excluded.name, version=excluded.version, kind=excluded.kind,
              source=excluded.source, scopes_json=excluded.scopes_json,
              assumptions_json=excluded.assumptions_json,
              limitations_json=excluded.limitations_json, notes=excluded.notes,
              updated_at=excluded.updated_at""",
            (
                profile.profile_id, profile.name, profile.version, profile.kind, profile.source,
                json.dumps(profile.scopes), json.dumps(profile.assumptions),
                json.dumps(profile.limitations), profile.notes, profile.created_at, profile.updated_at,
            ),
        )
        self._db.commit()
        return profile

    def get_defense_profile(self, profile_id: str) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT * FROM defense_profiles WHERE profile_id=?", (profile_id,)
        ).fetchone()
        return self._decode_defense_profile(row) if row is not None else None

    def list_defense_profiles(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM defense_profiles ORDER BY updated_at DESC"
        ).fetchall()
        return [self._decode_defense_profile(row) for row in rows]

    def add_defense_observation(self, observation: DefenseObservation) -> DefenseObservation:
        self._require_case(observation.case_id)
        if self.get_defense_profile(observation.profile_id) is None:
            raise KeyError(f"unknown defense profile: {observation.profile_id}")
        self._db.execute(
            """INSERT INTO defense_observations
            (observation_id,case_id,profile_id,run_id,expected_disposition,
             observed_disposition,language,carrier,latency_ms,verified,notes,
             metadata_json,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                observation.observation_id, observation.case_id, observation.profile_id,
                observation.run_id, observation.expected_disposition,
                observation.observed_disposition, observation.language, observation.carrier,
                observation.latency_ms, int(observation.verified), observation.notes,
                json.dumps(observation.metadata, ensure_ascii=True), observation.created_at,
            ),
        )
        self._db.commit()
        return observation

    def list_defense_observations(
        self, *, profile_id: str | None = None, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[str] = []
        if profile_id:
            clauses.append("profile_id=?")
            values.append(profile_id)
        if run_id:
            clauses.append("run_id=?")
            values.append(run_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._db.execute(
            f"SELECT * FROM defense_observations{where} ORDER BY rowid", values
        ).fetchall()
        return [self._decode_defense_observation(row) for row in rows]

    def has_attempt(self, attempt_id: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM attempts WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        return row is not None

    def get_attempt(self, attempt_id: str) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if row is None:
            return None
        return self._decode_attempt(row)

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            return None
        return self._bundle_from_row(row)

    def list_cases(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self._db.execute(
                "SELECT * FROM cases WHERE status=? ORDER BY updated_at DESC", (status,)
            ).fetchall()
        else:
            rows = self._db.execute("SELECT * FROM cases ORDER BY updated_at DESC").fetchall()
        return [self._bundle_from_row(row, include_children=False) for row in rows]

    def search(self, query: str) -> list[dict[str, Any]]:
        needle = f"%{query}%"
        rows = self._db.execute(
            """SELECT DISTINCT c.* FROM cases c
            LEFT JOIN turns t ON t.case_id=c.case_id
            LEFT JOIN evidence e ON e.case_id=c.case_id
            LEFT JOIN attempts a ON a.case_id=c.case_id
            WHERE c.title LIKE ? OR c.target LIKE ? OR c.challenge LIKE ?
              OR c.mechanism LIKE ? OR c.carrier LIKE ? OR c.impact LIKE ?
              OR c.notes LIKE ? OR t.content LIKE ? OR e.description LIKE ?
              OR e.value LIKE ? OR a.input_text LIKE ? OR a.notes LIKE ?
            ORDER BY c.updated_at DESC""",
            (needle,) * 12,
        ).fetchall()
        return [self._bundle_from_row(row, include_children=False) for row in rows]

    def import_cases(
        self,
        records: Iterable[dict[str, Any]],
        *,
        preserve_existing_status: bool = True,
    ) -> list[Case]:
        imported: list[Case] = []
        for record in records:
            existing = self._db.execute(
                "SELECT status, created_at FROM cases WHERE case_id=?",
                (record.get("case_id") or record.get("id"),),
            ).fetchone()
            status = record.get("status", "open")
            created_at = record.get("created_at") or utc_now()
            if preserve_existing_status and existing is not None:
                status = str(existing["status"])
                created_at = str(existing["created_at"])
            case = Case(
                case_id=record.get("case_id") or record.get("id") or new_id("case"),
                title=record["title"],
                target=record.get("target", ""),
                challenge=record.get("challenge", ""),
                mechanism=record.get("mechanism", ""),
                carrier=record.get("carrier", ""),
                impact=record.get("impact", ""),
                status=status,
                tags=list(record.get("tags", [])),
                notes=record.get("notes", ""),
                created_at=created_at,
                updated_at=record.get("updated_at") or utc_now(),
            )
            self.save_case(case)
            imported.append(case)
        return imported

    def export_bundle(self, case_id: str) -> dict[str, Any]:
        bundle = self.get_case(case_id)
        if bundle is None:
            raise KeyError(f"unknown case: {case_id}")
        return bundle

    def _require_case(self, case_id: str) -> None:
        row = self._db.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown case: {case_id}")

    def _bundle_from_row(self, row: sqlite3.Row, include_children: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = dict(row)
        result["tags"] = json.loads(result.pop("tags_json"))
        if not include_children:
            return result
        case_id = result["case_id"]
        turns = self._db.execute(
            "SELECT * FROM turns WHERE case_id=? ORDER BY rowid", (case_id,)
        ).fetchall()
        evidence = self._db.execute(
            "SELECT * FROM evidence WHERE case_id=? ORDER BY rowid", (case_id,)
        ).fetchall()
        attempts = self._db.execute(
            "SELECT * FROM attempts WHERE case_id=? ORDER BY rowid", (case_id,)
        ).fetchall()
        result["turns"] = [self._decode_turn(row) for row in turns]
        result["evidence"] = [self._decode_evidence(row) for row in evidence]
        result["attempts"] = [self._decode_attempt(row) for row in attempts]
        result["intake"] = self.get_challenge_intake(case_id)
        result["mechanism_links"] = self.list_mechanism_case_links(case_id=case_id)
        result["plans"] = self.list_research_plans(case_id)
        return result

    @staticmethod
    def _decode_turn(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["refusal"] = bool(result["refusal"])
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    @staticmethod
    def _decode_evidence(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["verified"] = bool(result["verified"])
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    @staticmethod
    def _decode_attempt(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["first_refusal"] = bool(result["first_refusal"])
        return result

    @staticmethod
    def _decode_challenge_intake(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["success_criteria"] = json.loads(result.pop("success_criteria_json"))
        result["constraints"] = json.loads(result.pop("constraints_json"))
        result["target_config"] = json.loads(result.pop("target_config_json"))
        return result

    @staticmethod
    def _decode_mechanism_card(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for key in (
            "match_terms_json", "tags_json", "applicability_signals_json",
            "preconditions_json", "negative_signals_json",
        ):
            result[key.removesuffix("_json")] = json.loads(result.pop(key))
        return result

    @staticmethod
    def _decode_research_plan(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["hypotheses"] = json.loads(result.pop("hypotheses_json"))
        result["steps"] = json.loads(result.pop("steps_json"))
        result["context"] = json.loads(result.pop("context_json"))
        return result

    @staticmethod
    def _decode_defense_profile(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["scopes"] = json.loads(result.pop("scopes_json"))
        result["assumptions"] = json.loads(result.pop("assumptions_json"))
        result["limitations"] = json.loads(result.pop("limitations_json"))
        return result

    @staticmethod
    def _decode_defense_observation(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["verified"] = bool(result["verified"])
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result
