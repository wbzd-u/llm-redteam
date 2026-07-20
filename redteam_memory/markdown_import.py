from __future__ import annotations

import re
from pathlib import Path
from typing import Any


HEADING_RE = re.compile(r"^###\s+((?:A|B)-\d{8}-\d{3})\s*-\s*(.+?)\s*$", re.MULTILINE)


def _infer_target(title: str) -> tuple[str, str]:
    lower = title.lower()
    if "guard" in lower:
        return "Guard", "The Guard"
    if "librarius" in lower or "key" in lower:
        return "LIBRARIUS", "The Key"
    if "lamp" in lower or "lamplighter" in lower:
        return "Lamp", "The Lamp"
    if "genie" in lower or "freedom" in lower:
        return "Genie", "Freedom!"
    if "resume" in lower or "screening" in lower:
        return "Resume Screening", "Resume Screening"
    return "unknown", ""


def _infer_mechanism(title: str, section: str) -> str:
    lower = f"{title} {section}".lower()
    candidates = [
        ("document-carrier indirect injection", ("document-carrier", "resume screening")),
        ("tool schema mismatch; scorer target binding", ("regex", "scorer", "grant_wish")),
        ("template-level policy amendment", ("template-level", "hidden-context")),
        ("self-generated context poisoning; identity binding", ("identity hijack", "autobiography")),
        ("semantic redefinition; progressive commitment", ("freedom-by-reframing", "semantic convergence")),
        ("fragmented secret reconstruction", ("spatial", "reconstruction", "location")),
        ("emotional coercion; narrative pressure", ("emotional", "guilt", "moral")),
    ]
    for label, keywords in candidates:
        if any(keyword in lower for keyword in keywords):
            return label
    return "unclassified; inspect imported notes"


def _infer_carrier(title: str, section: str) -> str:
    lower = f"{title} {section}".lower()
    if "resume" in lower or "document" in lower:
        return "document carrier"
    if "tool" in lower or "grant_wish" in lower or "permit" in lower:
        return "tool call"
    if "template" in lower or "hidden-context" in lower:
        return "hidden context"
    return "multi-turn chat"


def _infer_impact(title: str, section: str) -> str:
    lower = f"{title} {section}".lower()
    if any(word in lower for word in (
        "rejected", "did not satisfy", "did not transfer", "detects", "failure",
        "not achieved", "no confirmed", "partial effect", "ruled out",
    )):
        return "no confirmed state change"
    if "tool" in lower or "permit" in lower or "grant_wish" in lower:
        return "tool or evaluator action"
    if any(word in lower for word in ("password", "secret", "key", "disclosure", "leak")):
        return "protected value or partial disclosure"
    return "behavior or evaluator state change"


def parse_break_log_text(text: str, *, source: str = "") -> list[dict[str, Any]]:
    """Parse case headings from the local break log without interpreting payloads."""
    matches = list(HEADING_RE.finditer(text))
    records: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        case_id = match.group(1)
        title = match.group(2).strip()
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[match.end():section_end].strip()
        target, challenge = _infer_target(title)
        status = "reported" if case_id.startswith("B-") else "negative"
        notes = section[:6000]
        if len(section) > len(notes):
            notes += "\n[section truncated during import]"
        records.append({
            "case_id": case_id,
            "title": title,
            "target": target,
            "challenge": challenge,
            "mechanism": _infer_mechanism(title, section),
            "carrier": _infer_carrier(title, section),
            "impact": _infer_impact(title, section),
            "status": status,
            "tags": ["break-log", "source:" + ("user-kb" if source else "text")],
            "notes": notes,
        })
    return records


def parse_break_log(path: str | Path) -> list[dict[str, Any]]:
    source_path = Path(path)
    return parse_break_log_text(source_path.read_text(encoding="utf-8"), source=str(source_path))
