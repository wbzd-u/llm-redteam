from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .models import Attempt, Case, Evidence, Turn, new_id, utc_now


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
