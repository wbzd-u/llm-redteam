from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .adapters import build_inspect_sample, build_promptfoo_config
from .grayswan import GraySwanTarget
from .markdown_import import parse_break_log
from .models import Attempt, Case, Evidence, Turn
from .ipi_import import import_ipi_dataset
from .jailbreaker_adapter import JailbreakerCEAdapter
from .runner import run_once
from .state import minimize_bundle, recommend_next
from .store import MemoryStore
from .targets import PyRITHTTPTarget, ReplayTarget


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "redteam_memory.sqlite3"


def _json(value: Any) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _content(args: argparse.Namespace) -> str:
    if args.content_file:
        return Path(args.content_file).read_text(encoding="utf-8")
    return args.content or ""


def _input_text(args: argparse.Namespace) -> str:
    if getattr(args, "input_file", None):
        return Path(args.input_file).read_text(encoding="utf-8")
    return args.input or ""


def _load_headers_file(path: str | Path) -> dict[str, str]:
    source = Path(path)
    if not source.name.endswith(".headers.json"):
        raise SystemExit("headers file must use the .headers.json suffix so it remains ignored by Git")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"headers file does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"headers file is not valid JSON: {source}") from exc
    if not isinstance(raw, dict) or not raw:
        raise SystemExit("headers file must contain a non-empty JSON object")
    headers: dict[str, str] = {}
    for key, value in raw.items():
        if (
            not isinstance(key, str)
            or not key.strip()
            or key != key.strip()
            or not isinstance(value, str)
            or not value
        ):
            raise SystemExit("headers file keys and values must be non-empty strings")
        if "\r" in key or "\n" in key or "\r" in value or "\n" in value:
            raise SystemExit("headers file contains an invalid newline in a header")
        headers[key] = value
    return headers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evidence-first LLM red-team memory")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="initialize the database")

    case = sub.add_parser("case", help="manage cases")
    case_sub = case.add_subparsers(dest="case_command", required=True)
    case_add = case_sub.add_parser("add")
    case_add.add_argument("--title", required=True)
    case_add.add_argument("--target", default="")
    case_add.add_argument("--challenge", default="")
    case_add.add_argument("--mechanism", default="")
    case_add.add_argument("--carrier", default="")
    case_add.add_argument("--impact", default="")
    case_add.add_argument("--status", default="open")
    case_add.add_argument("--tag", action="append", default=[])
    case_add.add_argument("--notes", default="")
    case_sub.add_parser("list").add_argument("--status", default=None)

    turn = sub.add_parser("turn", help="record a conversation turn")
    turn_sub = turn.add_subparsers(dest="turn_command", required=True)
    turn_add = turn_sub.add_parser("add")
    turn_add.add_argument("--case-id", required=True)
    turn_add.add_argument("--role", required=True)
    turn_add.add_argument("--content")
    turn_add.add_argument("--content-file")
    turn_add.add_argument("--channel", default="chat")
    turn_add.add_argument("--provenance", default="unknown")
    turn_add.add_argument("--observed-effect", default="")
    turn_add.add_argument("--refusal", action="store_true")

    evidence = sub.add_parser("evidence", help="record runtime or evaluator evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_add = evidence_sub.add_parser("add")
    evidence_add.add_argument("--case-id", required=True)
    evidence_add.add_argument("--kind", required=True)
    evidence_add.add_argument("--description", required=True)
    evidence_add.add_argument("--value", default="")
    evidence_add.add_argument("--source", default="")
    evidence_add.add_argument("--turn-id", default="")
    evidence_add.add_argument("--verified", action="store_true")

    attempt = sub.add_parser("attempt", help="record one mechanism attempt")
    attempt_sub = attempt.add_subparsers(dest="attempt_command", required=True)
    attempt_add = attempt_sub.add_parser("add")
    attempt_add.add_argument("--case-id", required=True)
    attempt_add.add_argument("--mechanism", required=True)
    attempt_add.add_argument("--input", required=True)
    attempt_add.add_argument("--outcome", default="unknown")
    attempt_add.add_argument("--first-refusal", action="store_true")
    attempt_add.add_argument("--score", type=float, default=None)
    attempt_add.add_argument("--notes", default="")

    show = sub.add_parser("show", help="show a complete case bundle")
    show.add_argument("case_id")
    search = sub.add_parser("search", help="search case metadata and recorded text")
    search.add_argument("query")

    recommend = sub.add_parser("recommend", help="recommend a conservative next experiment")
    recommend.add_argument("case_id")

    compact = sub.add_parser("compact", help="export a redacted evidence-minimal case view")
    compact.add_argument("case_id")

    run = sub.add_parser("run", help="execute one controlled target interaction")
    run_sub = run.add_subparsers(dest="run_command", required=True)
    replay = run_sub.add_parser("replay", help="run against a deterministic offline response")
    replay.add_argument("--case-id", required=True)
    replay.add_argument("--mechanism", default=None)
    replay.add_argument("--input")
    replay.add_argument("--input-file")
    replay.add_argument("--attempt-id", default=None)
    replay.add_argument("--response")
    replay.add_argument("--response-file")
    replay.add_argument("--outcome", default="unknown")
    replay.add_argument("--refusal", action="store_true")
    replay.add_argument("--observed-effect", default="")
    replay.add_argument("--conversation-id", default=None)

    pyrit_http = run_sub.add_parser("pyrit-http", help="run through PyRIT HTTPTarget")
    pyrit_http.add_argument("--case-id", required=True)
    pyrit_http.add_argument("--mechanism", default=None)
    pyrit_http.add_argument("--request-file", required=True)
    pyrit_http.add_argument("--input")
    pyrit_http.add_argument("--input-file")
    pyrit_http.add_argument("--attempt-id", default=None)
    pyrit_http.add_argument("--placeholder", default="{PROMPT}")
    pyrit_http.add_argument("--response-key", default=None)
    pyrit_http.add_argument("--prompt-encoding", choices=["raw", "json", "url"], default="raw")
    pyrit_http.add_argument("--model-name", default="")
    pyrit_http.add_argument("--timeout", type=float, default=30.0)
    pyrit_http.add_argument("--conversation-id", default=None)
    pyrit_http.add_argument("--outcome", default="unknown")
    pyrit_http.add_argument("--refusal", action="store_true")
    pyrit_http.add_argument("--observed-effect", default="")
    pyrit_http.add_argument("--no-tls", action="store_true")
    pyrit_http.add_argument(
        "--execute",
        action="store_true",
        help="required to permit the network request; without it only configuration is checked",
    )

    grayswan = run_sub.add_parser("grayswan", help="run through the GraySwan challenge endpoint")
    grayswan.add_argument("--case-id", required=True)
    grayswan.add_argument("--mechanism", default=None)
    grayswan.add_argument("--input")
    grayswan.add_argument("--input-file")
    grayswan.add_argument("--attempt-id", default=None)
    grayswan.add_argument("--model", required=True)
    grayswan.add_argument("--association-id", required=True)
    grayswan.add_argument("--behavior-id", required=True)
    grayswan.add_argument("--challenge-id", required=True)
    grayswan.add_argument("--chat-id", default=None, help="existing GraySwan chat ID; omit for a new chat")
    grayswan.add_argument(
        "--headers-file",
        required=True,
        help="JSON object containing runtime request headers; values are never printed",
    )
    grayswan.add_argument("--parent-id", default=None)
    grayswan.add_argument("--timeout", type=float, default=45.0)
    grayswan.add_argument("--outcome", default="unknown")
    grayswan.add_argument("--refusal", action="store_true")
    grayswan.add_argument("--observed-effect", default="")
    grayswan.add_argument(
        "--execute",
        action="store_true",
        help="required to permit the network request; without it credentials are not loaded",
    )

    seed = sub.add_parser("seed", help="import case metadata from JSON")
    seed.add_argument("json_file")

    import_log = sub.add_parser("import-log", help="import ID-labelled cases from a Markdown break log")
    import_log.add_argument("markdown_file")
    import_log.add_argument("--full", action="store_true", help="print full imported case records")

    import_ipi = sub.add_parser("import-ipi", help="import IPI Arena JSONL attacks as seed cases")
    import_ipi.add_argument("jsonl_file")
    import_ipi.add_argument("--limit", type=int, default=None)

    jailbreaker = sub.add_parser("jailbreaker", help="use Jailbreaker-CE offline attack registry")
    jailbreaker_sub = jailbreaker.add_subparsers(dest="jailbreaker_command", required=True)
    jailbreaker_list = jailbreaker_sub.add_parser("list")
    jailbreaker_list.add_argument("--repo", required=True)
    jailbreaker_list.add_argument("--python", dest="python_executable", default=None)
    jailbreaker_seed = jailbreaker_sub.add_parser("seed")
    jailbreaker_seed.add_argument("--repo", required=True)
    jailbreaker_seed.add_argument("--python", dest="python_executable", default=None)
    jailbreaker_seed.add_argument("--technique", required=True)
    jailbreaker_seed.add_argument("--intent", required=True)
    jailbreaker_seed.add_argument("--target-id", default="offline-target")
    jailbreaker_seed.add_argument("--seed-prompt", default=None)
    jailbreaker_seed.add_argument("--system-prompt", default=None)

    export = sub.add_parser("export", help="export a case as an experiment artifact")
    export.add_argument("format", choices=["inspect", "promptfoo"])
    export.add_argument("--case-id", action="append", required=True)
    export.add_argument("--out", required=True)
    export.add_argument("--include-empty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    with MemoryStore(args.db) as store:
        if args.command == "init":
            print(f"initialized {args.db}")
            return
        if args.command == "case":
            if args.case_command == "add":
                _json(store.save_case(Case(
                    title=args.title,
                    target=args.target,
                    challenge=args.challenge,
                    mechanism=args.mechanism,
                    carrier=args.carrier,
                    impact=args.impact,
                    status=args.status,
                    tags=args.tag,
                    notes=args.notes,
                )).to_dict())
            else:
                _json(store.list_cases(args.status))
            return
        if args.command == "turn":
            _json(store.add_turn(Turn(
                case_id=args.case_id,
                role=args.role,
                content=_content(args),
                channel=args.channel,
                provenance=args.provenance,
                observed_effect=args.observed_effect,
                refusal=args.refusal,
            )).to_dict())
            return
        if args.command == "evidence":
            _json(store.add_evidence(Evidence(
                case_id=args.case_id,
                kind=args.kind,
                description=args.description,
                value=args.value,
                source=args.source,
                turn_id=args.turn_id,
                verified=args.verified,
            )).to_dict())
            return
        if args.command == "attempt":
            _json(store.add_attempt(Attempt(
                case_id=args.case_id,
                mechanism=args.mechanism,
                input_text=args.input,
                outcome=args.outcome,
                first_refusal=args.first_refusal,
                score=args.score,
                notes=args.notes,
            )).to_dict())
            return
        if args.command == "show":
            bundle = store.get_case(args.case_id)
            if bundle is None:
                raise SystemExit(f"unknown case: {args.case_id}")
            _json(bundle)
            return
        if args.command == "search":
            _json(store.search(args.query))
            return
        if args.command == "recommend":
            bundle = store.get_case(args.case_id)
            if bundle is None:
                raise SystemExit(f"unknown case: {args.case_id}")
            _json(recommend_next(bundle).to_dict())
            return
        if args.command == "compact":
            bundle = store.get_case(args.case_id)
            if bundle is None:
                raise SystemExit(f"unknown case: {args.case_id}")
            _json(minimize_bundle(bundle))
            return
        if args.command == "run":
            if args.run_command == "replay":
                prompt = _input_text(args)
                stored_attempt = None
                if not prompt and args.attempt_id:
                    stored_attempt = store.get_attempt(args.attempt_id)
                    if stored_attempt is None or stored_attempt["case_id"] != args.case_id:
                        raise SystemExit("attempt-id is missing or does not belong to case-id")
                    prompt = stored_attempt["input_text"]
                mechanism = args.mechanism or (stored_attempt or {}).get("mechanism")
                if not mechanism:
                    raise SystemExit("replay requires --mechanism unless --attempt-id is supplied")
                response = ""
                if args.response_file:
                    response = Path(args.response_file).read_text(encoding="utf-8")
                elif args.response is not None:
                    response = args.response
                else:
                    raise SystemExit("replay requires --response or --response-file")
                if not prompt:
                    raise SystemExit("replay requires --input or --input-file")
                result = asyncio.run(run_once(
                    store,
                    case_id=args.case_id,
                    target=ReplayTarget(response),
                    prompt=prompt,
                    mechanism=mechanism,
                    conversation_id=args.conversation_id,
                    outcome=args.outcome,
                    refusal=args.refusal,
                    observed_effect=args.observed_effect,
                ))
                _json(result.to_dict())
                return
            if args.run_command == "pyrit-http":
                raw_request = Path(args.request_file).read_text(encoding="utf-8")
                prompt = _input_text(args)
                stored_attempt = None
                if not prompt and args.attempt_id:
                    stored_attempt = store.get_attempt(args.attempt_id)
                    if stored_attempt is None or stored_attempt["case_id"] != args.case_id:
                        raise SystemExit("attempt-id is missing or does not belong to case-id")
                    prompt = stored_attempt["input_text"]
                mechanism = args.mechanism or (stored_attempt or {}).get("mechanism")
                if not mechanism:
                    raise SystemExit("pyrit-http requires --mechanism unless --attempt-id is supplied")
                if not prompt:
                    raise SystemExit("pyrit-http requires --input or --input-file")
                if not args.execute:
                    _json({
                        "dry_run": True,
                        "message": "Network execution is disabled. Re-run with --execute after reviewing the captured request.",
                        "request_file": str(Path(args.request_file).resolve()),
                        "placeholder": args.placeholder,
                        "response_key": args.response_key,
                    })
                    return
                target = PyRITHTTPTarget(
                    raw_http_request=raw_request,
                    prompt_placeholder=args.placeholder,
                    response_key=args.response_key,
                    prompt_encoding=args.prompt_encoding,
                    use_tls=not args.no_tls,
                    timeout=args.timeout,
                    model_name=args.model_name,
                )
                result = asyncio.run(run_once(
                    store,
                    case_id=args.case_id,
                    target=target,
                    prompt=prompt,
                    mechanism=mechanism,
                    conversation_id=args.conversation_id,
                    outcome=args.outcome,
                    refusal=args.refusal,
                    observed_effect=args.observed_effect,
                ))
                _json(result.to_dict())
                return
            if args.run_command == "grayswan":
                prompt = _input_text(args)
                stored_attempt = None
                if not prompt and args.attempt_id:
                    stored_attempt = store.get_attempt(args.attempt_id)
                    if stored_attempt is None or stored_attempt["case_id"] != args.case_id:
                        raise SystemExit("attempt-id is missing or does not belong to case-id")
                    prompt = stored_attempt["input_text"]
                mechanism = args.mechanism or (stored_attempt or {}).get("mechanism")
                if not mechanism:
                    raise SystemExit("grayswan requires --mechanism unless --attempt-id is supplied")
                if not prompt:
                    raise SystemExit("grayswan requires --input or --input-file")
                if not args.execute:
                    _json({
                        "dry_run": True,
                        "message": "Network execution and credential loading are disabled. Re-run with --execute after reviewing the target identifiers.",
                        "endpoint": "https://app.grayswan.ai/api/compete/challenge-completion",
                        "model": args.model,
                        "association_id": args.association_id,
                        "behavior_id": args.behavior_id,
                        "challenge_id": args.challenge_id,
                        "chat_id_supplied": bool(args.chat_id),
                        "headers_file": str(Path(args.headers_file).resolve()),
                        "headers_loaded": False,
                        "parent_id_supplied": bool(args.parent_id),
                    })
                    return
                headers = _load_headers_file(args.headers_file)
                target = GraySwanTarget(
                    model=args.model,
                    association_id=args.association_id,
                    behavior_id=args.behavior_id,
                    challenge_id=args.challenge_id,
                    headers=headers,
                    chat_id=args.chat_id,
                    parent_id=args.parent_id,
                    timeout=args.timeout,
                )
                result = asyncio.run(run_once(
                    store,
                    case_id=args.case_id,
                    target=target,
                    prompt=prompt,
                    mechanism=mechanism,
                    outcome=args.outcome,
                    refusal=args.refusal,
                    observed_effect=args.observed_effect,
                ))
                _json(result.to_dict())
                return
        if args.command == "seed":
            records = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
            _json([case.to_dict() for case in store.import_cases(records)])
            return
        if args.command == "import-log":
            records = parse_break_log(args.markdown_file)
            imported = store.import_cases(records)
            if args.full:
                _json([case.to_dict() for case in imported])
            else:
                _json({
                    "imported": len(imported),
                    "case_ids": [case.case_id for case in imported],
                })
            return
        if args.command == "import-ipi":
            _json(import_ipi_dataset(store, args.jsonl_file, limit=args.limit))
            return
        if args.command == "jailbreaker":
            adapter = JailbreakerCEAdapter(args.repo, python_executable=args.python_executable)
            if args.jailbreaker_command == "list":
                _json(adapter.list_techniques())
            else:
                _json(adapter.seed_case(
                    store,
                    technique=args.technique,
                    intent=args.intent,
                    target_id=args.target_id,
                    seed_prompt=args.seed_prompt,
                    system_prompt=args.system_prompt,
                ))
            return
        if args.command == "export":
            bundles = [store.export_bundle(case_id) for case_id in args.case_id]
            if args.format == "inspect":
                output: Any = [
                    build_inspect_sample(bundle)
                    for bundle in bundles
                    if args.include_empty or build_inspect_sample(bundle)["input"]
                ]
            else:
                output = build_promptfoo_config(bundles, include_empty=args.include_empty)
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"wrote {args.out}")
            return


if __name__ == "__main__":
    main()
