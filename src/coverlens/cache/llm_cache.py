"""Disk cache for LLM calls: rerunning unchanged input makes zero calls.

The key covers everything that can change an answer: model tag and digest,
system and user prompt, sampling options, output schema and template version.
"""

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

KEY_FORMAT = "1"  # bump to invalidate every entry if the key recipe changes


class LlmRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    model_digest: str  # weights identity: the same tag can be re-pulled
    system: str
    prompt: str
    options: dict[str, Any]  # temperature, seed, num_ctx, ...
    output_schema: dict[str, Any]
    template_version: str

    def key(self) -> str:
        payload = {"key_format": KEY_FORMAT, **self.model_dump(mode="json")}
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class LlmUsage(BaseModel):
    """What one or more LLM calls cost."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0

    def __add__(self, other: LlmUsage) -> LlmUsage:
        return LlmUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            seconds=self.seconds + other.seconds,
        )


class LlmReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    usage: LlmUsage = LlmUsage()


Transport = Callable[[LlmRequest], LlmReply]


class DiskCache:
    """One JSON file per request, sharded by the first two hex digits."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, request: LlmRequest) -> Path:
        key = request.key()
        return self.directory / key[:2] / f"{key}.json"

    def get(self, request: LlmRequest) -> LlmReply | None:
        try:
            entry = json.loads(self.path_for(request).read_text(encoding="utf-8"))
        except OSError, ValueError:
            return None
        if not isinstance(entry, dict) or entry.get("key") != request.key():
            return None
        text = entry.get("response")
        if not isinstance(text, str):
            return None
        try:
            usage = LlmUsage.model_validate(entry.get("usage") or {})
        except ValidationError:
            usage = LlmUsage()
        return LlmReply(text=text, usage=usage)

    def put(self, request: LlmRequest, reply: LlmReply) -> None:
        path = self.path_for(request)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "key": request.key(),
            "request": request.model_dump(mode="json"),
            "response": reply.text,
            "usage": reply.usage.model_dump(),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(tmp, path)  # atomic, so a crash never leaves half an entry


class CachedClient:
    """Sends requests through the cache.

    `calls` and `usage` cover real transport calls in this run; `hits` and
    `cached_usage` cover answers served from the cache (cost avoided).
    """

    def __init__(self, transport: Transport, cache: DiskCache) -> None:
        self._transport = transport
        self._cache = cache
        self.calls = 0
        self.hits = 0
        self.usage = LlmUsage()
        self.cached_usage = LlmUsage()

    def complete(self, request: LlmRequest) -> str:
        cached = self._cache.get(request)
        if cached is not None:
            self.hits += 1
            self.cached_usage += cached.usage
            return cached.text
        reply = self._transport(request)
        self.calls += 1
        self.usage += reply.usage
        self._cache.put(request, reply)
        return reply.text
