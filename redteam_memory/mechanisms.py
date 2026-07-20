"""Mechanism-card import and transparent retrieval for the personal memory layer."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .models import MechanismCard, new_id
from .store import MemoryStore


CONFIDENCE_VALUES = {"hypothesis", "observed", "confirmed"}
RELATION_VALUES = {"candidate", "observed", "confirmed", "negative"}
LIST_FIELDS = (
    "match_terms", "tags", "applicability_signals", "preconditions", "negative_signals",
)


def _string_list(record: dict[str, Any], field: str) -> list[str]:
    value = record.get(field, [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"mechanism field '{field}' must be a list of non-empty strings")
    return [item.strip() for item in value]


def normalize_mechanism_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("each mechanism entry must be an object")
    normalized = dict(record)
    for field in ("name", "category"):
        value = normalized.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"mechanism field '{field}' must be a non-empty string")
        normalized[field] = value.strip()
    for field in ("summary", "notes"):
        value = normalized.get(field, "")
        if not isinstance(value, str):
            raise ValueError(f"mechanism field '{field}' must be a string")
        normalized[field] = value.strip()
    for field in LIST_FIELDS:
        normalized[field] = _string_list(normalized, field)
    confidence = str(normalized.get("confidence", "hypothesis"))
    if confidence not in CONFIDENCE_VALUES:
        raise ValueError(f"mechanism confidence must be one of: {', '.join(sorted(CONFIDENCE_VALUES))}")
    normalized["confidence"] = confidence
    if "mechanism_id" in normalized and (not isinstance(normalized["mechanism_id"], str) or not normalized["mechanism_id"].strip()):
        raise ValueError("mechanism_id must be a non-empty string when supplied")
    return normalized


def load_mechanism_file(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"mechanism file does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"mechanism file is not valid JSON: {source}") from exc
    records = raw.get("mechanisms") if isinstance(raw, dict) and "mechanisms" in raw else raw
    if not isinstance(records, list):
        raise ValueError("mechanism file must be a JSON list or an object with a 'mechanisms' list")
    return [normalize_mechanism_record(record) for record in records]


def import_mechanisms(store: MemoryStore, records: Iterable[dict[str, Any]]) -> list[MechanismCard]:
    imported: list[MechanismCard] = []
    for record in records:
        normalized = normalize_mechanism_record(record)
        card = MechanismCard(
            mechanism_id=normalized.get("mechanism_id") or new_id("mechanism"),
            name=normalized["name"],
            category=normalized["category"],
            summary=normalized["summary"],
            match_terms=normalized["match_terms"],
            tags=normalized["tags"],
            applicability_signals=normalized["applicability_signals"],
            preconditions=normalized["preconditions"],
            negative_signals=normalized["negative_signals"],
            confidence=normalized["confidence"],
            notes=normalized["notes"],
        )
        imported.append(store.save_mechanism_card(card))
    return imported


def _case_text(bundle: dict[str, Any]) -> str:
    values: list[str] = []
    for field in ("title", "target", "challenge", "mechanism", "carrier", "impact", "notes"):
        value = bundle.get(field, "")
        if isinstance(value, str):
            values.append(value)
    values.extend(str(tag) for tag in bundle.get("tags", []))
    intake = bundle.get("intake") or {}
    for field in ("authorization_scope",):
        value = intake.get(field, "")
        if isinstance(value, str):
            values.append(value)
    for field in ("success_criteria", "constraints"):
        values.extend(str(value) for value in intake.get(field, []))
    return "\n".join(values).casefold()


def _terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[\w-]{2,}", value.casefold()) if len(term) >= 2}


def recommend_mechanisms(store: MemoryStore, case_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Return transparent, rule-scored mechanism-card candidates for a Case."""
    bundle = store.get_case(case_id)
    if bundle is None:
        raise KeyError(f"unknown case: {case_id}")
    text = _case_text(bundle)
    case_tags = {str(tag).casefold() for tag in bundle.get("tags", [])}
    existing = {link["mechanism_id"] for link in bundle.get("mechanism_links", [])}
    recommendations: list[dict[str, Any]] = []
    for card in store.list_mechanism_cards():
        score = 0
        reasons: list[dict[str, Any]] = []
        tag_overlap = sorted(case_tags & {tag.casefold() for tag in card["tags"]})
        if tag_overlap:
            points = 3 * len(tag_overlap)
            score += points
            reasons.append({"kind": "tag_overlap", "terms": tag_overlap, "points": points})
        matched_terms = [term for term in card["match_terms"] if term.casefold() in text]
        if matched_terms:
            points = 2 * len(matched_terms)
            score += points
            reasons.append({"kind": "match_term", "terms": matched_terms, "points": points})
        name_terms = _terms(card["name"] + " " + card["category"])
        case_terms = _terms(text)
        overlap = sorted(name_terms & case_terms)
        if overlap:
            points = min(4, len(overlap))
            score += points
            reasons.append({"kind": "name_category_overlap", "terms": overlap, "points": points})
        historical_links = store.list_mechanism_case_links(mechanism_id=card["mechanism_id"])
        relation_counts = Counter(link["relation"] for link in historical_links)
        if relation_counts["confirmed"]:
            score += 1
            reasons.append({"kind": "historical_confirmed", "count": relation_counts["confirmed"], "points": 1})
        if card["mechanism_id"] in existing:
            score += 5
            reasons.append({"kind": "already_linked_to_case", "points": 5})
        if score:
            recommendations.append({
                "mechanism": card,
                "score": score,
                "reasons": reasons,
                "historical_relations": dict(relation_counts),
            })
    recommendations.sort(key=lambda item: (-item["score"], item["mechanism"]["name"]))
    return recommendations[:limit]
