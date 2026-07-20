"""JSONL bridge executed inside the isolated LLM Guard environment.

Input is one JSON object on stdin. Output is one JSON object on stdout. The
bridge intentionally exposes only scanner results, not model internals.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


def build_scanner(request: dict):
    from llm_guard import input_scanners

    scanner_name = request.get("scanner", "PromptInjection")
    if scanner_name != "PromptInjection":
        raise ValueError("initial bridge supports only the PromptInjection scanner")
    kwargs = {"use_onnx": bool(request.get("use_onnx", False))}
    if request.get("threshold") is not None:
        kwargs["threshold"] = float(request["threshold"])
    if request.get("match_type") is not None:
        kwargs["match_type"] = request["match_type"]
    return input_scanners.PromptInjection(**kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM Guard local JSON bridge")
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        raise SystemExit(f"repo does not exist: {repo}")
    sys.path.insert(0, str(repo))
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict) or not isinstance(request.get("prompt"), str):
            raise ValueError("request must contain a string prompt")
        scanner = build_scanner(request)
        started = time.perf_counter()
        sanitized, valid, risk_score = scanner.scan(request["prompt"])
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        print(json.dumps({
            "ok": True,
            "scanner": request.get("scanner", "PromptInjection"),
            "prompt": request["prompt"],
            "sanitized_prompt": sanitized,
            "valid": bool(valid),
            "risk_score": risk_score,
            "latency_ms": latency_ms,
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
