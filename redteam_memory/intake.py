"""Challenge Inbox import helpers.

The format is deliberately small and JSON-only for the first iteration: it is
easy to validate, version, export, and feed to a later LLM planning layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = ("title", "challenge")


def load_intake_file(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"intake file does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"intake file is not valid JSON: {source}") from exc
    if not isinstance(raw, dict):
        raise ValueError("intake file must contain one JSON object")
    return normalize_intake_record(raw, source=str(source))


def normalize_intake_record(record: dict[str, Any], *, source: str = "manual") -> dict[str, Any]:
    """Validate a portable inbox record without interpreting its content."""
    normalized = dict(record)
    for field in REQUIRED_FIELDS:
        value = normalized.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"intake field '{field}' must be a non-empty string")
        normalized[field] = value.strip()

    for field in ("target", "mechanism", "carrier", "impact", "notes", "authorization_scope"):
        value = normalized.get(field, "")
        if not isinstance(value, str):
            raise ValueError(f"intake field '{field}' must be a string")
        normalized[field] = value.strip()

    normalized["status"] = str(normalized.get("status", "open"))
    normalized["source"] = str(normalized.get("source") or source)
    for field in ("tags", "success_criteria", "constraints", "turns"):
        value = normalized.get(field, [])
        if not isinstance(value, list):
            raise ValueError(f"intake field '{field}' must be a list")
        normalized[field] = value
    if not all(isinstance(tag, str) and tag.strip() for tag in normalized["tags"]):
        raise ValueError("intake tags must be non-empty strings")
    for field in ("success_criteria", "constraints"):
        if not all(isinstance(item, str) and item.strip() for item in normalized[field]):
            raise ValueError(f"intake {field} must contain non-empty strings")
    target_config = normalized.get("target_config", {})
    if not isinstance(target_config, dict):
        raise ValueError("intake field 'target_config' must be an object")
    normalized["target_config"] = target_config
    for turn in normalized["turns"]:
        if not isinstance(turn, dict):
            raise ValueError("each intake turn must be an object")
        if not isinstance(turn.get("role"), str) or not isinstance(turn.get("content"), str):
            raise ValueError("each intake turn requires string role and content")
    return normalized
