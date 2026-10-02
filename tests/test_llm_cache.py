from pathlib import Path
from typing import Any

import pytest

from coverlens.cache.llm_cache import CachedClient, DiskCache, LlmRequest


def request(**overrides: Any) -> LlmRequest:
    fields: dict[str, Any] = {
        "model": "llama3.1:8b",
        "model_digest": "sha256:abc",
        "system": "You judge coverage.",
        "prompt": "Does TC-001 cover US-01.AC1?",
        "options": {"temperature": 0, "seed": 7},
        "output_schema": {
            "type": "object",
            "properties": {"status": {"type": "string"}},
        },
        "template_version": "v1",
    }
    return LlmRequest.model_validate(fields | overrides)


class Transport:
    """Fake LLM transport that counts how often it is really called."""

    def __init__(self, reply: str = '{"status": "covered"}') -> None:
        self.reply = reply
        self.calls = 0

    def __call__(self, req: LlmRequest) -> str:
        self.calls += 1
        return self.reply


# --- request keys --------------------------------------------------------------


def test_key_is_a_stable_sha256() -> None:
    key = request().key()
    assert len(key) == 64
    assert key == request().key()


def test_key_ignores_dict_order() -> None:
    a = request(options={"temperature": 0, "seed": 7})
    b = request(options={"seed": 7, "temperature": 0})
    assert a.key() == b.key()


@pytest.mark.parametrize(
    "change",
    [
        {"model": "llama3.2:3b"},
        {"model_digest": "sha256:def"},  # same tag, re-pulled weights
        {"system": "Be strict."},
        {"prompt": "Does TC-002 cover US-01.AC1?"},
        {"options": {"temperature": 0.2, "seed": 7}},
        {"options": {"temperature": 0, "seed": 8}},
        {"output_schema": {"type": "object"}},
        {"template_version": "v2"},
    ],
)
def test_every_input_that_changes_the_answer_changes_the_key(
    change: dict[str, Any],
) -> None:
    assert request(**change).key() != request().key()


# --- DiskCache -----------------------------------------------------------------


def test_miss_then_hit(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path / "cache")
    assert cache.get(request()) is None
    cache.put(request(), "answer")
    assert cache.get(request()) == "answer"


def test_entries_survive_a_new_cache_object(tmp_path: Path) -> None:
    DiskCache(tmp_path).put(request(), "answer")
    assert DiskCache(tmp_path).get(request()) == "answer"


def test_unicode_round_trips(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cache.put(request(prompt="Phụ đề tiếng Việt?"), "Có — đúng")
    assert cache.get(request(prompt="Phụ đề tiếng Việt?")) == "Có — đúng"


def test_a_corrupt_entry_is_a_miss(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cache.put(request(), "answer")
    cache.path_for(request()).write_text("{not json", encoding="utf-8")
    assert cache.get(request()) is None


def test_an_entry_for_another_request_is_a_miss(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cache.put(request(), "answer")
    other = request(prompt="other")
    cache.path_for(other).parent.mkdir(parents=True, exist_ok=True)
    cache.path_for(other).write_bytes(cache.path_for(request()).read_bytes())
    assert cache.get(other) is None


def test_entry_records_the_request_for_debugging(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cache.put(request(), "answer")
    text = cache.path_for(request()).read_text(encoding="utf-8")
    assert "Does TC-001 cover US-01.AC1?" in text
    assert "sha256:abc" in text


# --- CachedClient --------------------------------------------------------------


def test_first_call_hits_the_transport_and_the_second_does_not(tmp_path: Path) -> None:
    transport = Transport()
    client = CachedClient(transport, DiskCache(tmp_path))
    assert client.complete(request()) == '{"status": "covered"}'
    assert client.complete(request()) == '{"status": "covered"}'
    assert transport.calls == 1
    assert (client.calls, client.hits) == (1, 1)


def test_rerunning_unchanged_input_makes_zero_calls(tmp_path: Path) -> None:
    CachedClient(Transport(), DiskCache(tmp_path)).complete(request())

    rerun_transport = Transport()
    rerun = CachedClient(rerun_transport, DiskCache(tmp_path))
    rerun.complete(request())
    assert rerun_transport.calls == 0
    assert rerun.calls == 0


def test_a_changed_request_calls_again(tmp_path: Path) -> None:
    transport = Transport()
    client = CachedClient(transport, DiskCache(tmp_path))
    client.complete(request())
    client.complete(request(template_version="v2"))
    assert transport.calls == 2


def test_transport_errors_propagate_and_are_not_cached(tmp_path: Path) -> None:
    def broken(_: LlmRequest) -> str:
        raise ConnectionError("ollama is down")

    cache = DiskCache(tmp_path)
    with pytest.raises(ConnectionError):
        CachedClient(broken, cache).complete(request())
    assert cache.get(request()) is None
