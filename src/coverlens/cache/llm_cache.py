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

from pydantic import BaseModel, ConfigDict

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


Transport = Callable[[LlmRequest], str]


class DiskCache:
    """One JSON file per request, sharded by the first two hex digits."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, request: LlmRequest) -> Path:
        key = request.key()
        return self.directory / key[:2] / f"{key}.json"

    def get(self, request: LlmRequest) -> str | None:
        try:
            entry = json.loads(self.path_for(request).read_text(encoding="utf-8"))
        except OSError, ValueError:
            return None
        if not isinstance(entry, dict) or entry.get("key") != request.key():
            return None
        response = entry.get("response")
        return response if isinstance(response, str) else None

    def put(self, request: LlmRequest, response: str) -> None:
        path = self.path_for(request)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "key": request.key(),
            "request": request.model_dump(mode="json"),
            "response": response,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(tmp, path)  # atomic, so a crash never leaves half an entry


class CachedClient:
    """Sends requests through the cache; `calls` counts real transport calls."""

    def __init__(self, transport: Transport, cache: DiskCache) -> None:
        self._transport = transport
        self._cache = cache
        self.calls = 0
        self.hits = 0

    def complete(self, request: LlmRequest) -> str:
        cached = self._cache.get(request)
        if cached is not None:
            self.hits += 1
            return cached
        response = self._transport(request)
        self.calls += 1
        self._cache.put(request, response)
        return response
