"""Small bridge for the local, offline PyRIT learning demonstration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = PROJECT_ROOT / "scripts" / "pyrit_quickstart_demo.py"


def _default_pyrit_python() -> Path:
    configured = os.environ.get("PYRIT_PYTHON")
    if configured:
        return Path(configured)
    root = Path(os.environ.get("PYRIT_ROOT", Path.home() / "ai_redteam_tools" / "pyrit"))
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run_native_demo(payload: dict[str, Any], *, python_executable: str | Path | None = None) -> dict[str, Any]:
    """Run PyRIT's PromptSendingAttack against its offline TextTarget.

    The PyRIT dependency deliberately stays in its own virtual environment.
    No target URL, cookie, header, API key, or user task data is accepted here.
    """
    prompt = str(payload.get("prompt", "")).strip()
    converter = str(payload.get("converter", "raw")).strip() or "raw"
    if not prompt:
        raise ValueError("prompt is required")
    if len(prompt) > 2000:
        raise ValueError("prompt is too long for the quickstart demo")
    if converter not in {"raw", "base64"}:
        raise ValueError("converter must be raw or base64")

    executable = Path(python_executable) if python_executable else _default_pyrit_python()
    if not executable.is_file():
        raise RuntimeError("PyRIT Python environment was not found; set PYRIT_PYTHON to its python executable")
    completed = subprocess.run(
        [str(executable), str(DEMO_SCRIPT)],
        input=json.dumps({"prompt": prompt, "converter": converter,}, ensure_ascii=True).encode("utf-8"),
        capture_output=True,
        timeout=30,
        check=False,
    )
    try:
        data = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("PyRIT quickstart returned invalid output") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(str(data.get("error") or stderr or "PyRIT quickstart failed"))
    return data
