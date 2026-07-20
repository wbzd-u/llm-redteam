"""Local-only HTTP API for the React workbench dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .research import case_rows, research_summary
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
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    def with_store() -> MemoryStore:
        return MemoryStore(db_path)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "db_path": str(db_path)}

    @app.get("/api/overview")
    def overview() -> dict[str, Any]:
        with with_store() as store:
            rows = case_rows(store)
            return {
                "summary": research_summary(store),
                "recent_cases": sorted(rows, key=lambda item: item["case_id"], reverse=True)[:8],
            }

    @app.get("/api/cases")
    def cases() -> list[dict[str, Any]]:
        with with_store() as store:
            return case_rows(store)

    @app.get("/api/cases/{case_id}")
    def case_detail(case_id: str) -> dict[str, Any]:
        with with_store() as store:
            bundle = store.get_case(case_id)
        if bundle is None:
            raise HTTPException(status_code=404, detail="unknown case")
        return bundle

    @app.get("/api/mechanisms")
    def mechanisms() -> list[dict[str, Any]]:
        with with_store() as store:
            return store.list_mechanism_cards()

    @app.get("/api/research/summary")
    def research() -> dict[str, Any]:
        with with_store() as store:
            return research_summary(store)

    return app
