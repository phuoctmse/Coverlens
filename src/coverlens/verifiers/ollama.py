"""Tier 3: a local Llama judge served by Ollama, with forced JSON output.

Talks to Ollama's HTTP API with the standard library only. Every call goes
through the LLM cache, so rerunning unchanged input makes no calls.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from coverlens.cache.llm_cache import CachedClient, LlmReply, LlmRequest, LlmUsage
from coverlens.core.models import Case, Requirement, Status, Verdict

DEFAULT_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_OPTIONS: dict[str, Any] = {"temperature": 0, "seed": 42, "num_ctx": 8192}
TEMPLATE_VERSION = "judge-v1"  # bump when SYSTEM_PROMPT or the prompt layout changes
MAX_ERROR_CHARS = 400
NANOSECONDS = 1_000_000_000  # Ollama reports durations in ns

SYSTEM_PROMPT = """\
You are a senior QA reviewer. You decide whether existing test cases verify one \
acceptance criterion of a product feature.

A case covers the criterion when running its steps would check the behaviour the \
criterion describes. A case that touches the same screen or feature but checks \
something else does not cover it. Judge only from the case text you are given.

Reply with JSON only:
- "status": "covered" or "gap"
- "cited_case_ids": the IDs of the cases that cover the criterion (at least one \
when covered, empty when gap); use only IDs from the list you are given
- "rationale": one or two sentences explaining the decision"""


class OllamaError(Exception):
    """Ollama could not be reached or returned something unusable."""


class JudgeAnswer(BaseModel):
    status: Literal["covered", "gap"]
    cited_case_ids: list[str]
    rationale: str


OUTPUT_SCHEMA = JudgeAnswer.model_json_schema()


class OllamaTransport:
    """Sends one chat request to Ollama and returns the reply text."""

    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Ignore system proxy settings: Ollama runs on this machine.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _call(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise OllamaError(f"{url}: HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise OllamaError(f"cannot reach Ollama at {self.base_url}: {exc}") from exc
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise OllamaError(f"{url}: reply is not JSON") from exc
        if not isinstance(payload, dict):
            raise OllamaError(f"{url}: unexpected reply {payload!r:.100}")
        return payload

    def model_digest(self, model: str) -> str:
        """The digest of a pulled model, so re-pulled weights miss the cache."""
        wanted = {model, f"{model}:latest"}
        for entry in self._call("/api/tags").get("models", []):
            if entry.get("name") in wanted or entry.get("model") in wanted:
                return str(entry.get("digest", ""))
        raise OllamaError(f"model {model} is not pulled; run: ollama pull {model}")

    def __call__(self, request: LlmRequest) -> LlmReply:
        payload = self._call(
            "/api/chat",
            {
                "model": request.model,
                "messages": [
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.prompt},
                ],
                "format": request.output_schema,
                "options": request.options,
                "stream": False,
            },
        )
        content = payload.get("message", {}).get("content")
        if not isinstance(content, str):
            raise OllamaError("/api/chat: reply has no message content")
        usage = LlmUsage(
            prompt_tokens=int(payload.get("prompt_eval_count") or 0),
            output_tokens=int(payload.get("eval_count") or 0),
            seconds=int(payload.get("total_duration") or 0) / NANOSECONDS,
        )
        return LlmReply(text=content, usage=usage)


def build_prompt(requirement: Requirement, candidates: Sequence[Case]) -> str:
    cases = "\n\n".join(f"[{case.id}]\n{case.judge_text()}" for case in candidates)
    return (
        f"Acceptance criterion {requirement.id}:\n{requirement.text}\n\n"
        f"Candidate test cases:\n\n{cases}"
    )


def _check(raw: str, allowed: set[str]) -> tuple[JudgeAnswer | None, str]:
    """Parse and validate a reply; return (answer, "") or (None, error)."""
    try:
        answer = JudgeAnswer.model_validate_json(raw)
    except ValidationError as exc:
        return None, str(exc)[:MAX_ERROR_CHARS]
    if answer.status == "covered":
        if not answer.cited_case_ids:
            return None, "status is covered but cited_case_ids is empty"
        unknown = [cid for cid in answer.cited_case_ids if cid not in allowed]
        if unknown:
            return None, f"cited {unknown}, which are not in the candidate list"
    return answer, ""


class OllamaVerifier:
    """Tier 3 judge. Retries once on an invalid reply, then answers UNCERTAIN."""

    def __init__(
        self,
        client: CachedClient,
        model: str,
        model_digest: str,
        options: dict[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._digest = model_digest
        self._options = DEFAULT_OPTIONS if options is None else options

    def _ask(self, prompt: str) -> str:
        return self._client.complete(
            LlmRequest(
                model=self._model,
                model_digest=self._digest,
                system=SYSTEM_PROMPT,
                prompt=prompt,
                options=self._options,
                output_schema=OUTPUT_SCHEMA,
                template_version=TEMPLATE_VERSION,
            )
        )

    def judge(self, requirement: Requirement, candidates: Sequence[Case]) -> Verdict:
        def verdict(
            status: Status, rationale: str, cited: Sequence[str] = ()
        ) -> Verdict:
            return Verdict(
                requirement_id=requirement.id,
                status=status,
                tier=3,
                cited_case_ids=tuple(dict.fromkeys(cited)),
                rationale=rationale,
            )

        if not candidates:
            return verdict(Status.GAP, "No candidate cases to judge.")
        allowed = {case.id for case in candidates}
        prompt = build_prompt(requirement, candidates)
        try:
            answer, error = _check(self._ask(prompt), allowed)
            if answer is None:
                retry = (
                    f"{prompt}\n\nYour previous reply was invalid: {error}\n"
                    "Reply again with JSON that follows the schema."
                )
                answer, error = _check(self._ask(retry), allowed)
        except OllamaError as exc:
            return verdict(Status.UNCERTAIN, f"LLM call failed: {exc}")
        if answer is None:
            return verdict(
                Status.UNCERTAIN, f"LLM reply invalid after one retry: {error}"
            )
        if answer.status == "covered":
            return verdict(Status.COVERED, answer.rationale, answer.cited_case_ids)
        return verdict(Status.GAP, answer.rationale)
