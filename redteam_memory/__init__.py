"""Evidence-first memory primitives for authorized LLM red-team work."""

from .models import Attempt, Case, ChallengeIntake, DefenseObservation, DefenseProfile, Evidence, MechanismCard, ResearchPlan, Turn
from .intake import load_intake_file, normalize_intake_record
from .mechanisms import import_mechanisms, load_mechanism_file, normalize_mechanism_record, recommend_mechanisms
from .planner import build_planner_brief, deterministic_draft, validate_plan_payload
from .analysis_export import case_markdown, write_attempt_csv
from .llm_provider import OpenAICompatiblePlanner, ProviderError
from .defense import coverage_matrix, observation_verdict, regression_gate
from .llm_guard_adapter import LLMGuardAdapter, record_llm_guard_observation
from .inspect_integration import load_inspect_samples, task_from_memory
from .ipi_import import import_ipi_dataset, ipi_case_id, iter_ipi_records
from .jailbreaker_adapter import JailbreakerCEAdapter
from .markdown_import import parse_break_log, parse_break_log_text
from .runner import RunResult, run_once
from .state import NextAction, derive_stage, minimize_bundle, recommend_next
from .store import MemoryStore
from .targets import PyRITHTTPTarget, ReplayTarget, TargetResponse
from .grayswan import GraySwanTarget, parse_grayswan_stream

__all__ = [
    "Attempt",
    "Case",
    "case_markdown",
    "ChallengeIntake",
    "DefenseObservation",
    "DefenseProfile",
    "LLMGuardAdapter",
    "Evidence",
    "GraySwanTarget",
    "MemoryStore",
    "MechanismCard",
    "OpenAICompatiblePlanner",
    "ProviderError",
    "ResearchPlan",
    "NextAction",
    "PyRITHTTPTarget",
    "ReplayTarget",
    "RunResult",
    "TargetResponse",
    "Turn",
    "derive_stage",
    "coverage_matrix",
    "build_planner_brief",
    "deterministic_draft",
    "load_inspect_samples",
    "load_intake_file",
    "load_mechanism_file",
    "import_ipi_dataset",
    "ipi_case_id",
    "iter_ipi_records",
    "JailbreakerCEAdapter",
    "parse_break_log",
    "parse_break_log_text",
    "parse_grayswan_stream",
    "observation_verdict",
    "minimize_bundle",
    "normalize_mechanism_record",
    "normalize_intake_record",
    "recommend_next",
    "record_llm_guard_observation",
    "recommend_mechanisms",
    "regression_gate",
    "run_once",
    "task_from_memory",
    "import_mechanisms",
    "validate_plan_payload",
    "write_attempt_csv",
]
