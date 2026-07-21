from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .adapters import build_inspect_sample, build_promptfoo_config
from .defense import coverage_matrix, regression_gate
from .grayswan import GraySwanTarget
from .llm_guard_adapter import LLMGuardAdapter, record_llm_guard_observation
from .markdown_import import parse_break_log
from .models import Attempt, Case, ChallengeIntake, DefenseObservation, DefenseProfile, Evidence, ResearchPlan, Turn
from .intake import load_intake_file
from .mechanisms import RELATION_VALUES, import_mechanisms, load_mechanism_file, recommend_mechanisms
from .planner import build_planner_brief, deterministic_draft, validate_plan_payload
from .analysis_export import case_markdown, write_attempt_csv
from .llm_provider import OpenAICompatiblePlanner, ProviderError
from .campaign import create_campaign, load_campaign_inputs, run_campaign
from .research import CHART_METRICS, research_summary, write_case_csv, write_paper_packet, write_summary_json, write_summary_svg
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

    intake = sub.add_parser("intake", help="import a structured challenge brief and optional chat transcript")
    intake_sub = intake.add_subparsers(dest="intake_command", required=True)
    intake_import = intake_sub.add_parser("import", help="import one Challenge Inbox JSON record")
    intake_import.add_argument("json_file")

    mechanism = sub.add_parser("mechanism", help="manage reusable mechanism cards and Case links")
    mechanism_sub = mechanism.add_subparsers(dest="mechanism_command", required=True)
    mechanism_import = mechanism_sub.add_parser("import", help="import mechanism cards from JSON")
    mechanism_import.add_argument("json_file")
    mechanism_sub.add_parser("list")
    mechanism_show = mechanism_sub.add_parser("show")
    mechanism_show.add_argument("mechanism_id")
    mechanism_link = mechanism_sub.add_parser("link", help="link a mechanism card to a Case")
    mechanism_link.add_argument("--mechanism-id", required=True)
    mechanism_link.add_argument("--case-id", required=True)
    mechanism_link.add_argument("--relation", choices=sorted(RELATION_VALUES), required=True)
    mechanism_link.add_argument("--notes", default="")
    mechanism_recommend = mechanism_sub.add_parser("recommend", help="recommend relevant cards for a Case")
    mechanism_recommend.add_argument("--case-id", required=True)
    mechanism_recommend.add_argument("--limit", type=int, default=5)

    plan = sub.add_parser("plan", help="create, import, and review evidence-linked test plans")
    plan_sub = plan.add_subparsers(dest="plan_command", required=True)
    plan_context = plan_sub.add_parser("context", help="export minimum structured context for an external LLM planner")
    plan_context.add_argument("--case-id", required=True)
    plan_context.add_argument("--limit", type=int, default=5)
    plan_draft = plan_sub.add_parser("draft", help="create a deterministic, review-required plan draft")
    plan_draft.add_argument("--case-id", required=True)
    plan_generate = plan_sub.add_parser("generate", help="generate and save a plan through an explicit LLM endpoint")
    plan_generate.add_argument("--case-id", required=True)
    plan_generate.add_argument("--endpoint", required=True, help="OpenAI-compatible chat-completions endpoint")
    plan_generate.add_argument("--model", required=True)
    plan_generate.add_argument("--api-key-env", default="OPENAI_API_KEY")
    plan_generate.add_argument("--timeout", type=float, default=60.0)
    plan_generate.add_argument("--limit", type=int, default=5)
    plan_generate.add_argument(
        "--execute", action="store_true",
        help="required to make a network request; otherwise prints a safe dry-run",
    )
    plan_import = plan_sub.add_parser("import", help="validate and save a structured planner result")
    plan_import.add_argument("--case-id", required=True)
    plan_import.add_argument("--planner", default="external-llm")
    plan_import.add_argument("--json-file", required=True)
    plan_list = plan_sub.add_parser("list")
    plan_list.add_argument("--case-id", required=True)
    plan_show = plan_sub.add_parser("show")
    plan_show.add_argument("plan_id")
    plan_approve = plan_sub.add_parser("approve", help="mark a reviewed plan as approved for Campaign execution")
    plan_approve.add_argument("plan_id")

    campaign = sub.add_parser("campaign", help="run approved plan steps within explicit execution budgets")
    campaign_sub = campaign.add_subparsers(dest="campaign_command", required=True)
    campaign_create = campaign_sub.add_parser("create")
    campaign_create.add_argument("--plan-id", required=True)
    campaign_create.add_argument("--target-kind", choices=["replay", "grayswan"], required=True)
    campaign_create.add_argument("--max-turns", type=int, default=3)
    campaign_create.add_argument("--max-seconds", type=float, default=120.0)
    campaign_create.add_argument("--max-cost", type=float, default=None)
    campaign_create.add_argument("--conversation-id", default="")
    campaign_list = campaign_sub.add_parser("list")
    campaign_list.add_argument("--case-id", required=True)
    campaign_replay = campaign_sub.add_parser("replay", help="run supplied approved inputs through an offline Replay target")
    campaign_replay.add_argument("--campaign-id", required=True)
    campaign_replay.add_argument("--inputs-file", required=True)
    campaign_replay.add_argument("--response", default="controlled response")
    campaign_replay.add_argument("--response-file", default=None)
    campaign_grayswan = campaign_sub.add_parser("grayswan", help="run supplied approved inputs through a GraySwan challenge")
    campaign_grayswan.add_argument("--campaign-id", required=True)
    campaign_grayswan.add_argument("--inputs-file", required=True)
    campaign_grayswan.add_argument("--model", required=True)
    campaign_grayswan.add_argument("--association-id", required=True)
    campaign_grayswan.add_argument("--behavior-id", required=True)
    campaign_grayswan.add_argument("--challenge-id", required=True)
    campaign_grayswan.add_argument("--headers-file", required=True)
    campaign_grayswan.add_argument("--chat-id", default=None)
    campaign_grayswan.add_argument("--parent-id", default=None)
    campaign_grayswan.add_argument("--timeout", type=float, default=45.0)
    campaign_grayswan.add_argument("--execute", action="store_true")

    analysis = sub.add_parser("analysis", help="export evidence-linked case analysis")
    analysis_sub = analysis.add_subparsers(dest="analysis_command", required=True)
    analysis_markdown = analysis_sub.add_parser("markdown")
    analysis_markdown.add_argument("--case-id", required=True)
    analysis_markdown.add_argument("--out", required=True)
    analysis_csv = analysis_sub.add_parser("attempt-csv")
    analysis_csv.add_argument("--case-id", required=True)
    analysis_csv.add_argument("--out", required=True)

    research = sub.add_parser("research", help="summarize and export cross-Case research data")
    research_sub = research.add_subparsers(dest="research_command", required=True)
    research_sub.add_parser("summary")
    research_csv = research_sub.add_parser("case-csv")
    research_csv.add_argument("--out", required=True)
    research_json = research_sub.add_parser("summary-json")
    research_json.add_argument("--out", required=True)
    research_packet = research_sub.add_parser("paper-packet", help="write a paper-ready methods, data dictionary, and limitation packet")
    research_packet.add_argument("--out", required=True)
    research_chart = research_sub.add_parser("chart")
    research_chart.add_argument("--metric", choices=sorted(CHART_METRICS), required=True)
    research_chart.add_argument("--out", required=True)

    serve = sub.add_parser("serve", help="start the local read-only dashboard API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)

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

    defense = sub.add_parser("defense", help="record and compare defensive-control observations")
    defense_sub = defense.add_subparsers(dest="defense_command", required=True)
    defense_profile = defense_sub.add_parser("profile", help="manage public defense profiles")
    defense_profile_sub = defense_profile.add_subparsers(dest="profile_command", required=True)
    defense_profile_add = defense_profile_sub.add_parser("add")
    defense_profile_add.add_argument("--name", required=True)
    defense_profile_add.add_argument("--version", default="")
    defense_profile_add.add_argument("--kind", default="other")
    defense_profile_add.add_argument("--source", default="")
    defense_profile_add.add_argument("--scope", action="append", default=[])
    defense_profile_add.add_argument("--assumption", action="append", default=[])
    defense_profile_add.add_argument("--limitation", action="append", default=[])
    defense_profile_add.add_argument("--notes", default="")
    defense_profile_sub.add_parser("list")

    defense_observe = defense_sub.add_parser("observe", help="record an authorized defense decision")
    defense_observe_sub = defense_observe.add_subparsers(dest="observe_command", required=True)
    defense_observe_add = defense_observe_sub.add_parser("add")
    defense_observe_add.add_argument("--case-id", required=True)
    defense_observe_add.add_argument("--profile-id", required=True)
    defense_observe_add.add_argument("--run-id", required=True)
    defense_observe_add.add_argument("--expected", dest="expected_disposition", choices=["allow", "block", "unknown"], required=True)
    defense_observe_add.add_argument("--observed", dest="observed_disposition", choices=["allow", "block", "unknown"], required=True)
    defense_observe_add.add_argument("--language", default="und")
    defense_observe_add.add_argument("--carrier", default="text")
    defense_observe_add.add_argument("--latency-ms", type=float, default=None)
    defense_observe_add.add_argument("--verified", action="store_true")
    defense_observe_add.add_argument("--notes", default="")

    defense_matrix = defense_sub.add_parser("matrix", help="aggregate coverage and disagreement observations")
    defense_matrix.add_argument("--profile-id", default=None)
    defense_matrix.add_argument("--run-id", default=None)
    defense_regression = defense_sub.add_parser("regression", help="compare two observed defense runs")
    defense_regression.add_argument("--baseline-run", required=True)
    defense_regression.add_argument("--candidate-run", required=True)
    defense_regression.add_argument("--profile-id", default=None)

    llm_guard = defense_sub.add_parser("llm-guard", help="scan offline through an isolated LLM Guard checkout")
    llm_guard.add_argument("--repo", required=True)
    llm_guard.add_argument("--python", dest="python_executable", default=None)
    llm_guard.add_argument("--scanner", default="PromptInjection", choices=["PromptInjection"])
    llm_guard.add_argument("--threshold", type=float, default=None)
    llm_guard.add_argument("--match-type", default=None)
    llm_guard.add_argument("--use-onnx", action="store_true")
    llm_guard.add_argument("--timeout", type=float, default=600.0)
    llm_guard.add_argument("--input")
    llm_guard.add_argument("--input-file")
    llm_guard.add_argument("--case-id", default=None)
    llm_guard.add_argument("--profile-id", default=None)
    llm_guard.add_argument("--run-id", default=None)
    llm_guard.add_argument("--expected", dest="expected_disposition", choices=["allow", "block", "unknown"], default=None)
    llm_guard.add_argument("--language", default="und")
    llm_guard.add_argument("--carrier", default="text")
    llm_guard.add_argument("--verified", action="store_true")
    llm_guard.add_argument("--notes", default="")

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
        if args.command == "intake":
            try:
                record = load_intake_file(args.json_file)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            case = store.save_case(Case(
                title=record["title"],
                target=record["target"],
                challenge=record["challenge"],
                mechanism=record["mechanism"],
                carrier=record["carrier"],
                impact=record["impact"],
                status=record["status"],
                tags=record["tags"],
                notes=record["notes"],
            ))
            intake = store.save_challenge_intake(ChallengeIntake(
                case_id=case.case_id,
                authorization_scope=record["authorization_scope"],
                success_criteria=record["success_criteria"],
                constraints=record["constraints"],
                target_config=record["target_config"],
                source=record["source"],
            ))
            turns: list[dict[str, Any]] = []
            for item in record["turns"]:
                metadata = item.get("metadata", {})
                if not isinstance(metadata, dict):
                    raise SystemExit("intake turn metadata must be an object")
                turns.append(store.add_turn(Turn(
                    case_id=case.case_id,
                    role=item["role"],
                    content=item["content"],
                    channel=str(item.get("channel", "chat")),
                    provenance=str(item.get("provenance", "imported")),
                    observed_effect=str(item.get("observed_effect", "")),
                    refusal=bool(item.get("refusal", False)),
                    metadata=metadata,
                )).to_dict())
            _json({"case": case.to_dict(), "intake": intake.to_dict(), "turns_imported": len(turns), "turns": turns})
            return
        if args.command == "mechanism":
            if args.mechanism_command == "import":
                try:
                    cards = import_mechanisms(store, load_mechanism_file(args.json_file))
                except ValueError as exc:
                    raise SystemExit(str(exc)) from exc
                _json([card.to_dict() for card in cards])
                return
            if args.mechanism_command == "list":
                _json(store.list_mechanism_cards())
                return
            if args.mechanism_command == "show":
                card = store.get_mechanism_card(args.mechanism_id)
                if card is None:
                    raise SystemExit(f"unknown mechanism: {args.mechanism_id}")
                card["case_links"] = store.list_mechanism_case_links(mechanism_id=args.mechanism_id)
                _json(card)
                return
            if args.mechanism_command == "link":
                try:
                    _json(store.link_mechanism_case(
                        args.mechanism_id, args.case_id, relation=args.relation, notes=args.notes,
                    ))
                except KeyError as exc:
                    raise SystemExit(str(exc)) from exc
                return
            try:
                _json(recommend_mechanisms(store, args.case_id, limit=args.limit))
            except KeyError as exc:
                raise SystemExit(str(exc)) from exc
            return
        if args.command == "plan":
            try:
                if args.plan_command == "context":
                    _json(build_planner_brief(store, args.case_id, limit=args.limit))
                    return
                if args.plan_command == "draft":
                    _json(store.save_research_plan(deterministic_draft(store, args.case_id)).to_dict())
                    return
                if args.plan_command == "generate":
                    brief = build_planner_brief(store, args.case_id, limit=args.limit)
                    provider = OpenAICompatiblePlanner(
                        endpoint=args.endpoint,
                        model=args.model,
                        api_key_env=args.api_key_env,
                        timeout=args.timeout,
                    )
                    if not args.execute:
                        _json(provider.dry_run(brief))
                        return
                    payload = validate_plan_payload(provider.generate(brief))
                    plan = store.save_research_plan(ResearchPlan(
                        case_id=args.case_id,
                        planner=f"openai-compatible:{args.model}",
                        status=payload["status"],
                        hypotheses=payload["hypotheses"],
                        steps=payload["steps"],
                        context=brief,
                        notes=payload["notes"],
                    ))
                    _json(plan.to_dict())
                    return
                if args.plan_command == "import":
                    try:
                        raw = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
                    except FileNotFoundError as exc:
                        raise SystemExit(f"plan file does not exist: {args.json_file}") from exc
                    except json.JSONDecodeError as exc:
                        raise SystemExit(f"plan file is not valid JSON: {args.json_file}") from exc
                    payload = validate_plan_payload(raw)
                    plan = store.save_research_plan(ResearchPlan(
                        case_id=args.case_id,
                        planner=args.planner,
                        status=payload["status"],
                        hypotheses=payload["hypotheses"],
                        steps=payload["steps"],
                        context=build_planner_brief(store, args.case_id),
                        notes=payload["notes"],
                    ))
                    _json(plan.to_dict())
                    return
                if args.plan_command == "list":
                    _json(store.list_research_plans(args.case_id))
                    return
                if args.plan_command == "approve":
                    _json(store.set_research_plan_status(args.plan_id, "approved"))
                    return
                plan = store.get_research_plan(args.plan_id)
                if plan is None:
                    raise SystemExit(f"unknown plan: {args.plan_id}")
                _json(plan)
                return
            except (KeyError, ProviderError) as exc:
                raise SystemExit(str(exc)) from exc
        if args.command == "campaign":
            try:
                if args.campaign_command == "create":
                    _json(create_campaign(
                        store, plan_id=args.plan_id, target_kind=args.target_kind,
                        max_turns=args.max_turns, max_seconds=args.max_seconds,
                        max_cost=args.max_cost, conversation_id=args.conversation_id,
                    ).to_dict())
                    return
                if args.campaign_command == "list":
                    _json(store.list_campaigns(args.case_id))
                    return
                inputs = load_campaign_inputs(args.inputs_file)
                if args.campaign_command == "replay":
                    response = Path(args.response_file).read_text(encoding="utf-8") if args.response_file else args.response
                    _json(asyncio.run(run_campaign(
                        store, campaign_id=args.campaign_id, target=ReplayTarget(response), inputs=inputs,
                    )))
                    return
                campaign_record = store.get_campaign(args.campaign_id)
                if campaign_record is None:
                    raise KeyError(f"unknown campaign: {args.campaign_id}")
                if campaign_record["target_kind"] != "grayswan":
                    raise ValueError("campaign target_kind does not match grayswan")
                if not args.execute:
                    _json({
                        "dry_run": True, "campaign_id": args.campaign_id,
                        "inputs": len(inputs), "headers_loaded": False,
                    })
                    return
                headers = _load_headers_file(args.headers_file)
                target = GraySwanTarget(
                    model=args.model, association_id=args.association_id, behavior_id=args.behavior_id,
                    challenge_id=args.challenge_id, headers=headers, chat_id=args.chat_id,
                    parent_id=args.parent_id, timeout=args.timeout,
                )
                _json(asyncio.run(run_campaign(
                    store, campaign_id=args.campaign_id, target=target, inputs=inputs,
                )))
                return
            except (KeyError, ValueError) as exc:
                raise SystemExit(str(exc)) from exc
        if args.command == "analysis":
            bundle = store.get_case(args.case_id)
            if bundle is None:
                raise SystemExit(f"unknown case: {args.case_id}")
            if args.analysis_command == "markdown":
                destination = Path(args.out)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(case_markdown(bundle), encoding="utf-8")
                _json({"format": "markdown", "path": str(destination), "case_id": args.case_id})
            else:
                write_attempt_csv(bundle, args.out)
                _json({"format": "attempt-csv", "path": str(args.out), "case_id": args.case_id})
            return
        if args.command == "research":
            if args.research_command == "summary":
                _json(research_summary(store))
            elif args.research_command == "case-csv":
                write_case_csv(store, args.out)
                _json({"format": "case-csv", "path": str(args.out)})
            elif args.research_command == "summary-json":
                write_summary_json(store, args.out)
            elif args.research_command == "paper-packet":
                write_paper_packet(store, args.out)
                _json({"format": "paper-packet-markdown", "path": str(args.out)})
            else:
                write_summary_svg(store, metric=args.metric, path=args.out)
                _json({"format": "svg", "metric": args.metric, "path": str(args.out)})
            return
        if args.command == "serve":
            try:
                import uvicorn
                from .web_api import create_app
            except ImportError as exc:
                raise SystemExit("Dashboard dependencies are missing. Install with: pip install -e .[dashboard]") from exc
            uvicorn.run(create_app(args.db), host=args.host, port=args.port)
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
        if args.command == "defense":
            if args.defense_command == "profile":
                if args.profile_command == "add":
                    _json(store.save_defense_profile(DefenseProfile(
                        name=args.name,
                        version=args.version,
                        kind=args.kind,
                        source=args.source,
                        scopes=args.scope,
                        assumptions=args.assumption,
                        limitations=args.limitation,
                        notes=args.notes,
                    )).to_dict())
                else:
                    _json(store.list_defense_profiles())
                return
            if args.defense_command == "observe":
                _json(store.add_defense_observation(DefenseObservation(
                    case_id=args.case_id,
                    profile_id=args.profile_id,
                    run_id=args.run_id,
                    expected_disposition=args.expected_disposition,
                    observed_disposition=args.observed_disposition,
                    language=args.language,
                    carrier=args.carrier,
                    latency_ms=args.latency_ms,
                    verified=args.verified,
                    notes=args.notes,
                )).to_dict())
                return
            if args.defense_command == "llm-guard":
                prompt = _input_text(args)
                if not prompt:
                    raise SystemExit("defense llm-guard requires --input or --input-file")
                record_values = [args.case_id, args.profile_id, args.run_id, args.expected_disposition]
                if any(value is not None for value in record_values) and not all(value is not None for value in record_values):
                    raise SystemExit("recording an LLM Guard observation requires --case-id, --profile-id, --run-id, and --expected")
                adapter = LLMGuardAdapter(
                    repo=args.repo,
                    python_executable=args.python_executable,
                    scanner=args.scanner,
                    threshold=args.threshold,
                    match_type=args.match_type,
                    use_onnx=args.use_onnx,
                    timeout=args.timeout,
                )
                result = adapter.scan(prompt)
                if all(value is not None for value in record_values):
                    observation = record_llm_guard_observation(
                        store,
                        case_id=args.case_id,
                        profile_id=args.profile_id,
                        run_id=args.run_id,
                        expected_disposition=args.expected_disposition,
                        result=result,
                        language=args.language,
                        carrier=args.carrier,
                        verified=args.verified,
                        notes=args.notes,
                    )
                    result["observation"] = observation.to_dict()
                _json(result)
                return
            observations = store.list_defense_observations(
                profile_id=args.profile_id,
                run_id=getattr(args, "run_id", None),
            )
            if args.defense_command == "matrix":
                _json(coverage_matrix(observations))
            else:
                baseline = store.list_defense_observations(
                    profile_id=args.profile_id, run_id=args.baseline_run
                )
                candidate = store.list_defense_observations(
                    profile_id=args.profile_id, run_id=args.candidate_run
                )
                _json(regression_gate(baseline, candidate))
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
