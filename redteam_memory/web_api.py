"""Local-only HTTP API for the React workbench dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .mechanisms import recommend_mechanisms
from .models import Attempt, Case, ChallengeIntake, Evidence, Turn
from .planner import deterministic_draft
from .research import case_rows, paper_packet, research_cross_tabs, research_summary
from .state import recommend_next
from .store import MemoryStore


def create_app(db_path: str | Path):
    """Create the API lazily so the CLI core has no FastAPI dependency."""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError as exc:
        raise RuntimeError(
            "Dashboard API dependencies are missing. Install with: pip install -e .[dashboard]"
        ) from exc

    app = FastAPI(title="LLM Red Team Workbench API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    def with_store() -> MemoryStore:
        return MemoryStore(db_path)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "db_path": str(db_path)}

    @app.get("/api/overview")
    def overview(source: str | None = None) -> dict[str, Any]:
        with with_store() as store:
            rows = case_rows(store, source=source)
            return {
                "summary": research_summary(store, source=source),
                "recent_cases": sorted(rows, key=lambda item: item["case_id"], reverse=True)[:8],
            }

    @app.get("/api/cases")
    def cases(source: str | None = None) -> list[dict[str, Any]]:
        with with_store() as store:
            return case_rows(store, source=source)

    @app.get("/api/cases/{case_id}")
    def case_detail(case_id: str) -> dict[str, Any]:
        with with_store() as store:
            bundle = store.get_case(case_id)
        if bundle is None:
            raise HTTPException(status_code=404, detail="unknown case")
        return bundle

    @app.get("/api/tasks/{case_id}/workspace")
    def task_workspace(case_id: str) -> dict[str, Any]:
        with with_store() as store:
            bundle = store.get_case(case_id)
            if bundle is None:
                raise HTTPException(status_code=404, detail="unknown task")
            return {
                "task": bundle,
                "recommended_mechanisms": recommend_mechanisms(store, case_id, limit=5),
                "next_action": recommend_next(bundle).to_dict(),
                "suggested_plan": deterministic_draft(store, case_id).to_dict() if not bundle.get("plans") else None,
            }

    @app.post("/api/tasks")
    def create_task(payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title", "")).strip()
        if not title:
            raise HTTPException(status_code=422, detail="title is required")
        tags = [str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()]
        if not any(tag.casefold().startswith("source:") for tag in tags):
            tags.append("source:user-kb")
        with with_store() as store:
            case = store.save_case(Case(
                title=title,
                target=str(payload.get("target", "")).strip(),
                challenge=str(payload.get("challenge", "")).strip(),
                carrier=str(payload.get("carrier", "text")).strip() or "text",
                impact=str(payload.get("impact", "")).strip(),
                status="open", tags=tags, notes=str(payload.get("notes", "")).strip(),
            ))
            store.save_challenge_intake(ChallengeIntake(
                case_id=case.case_id,
                authorization_scope=str(payload.get("authorization_scope", "")).strip(),
                success_criteria=[str(item).strip() for item in payload.get("success_criteria", []) if str(item).strip()],
                constraints=[str(item).strip() for item in payload.get("constraints", []) if str(item).strip()],
                source="dashboard",
            ))
            return {"case_id": case.case_id}

    @app.post("/api/tasks/{case_id}/plan/draft")
    def create_task_draft(case_id: str) -> dict[str, Any]:
        with with_store() as store:
            if store.get_case(case_id) is None:
                raise HTTPException(status_code=404, detail="unknown task")
            return store.save_research_plan(deterministic_draft(store, case_id)).to_dict()

    @app.post("/api/tasks/{case_id}/observation")
    def add_task_observation(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response_text = str(payload.get("response_text", "")).strip()
        if not response_text:
            raise HTTPException(status_code=422, detail="response_text is required")
        input_text = str(payload.get("input_text", "")).strip()
        mechanism = str(payload.get("mechanism", "baseline")).strip() or "baseline"
        outcome = str(payload.get("outcome", "unknown")).strip() or "unknown"
        refusal = bool(payload.get("refusal", False))
        observed_effect = str(payload.get("observed_effect", "")).strip()
        with with_store() as store:
            if store.get_case(case_id) is None:
                raise HTTPException(status_code=404, detail="unknown task")
            input_turn = store.add_turn(Turn(case_id=case_id, role="user", content=input_text, provenance="manual-dashboard")) if input_text else None
            response_turn = store.add_turn(Turn(
                case_id=case_id, role="assistant", content=response_text, provenance="manual-dashboard",
                observed_effect=observed_effect, refusal=refusal,
            ))
            attempt = store.add_attempt(Attempt(
                case_id=case_id, mechanism=mechanism, input_text=input_text or "[manual observation]",
                outcome=outcome, first_refusal=refusal, notes=observed_effect,
            ))
            evidence_description = str(payload.get("evidence_description", "")).strip()
            evidence = None
            if evidence_description:
                evidence = store.add_evidence(Evidence(
                    case_id=case_id, turn_id=response_turn.turn_id,
                    kind=str(payload.get("evidence_kind", "manual")).strip() or "manual",
                    description=evidence_description, source="manual-dashboard",
                    verified=bool(payload.get("evidence_verified", False)),
                    metadata={"confirms_impact": bool(payload.get("confirms_impact", False))},
                ))
            bundle = store.get_case(case_id)
            assert bundle is not None
            return {
                "input_turn_id": input_turn.turn_id if input_turn else None,
                "response_turn_id": response_turn.turn_id, "attempt_id": attempt.attempt_id,
                "evidence_id": evidence.evidence_id if evidence else None,
                "next_action": recommend_next(bundle).to_dict(),
            }

    @app.get("/api/mechanisms")
    def mechanisms() -> list[dict[str, Any]]:
        with with_store() as store:
            return store.list_mechanism_cards()

    @app.get("/api/research/summary")
    def research(source: str | None = None) -> dict[str, Any]:
        with with_store() as store:
            return research_summary(store, source=source)

    @app.get("/api/research/paper-packet")
    def research_paper_packet(source: str | None = None) -> dict[str, Any]:
        with with_store() as store:
            return paper_packet(store, source=source)

    @app.get("/api/research/cross-tabs")
    def research_cross_tabulations(source: str | None = None) -> dict[str, Any]:
        with with_store() as store:
            return research_cross_tabs(store, source=source)

    return app
