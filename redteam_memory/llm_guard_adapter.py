"""Subprocess adapter for an isolated, local LLM Guard installation."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from .models import DefenseObservation
from .store import MemoryStore


class LLMGuardAdapter:
    """Run the local LLM Guard bridge without importing its dependencies."""

    def __init__(
        self,
        *,
        repo: str | Path,
        python_executable: str | Path | None = None,
        scanner: str = "PromptInjection",
        threshold: float | None = None,
        match_type: str | None = None,
        use_onnx: bool = False,
        bridge_script: str | Path | None = None,
        timeout: float = 600.0,
    ) -> None:
        self.repo = Path(repo).resolve()
        if not self.repo.is_dir():
            raise ValueError(f"LLM Guard repo does not exist: {self.repo}")
        self.python_executable = str(python_executable or sys.executable)
        self.scanner = scanner
        self.threshold = threshold
        self.match_type = match_type
        self.use_onnx = use_onnx
        self.bridge_script = Path(bridge_script or Path(__file__).resolve().parents[1] / "scripts" / "llm_guard_bridge.py").resolve()
        if not self.bridge_script.is_file():
            raise ValueError(f"LLM Guard bridge does not exist: {self.bridge_script}")
        self.timeout = timeout

    def scan(self, prompt: str) -> dict[str, Any]:
        request: dict[str, Any] = {
            "prompt": prompt,
            "scanner": self.scanner,
            "use_onnx": self.use_onnx,
        }
        if self.threshold is not None:
            request["threshold"] = self.threshold
        if self.match_type is not None:
            request["match_type"] = self.match_type
        try:
            child_env = os.environ.copy()
            child_env.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
            child_env.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
            completed = subprocess.run(
                [self.python_executable, str(self.bridge_script), "--repo", str(self.repo)],
                input=json.dumps(request, ensure_ascii=False),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=child_env,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"LLM Guard scan timed out after {self.timeout:.1f} seconds") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"LLM Guard bridge failed ({completed.returncode}): {detail}")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM Guard bridge returned invalid JSON") from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError(str(result.get("error", "LLM Guard scan failed")))
        return result

    async def scan_async(self, prompt: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.scan, prompt)


def record_llm_guard_observation(
    store: MemoryStore,
    *,
    case_id: str,
    profile_id: str,
    run_id: str,
    expected_disposition: str,
    result: dict[str, Any],
    language: str = "und",
    carrier: str = "text",
    verified: bool = False,
    notes: str = "",
) -> DefenseObservation:
    """Convert one scanner result into the common defense observation schema."""
    if not isinstance(result.get("valid"), bool):
        raise ValueError("LLM Guard result must contain boolean 'valid'")
    observed = "allow" if result["valid"] else "block"
    return store.add_defense_observation(DefenseObservation(
        case_id=case_id,
        profile_id=profile_id,
        run_id=run_id,
        expected_disposition=expected_disposition,
        observed_disposition=observed,
        language=language,
        carrier=carrier,
        latency_ms=float(result["latency_ms"]) if result.get("latency_ms") is not None else None,
        verified=verified,
        notes=notes or "LLM Guard observation",
        metadata={
            "adapter": "llm_guard",
            "scanner": result.get("scanner", ""),
            "risk_score": result.get("risk_score"),
            "sanitized_changed": result.get("sanitized_prompt") != result.get("prompt"),
        },
    ))
