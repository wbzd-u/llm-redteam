from __future__ import annotations

import asyncio
import json
from urllib.parse import quote
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class TargetResponse:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)


class AsyncTarget(Protocol):
    async def send(self, prompt: str, *, conversation_id: str | None = None) -> TargetResponse:
        ...


class ReplayTarget:
    """Deterministic target used for offline tests and experiment replays."""

    def __init__(self, response: str | list[str], *, metadata: dict[str, Any] | None = None):
        self._responses = [response] if isinstance(response, str) else list(response)
        if not self._responses:
            raise ValueError("ReplayTarget requires at least one response")
        self._index = 0
        self._metadata = dict(metadata or {})
        self.prompts: list[tuple[str, str | None]] = []

    async def send(self, prompt: str, *, conversation_id: str | None = None) -> TargetResponse:
        self.prompts.append((prompt, conversation_id))
        response = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        return TargetResponse(text=response, metadata=dict(self._metadata))


class PyRITHTTPTarget:
    """Optional PyRIT-backed target for a captured raw HTTP request.

    PyRIT is imported lazily so the core memory package remains dependency-free.
    The request is never sent until ``send`` is called. Callers should keep a
    captured request in a local file and explicitly opt into network execution
    at the CLI layer.
    """

    def __init__(
        self,
        *,
        raw_http_request: str,
        prompt_placeholder: str = "{PROMPT}",
        response_key: str | None = None,
        prompt_encoding: str = "raw",
        use_tls: bool = True,
        timeout: float = 30.0,
        model_name: str = "",
    ) -> None:
        if not raw_http_request.strip():
            raise ValueError("raw_http_request cannot be empty")
        if prompt_placeholder not in raw_http_request:
            raise ValueError("raw_http_request does not contain the prompt placeholder")
        self.raw_http_request = raw_http_request
        self.prompt_placeholder = prompt_placeholder
        self.response_key = response_key
        if prompt_encoding not in {"raw", "json", "url"}:
            raise ValueError("prompt_encoding must be one of: raw, json, url")
        self.prompt_encoding = prompt_encoding
        self.use_tls = use_tls
        self.timeout = timeout
        self.model_name = model_name
        self._target: Any = None
        self._init_lock = asyncio.Lock()

    async def _ensure_target(self) -> Any:
        if self._target is not None:
            return self._target
        async with self._init_lock:
            if self._target is not None:
                return self._target
            try:
                from pyrit.prompt_target import HTTPTarget
                from pyrit.prompt_target import (
                    get_http_target_json_response_callback_function,
                )
                from pyrit.setup import IN_MEMORY, initialize_pyrit_async
            except ImportError as exc:
                raise RuntimeError(
                    "PyRIT is not importable in this Python environment. "
                    "Run this command with the PyRIT project venv or install PyRIT."
                ) from exc

            await initialize_pyrit_async(memory_db_type=IN_MEMORY, load_defaults=False, silent=True)
            callback = None
            if self.response_key:
                callback = get_http_target_json_response_callback_function(key=self.response_key)
            self._target = HTTPTarget(
                http_request=self.raw_http_request,
                prompt_regex_string=self.prompt_placeholder,
                callback_function=callback,
                use_tls=self.use_tls,
                model_name=self.model_name,
                timeout=self.timeout,
            )
        return self._target

    async def send(self, prompt: str, *, conversation_id: str | None = None) -> TargetResponse:
        target = await self._ensure_target()
        try:
            from pyrit.models import MessagePiece
        except ImportError as exc:
            raise RuntimeError("PyRIT models are unavailable in this Python environment") from exc

        conversation_id = conversation_id or uuid.uuid4().hex
        wire_prompt = prompt
        if self.prompt_encoding == "json":
            wire_prompt = json.dumps(prompt, ensure_ascii=False)[1:-1]
        elif self.prompt_encoding == "url":
            wire_prompt = quote(prompt, safe="")
        message = MessagePiece(
            role="user",
            original_value=wire_prompt,
            conversation_id=conversation_id,
        ).to_message()
        responses = await target.send_prompt_async(message=message)
        text = responses[0].get_value() if responses else ""
        return TargetResponse(
            text=str(text),
            metadata={
                "adapter": "pyrit_http",
                "conversation_id": conversation_id,
                "response_key": self.response_key or "raw",
                "prompt_encoding": self.prompt_encoding,
                "original_prompt": prompt,
                "model_name": self.model_name,
            },
        )
