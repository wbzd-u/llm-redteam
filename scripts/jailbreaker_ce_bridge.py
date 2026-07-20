from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _load(repo: Path) -> Any:
    backend = repo / "backend"
    if not backend.is_dir():
        raise SystemExit(f"Jailbreaker-CE backend not found: {backend}")
    sys.path.insert(0, str(backend))
    from app.attacklib import (  # type: ignore[import-not-found]
        AttackBuildRequest,
        get_attack_technique,
        list_attack_techniques,
        render_prompt,
    )
    from app.attacklib.renderer import render_scripted_turns  # type: ignore[import-not-found]
    return AttackBuildRequest, get_attack_technique, list_attack_techniques, render_prompt, render_scripted_turns


def main() -> None:
    parser = argparse.ArgumentParser(description="Jailbreaker-CE offline bridge")
    parser.add_argument("--repo", required=True)
    parser.add_argument("action", choices=["list", "generate"])
    parser.add_argument("--technique")
    parser.add_argument("--intent", default="authorized safety boundary probe")
    parser.add_argument("--target-id", default="offline-target")
    parser.add_argument("--seed-prompt", default=None)
    parser.add_argument("--system-prompt", default=None)
    args = parser.parse_args()

    AttackBuildRequest, get_attack_technique, list_attack_techniques, render_prompt, render_scripted_turns = _load(
        Path(args.repo).resolve()
    )
    if args.action == "list":
        output = []
        for technique in list_attack_techniques():
            output.append(_jsonable(technique.metadata))
        print(json.dumps(output, ensure_ascii=False))
        return

    if not args.technique:
        raise SystemExit("generate requires --technique")
    attack = get_attack_technique(args.technique)()
    request = AttackBuildRequest(
        target_id=args.target_id,
        unsafe_intent_label=args.intent,
        seed_prompt=args.seed_prompt,
    )
    case = attack.build_case(request)
    if case.conversation_turns:
        rendered = render_scripted_turns(case, system_prompt=args.system_prompt)
    else:
        rendered = render_prompt(case, system_prompt=args.system_prompt)
    output = {
        "technique_key": case.technique_key,
        "target_id": case.target_id,
        "unsafe_intent_label": case.unsafe_intent_label,
        "instructions": case.instructions,
        "assets": case.assets,
        "notes": list(case.notes),
        "conversation_turns": list(case.conversation_turns),
        "untrusted_documents": list(case.untrusted_documents),
        "workspace_files": list(case.workspace_files),
        "generation_overrides": case.generation_overrides,
        "rendered_messages": rendered,
        "metadata": _jsonable(attack.metadata),
    }
    print(json.dumps(_jsonable(output), ensure_ascii=False))


if __name__ == "__main__":
    main()
