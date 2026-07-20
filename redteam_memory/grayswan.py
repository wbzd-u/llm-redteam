"""GraySwan Proving Ground adapter for authorized local experiments."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Iterable, Mapping
from urllib.request import Request, urlopen
import uuid

from .targets import TargetResponse


GRAYSWAN_CHALLENGE_COMPLETION_URL = "https://app.grayswan.ai/api/compete/challenge-completion"


def parse_grayswan_stream(lines: Iterable[bytes | str]) -> TargetResponse:
    """Reconstruct text and metadata from metadata/0/d stream records."""
    chunks: list[str] = []
    metadata: dict[str, Any] = {"adapter": "grayswan", "protocol_records": []}
    evidence: list[dict[str, Any]] = []
    for raw_line in lines:
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
        line = line.strip()
        if not line or ":" not in line:
            continue
        kind, payload = line.split(":", 1)
        try:
            decoded: Any = json.loads(payload.strip())
        except json.JSONDecodeError:
            metadata["protocol_records"].append({"kind": kind, "raw": payload.strip()})
            continue
        if kind == "0" and isinstance(decoded, str):
            chunks.append(decoded)
        elif kind == "metadata" and isinstance(decoded, dict):
            metadata.update(decoded)
        elif kind == "d" and isinstance(decoded, dict):
            metadata["finish"] = decoded
            for field in ("success", "score", "completed", "passed"):
                if field in decoded:
                    confirms_impact = field in {"success", "passed"} and decoded[field] is True
                    evidence.append({
                        "kind": "runtime",
                        "description": f"GraySwan completion observation: {field}",
                        "value": json.dumps({field: decoded[field]}, ensure_ascii=False),
                        "source": "grayswan_sse",
                        "verified": True,
                        "metadata": {
                            "adapter": "grayswan",
                            "field": field,
                            "confirms_impact": confirms_impact,
                        },
                    })
        else:
            metadata["protocol_records"].append({"kind": kind, "value": decoded})
    return TargetResponse(text="".join(chunks), metadata=metadata, evidence=evidence)


class GraySwanTarget:
    """Stateful SSE target; credentials are accepted only as runtime headers."""

    def __init__(self, *, model: str, association_id: str, behavior_id: str,
                 challenge_id: str, headers: Mapping[str, str], chat_id: str | None = None,
                 parent_id: str | None = None,
                 url: str = GRAYSWAN_CHALLENGE_COMPLETION_URL, timeout: float = 45.0) -> None:
        if url != GRAYSWAN_CHALLENGE_COMPLETION_URL:
            raise ValueError("GraySwanTarget only permits the challenge-completion endpoint")
        self.model = model
        self.association_id = association_id
        self.behavior_id = behavior_id
        self.challenge_id = challenge_id
        self.chat_id = chat_id
        self.headers = {str(key): str(value) for key, value in headers.items()}
        self.parent_id = parent_id
        self.url = url
        self.timeout = timeout
        self._lock = asyncio.Lock()

    def _payload(self, prompt: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "id": self.chat_id, "model": self.model, "associationId": self.association_id,
            "behaviorId": self.behavior_id, "challengeId": self.challenge_id,
            "message": {
                "parentId": self.parent_id, "id": str(uuid.uuid4()), "role": "user",
                "attachments": [], "content": prompt,
                "created_at": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "display": True, "done": True, "timestamp": int(now.timestamp()),
            },
            "systemPromptInjection": None,
        }

    def _send_blocking(self, body: bytes) -> TargetResponse:
        headers = {"Accept": "*/*", "Content-Type": "application/json", **self.headers}
        request = Request(self.url, data=body, headers=headers, method="POST")
        with urlopen(request, timeout=self.timeout) as response:
            return parse_grayswan_stream(response)

    async def send(self, prompt: str, *, conversation_id: str | None = None) -> TargetResponse:
        del conversation_id
        async with self._lock:
            payload = self._payload(prompt)
            result = await asyncio.to_thread(
                self._send_blocking, json.dumps(payload, ensure_ascii=False).encode("utf-8")
            )
            result.metadata.update({
                "model": self.model, "challenge_id": self.challenge_id,
                "chat_id_before": self.chat_id or "",
                "assistant_parent_id_before": self.parent_id or "",
                "request_message_id": payload["message"]["id"],
            })
            returned_chat_id = result.metadata.get("chatId")
            if isinstance(returned_chat_id, str) and returned_chat_id:
                self.chat_id = returned_chat_id
                result.metadata["next_chat_id"] = returned_chat_id
            returned_id = result.metadata.get("messageId")
            if isinstance(returned_id, str) and returned_id:
                self.parent_id = returned_id
                result.metadata["next_parent_id"] = returned_id
            return result
