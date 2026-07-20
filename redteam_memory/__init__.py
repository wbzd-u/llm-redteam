"""Evidence-first memory primitives for authorized LLM red-team work."""

from .models import Attempt, Case, DefenseObservation, DefenseProfile, Evidence, Turn
from .defense import coverage_matrix, observation_verdict, regression_gate
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
    "DefenseObservation",
    "DefenseProfile",
    "Evidence",
    "GraySwanTarget",
    "MemoryStore",
    "NextAction",
    "PyRITHTTPTarget",
    "ReplayTarget",
    "RunResult",
    "TargetResponse",
    "Turn",
    "derive_stage",
    "coverage_matrix",
    "load_inspect_samples",
    "import_ipi_dataset",
    "ipi_case_id",
    "iter_ipi_records",
    "JailbreakerCEAdapter",
    "parse_break_log",
    "parse_break_log_text",
    "parse_grayswan_stream",
    "observation_verdict",
    "minimize_bundle",
    "recommend_next",
    "regression_gate",
    "run_once",
    "task_from_memory",
]
