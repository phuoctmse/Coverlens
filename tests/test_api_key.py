from pathlib import Path

import pytest

from coverlens.pipeline import resolve_api_key


def test_key_file_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "from-env")
    path = tmp_path / "key.txt"
    path.write_text("  from-file\n", encoding="utf-8")
    assert resolve_api_key(path) == "from-file"


def test_environment_variable_is_the_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "from-env")
    assert resolve_api_key(None) == "from-env"


def test_no_key_anywhere_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    assert resolve_api_key(None) is None


@pytest.mark.parametrize("content", [None, "   \n"])
def test_missing_or_empty_key_file_is_an_error(
    tmp_path: Path, content: str | None
) -> None:
    path = tmp_path / "key.txt"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="key.txt"):
        resolve_api_key(path)
