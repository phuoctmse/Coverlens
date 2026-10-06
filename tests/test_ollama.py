import json
from pathlib import Path

import pytest
from conftest import FakeOllamaServer

from coverlens.cache.llm_cache import (
    CachedClient,
    DiskCache,
    LlmReply,
    LlmRequest,
    LlmUsage,
)
from coverlens.core.models import Case, Requirement, Status
from coverlens.core.protocols import Verifier
from coverlens.verifiers.ollama import (
    TEMPLATE_VERSION,
    OllamaError,
    OllamaTransport,
    OllamaVerifier,
)

REQ = Requirement(
    id="US-01.AC1", parent_id="US-01", text="Valid sign-in lands on home."
)
CASES = [
    Case(
        id="TC-001",
        title="Sign in",
        preconditions="Has an account",
        steps="Enter valid credentials",
        expected_result="Home page shown",
        refs=("US-09.AC4",),
    ),
    Case(id="TC-002", title="Sign out", steps="Click sign out", expected_result="Out"),
]


def answer(status: str, *cited: str, rationale: str = "because") -> str:
    return json.dumps(
        {"status": status, "cited_case_ids": list(cited), "rationale": rationale}
    )


class Scripted:
    """Transport returning queued replies; records every request it gets."""

    def __init__(self, *replies: str | Exception) -> None:
        self.replies = list(replies)
        self.requests: list[LlmRequest] = []

    def __call__(self, request: LlmRequest) -> LlmReply:
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return LlmReply(text=reply)


def verifier(transport: Scripted, tmp_path: Path) -> OllamaVerifier:
    client = CachedClient(transport, DiskCache(tmp_path / "cache"))
    return OllamaVerifier(client, model="llama3.1:8b", model_digest="sha256:abc")


# --- OllamaVerifier ------------------------------------------------------------


def test_is_a_verifier(tmp_path: Path) -> None:
    assert isinstance(verifier(Scripted(), tmp_path), Verifier)


def test_covered_answer_becomes_a_tier_3_verdict(tmp_path: Path) -> None:
    transport = Scripted(answer("covered", "TC-001", rationale="TC-001 signs in."))
    verdict = verifier(transport, tmp_path).judge(REQ, CASES)
    assert verdict.status is Status.COVERED
    assert verdict.tier == 3
    assert verdict.cited_case_ids == ("TC-001",)
    assert verdict.rationale == "TC-001 signs in."


def test_gap_answer_drops_any_citations(tmp_path: Path) -> None:
    verdict = verifier(Scripted(answer("gap", "TC-002")), tmp_path).judge(REQ, CASES)
    assert verdict.status is Status.GAP
    assert verdict.cited_case_ids == ()


def test_prompt_shows_case_content_but_never_refs(tmp_path: Path) -> None:
    transport = Scripted(answer("gap"))
    verifier(transport, tmp_path).judge(REQ, CASES)
    [request] = transport.requests
    assert "US-01.AC1" in request.prompt
    assert "Valid sign-in lands on home." in request.prompt
    for text in ("TC-001", "Has an account", "Enter valid credentials", "TC-002"):
        assert text in request.prompt
    assert "US-09.AC4" not in request.prompt + request.system


def test_request_pins_model_digest_options_schema_and_template(tmp_path: Path) -> None:
    transport = Scripted(answer("gap"))
    verifier(transport, tmp_path).judge(REQ, CASES)
    [request] = transport.requests
    assert (request.model, request.model_digest) == ("llama3.1:8b", "sha256:abc")
    assert request.options["temperature"] == 0
    assert "seed" in request.options
    assert request.template_version == TEMPLATE_VERSION
    assert set(request.output_schema["properties"]) == {
        "status",
        "cited_case_ids",
        "rationale",
    }


@pytest.mark.parametrize(
    "bad",
    [
        "not json at all",
        '{"status": "maybe", "cited_case_ids": [], "rationale": "x"}',
        answer("covered"),  # covered without a citation
        answer("covered", "TC-999"),  # not a candidate
    ],
)
def test_one_retry_fixes_a_bad_answer(bad: str, tmp_path: Path) -> None:
    transport = Scripted(bad, answer("covered", "TC-001"))
    verdict = verifier(transport, tmp_path).judge(REQ, CASES)
    assert verdict.status is Status.COVERED
    assert len(transport.requests) == 2
    assert "invalid" in transport.requests[1].prompt.lower()


def test_two_bad_answers_are_uncertain(tmp_path: Path) -> None:
    transport = Scripted("nope", answer("covered", "TC-999"))
    verdict = verifier(transport, tmp_path).judge(REQ, CASES)
    assert verdict.status is Status.UNCERTAIN
    assert verdict.tier == 3
    assert "TC-999" in verdict.rationale


def test_transport_failure_is_uncertain(tmp_path: Path) -> None:
    transport = Scripted(OllamaError("connection refused"))
    verdict = verifier(transport, tmp_path).judge(REQ, CASES)
    assert verdict.status is Status.UNCERTAIN
    assert "connection refused" in verdict.rationale


def test_no_candidates_is_a_gap_without_a_call(tmp_path: Path) -> None:
    transport = Scripted()
    verdict = verifier(transport, tmp_path).judge(REQ, [])
    assert verdict.status is Status.GAP
    assert transport.requests == []


def test_rerun_is_served_from_the_cache(tmp_path: Path) -> None:
    verifier(Scripted("bad", answer("covered", "TC-001")), tmp_path).judge(REQ, CASES)
    rerun = Scripted()
    verdict = verifier(rerun, tmp_path).judge(REQ, CASES)
    assert verdict.status is Status.COVERED
    assert rerun.requests == []


# --- OllamaTransport against a local fake server -------------------------------


def sample_request() -> LlmRequest:
    return LlmRequest(
        model="llama3.1:8b",
        model_digest="abc123",
        system="sys",
        prompt="user",
        options={"temperature": 0},
        output_schema={"type": "object"},
        template_version="v",
    )


def test_transport_posts_a_non_streaming_chat_with_the_schema(
    fake_ollama: FakeOllamaServer,
) -> None:
    reply = OllamaTransport(fake_ollama.url)(sample_request())
    assert json.loads(reply.text)["status"] == "gap"
    [body] = fake_ollama.seen
    assert body["model"] == "llama3.1:8b"
    assert body["stream"] is False
    assert body["format"] == {"type": "object"}
    assert body["options"] == {"temperature": 0}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_transport_reads_the_model_digest(fake_ollama: FakeOllamaServer) -> None:
    assert OllamaTransport(fake_ollama.url).model_digest("llama3.1:8b") == "abc123"


def test_missing_model_says_how_to_pull_it(fake_ollama: FakeOllamaServer) -> None:
    with pytest.raises(OllamaError, match="ollama pull llama3.2:3b"):
        OllamaTransport(fake_ollama.url).model_digest("llama3.2:3b")


def test_http_errors_become_ollama_errors(fake_ollama: FakeOllamaServer) -> None:
    fake_ollama.reply_with(json.dumps({"error": "model not found"}), status=404)
    with pytest.raises(OllamaError, match="model not found"):
        OllamaTransport(fake_ollama.url)(sample_request())


def test_malformed_replies_become_ollama_errors(fake_ollama: FakeOllamaServer) -> None:
    fake_ollama.reply_with("<html>")
    with pytest.raises(OllamaError):
        OllamaTransport(fake_ollama.url)(sample_request())


def test_unreachable_server_is_an_ollama_error() -> None:
    with pytest.raises(OllamaError, match="127.0.0.1:9"):
        OllamaTransport("http://127.0.0.1:9", timeout=2).model_digest("x")


def test_transport_reports_token_counts_and_duration(
    fake_ollama: FakeOllamaServer,
) -> None:
    body = {
        "message": {"content": answer("gap")},
        "prompt_eval_count": 1200,
        "eval_count": 45,
        "total_duration": 2_500_000_000,  # nanoseconds
    }
    fake_ollama.reply_with(json.dumps(body))
    reply = OllamaTransport(fake_ollama.url)(sample_request())
    assert reply.usage == LlmUsage(prompt_tokens=1200, output_tokens=45, seconds=2.5)


def test_missing_usage_fields_count_as_zero(fake_ollama: FakeOllamaServer) -> None:
    fake_ollama.reply_with(json.dumps({"message": {"content": answer("gap")}}))
    assert OllamaTransport(fake_ollama.url)(sample_request()).usage == LlmUsage()


def test_default_url_avoids_the_localhost_ipv6_detour() -> None:
    from coverlens.verifiers.ollama import DEFAULT_URL

    assert DEFAULT_URL == "http://127.0.0.1:11434"
