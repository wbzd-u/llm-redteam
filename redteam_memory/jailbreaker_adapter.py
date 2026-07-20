from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .models import Attempt, Case
from .store import MemoryStore


class JailbreakerCEAdapter:
    """Subprocess adapter for Jailbreaker-CE's local attack registry."""

    def __init__(
        self,
        repo_path: str | Path,
        *,
        python_executable: str | Path | None = None,
        bridge_path: str | Path | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.python_executable = str(python_executable or sys.executable)
        self.bridge_path = Path(bridge_path or Path(__file__).resolve().parents[1] / "scripts" / "jailbreaker_ce_bridge.py")
        if not self.repo_path.is_dir():
            raise ValueError(f"Jailbreaker-CE repo does not exist: {self.repo_path}")

    def _run(self, args: list[str]) -> Any:
        completed = subprocess.run(
            [self.python_executable, str(self.bridge_path), "--repo", str(self.repo_path), *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"Jailbreaker-CE bridge failed ({completed.returncode}): {detail}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Jailbreaker-CE bridge returned invalid JSON") from exc

    def list_techniques(self) -> list[dict[str, Any]]:
        return list(self._run(["list"]))

    def generate_case(
        self,
        *,
        technique: str,
        intent: str,
        target_id: str = "offline-target",
        seed_prompt: str | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        args = ["generate", "--technique", technique, "--intent", intent, "--target-id", target_id]
        if seed_prompt is not None:
            args.extend(["--seed-prompt", seed_prompt])
        if system_prompt is not None:
            args.extend(["--system-prompt", system_prompt])
        return dict(self._run(args))

    def seed_case(
        self,
        store: MemoryStore,
        *,
        technique: str,
        intent: str,
        target_id: str = "offline-target",
        seed_prompt: str | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        generated = self.generate_case(
            technique=technique,
            intent=intent,
            target_id=target_id,
            seed_prompt=seed_prompt,
            system_prompt=system_prompt,
        )
        metadata = generated.get("metadata", {})
        digest = hashlib.sha256(
            f"{technique}\0{target_id}\0{intent}\0{seed_prompt or ''}".encode("utf-8")
        ).hexdigest()[:16]
        case_id = f"jbc-{digest}"
        messages = generated.get("rendered_messages", [])
        carrier = "multi-turn chat" if len(messages) > 1 else "chat"
        if generated.get("untrusted_documents"):
            carrier = "untrusted document"
        case = Case(
            case_id=case_id,
            title=f"Jailbreaker-CE seed: {technique}",
            target=target_id,
            challenge="Jailbreaker-CE",
            mechanism=f"{metadata.get('family', 'unknown')}:{technique}",
            carrier=carrier,
            impact="model or agent behavior boundary",
            status="seed",
            tags=["jailbreaker-ce", str(metadata.get("family", "unknown"))],
            notes=(
                "Generated offline from Jailbreaker-CE attack registry. "
                "This is a seed case, not evidence of a successful break. "
                + str(generated.get("instructions", ""))
            ),
        )
        existed = store.get_case(case_id) is not None
        store.save_case(case)
        attempt_id = f"{case_id}-attempt"
        if not store.has_attempt(attempt_id):
            rendered_input = json.dumps(messages, ensure_ascii=False, indent=2)
            store.add_attempt(Attempt(
                attempt_id=attempt_id,
                case_id=case_id,
                mechanism=case.mechanism,
                input_text=rendered_input,
                outcome="unknown",
                notes="Generated seed; inspect rendered_messages before execution.",
            ))
        return {
            "case_id": case_id,
            "created": not existed,
            "technique": technique,
            "message_count": len(messages),
            "metadata": metadata,
        }

