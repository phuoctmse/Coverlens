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


# --- .env -----------------------------------------------------------------------


def write_env(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_dotenv_is_the_last_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    dotenv = write_env(tmp_path, "OLLAMA_API_KEY=from-dotenv\n")
    assert resolve_api_key(None, dotenv) == "from-dotenv"


def test_environment_beats_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "from-env")
    dotenv = write_env(tmp_path, "OLLAMA_API_KEY=from-dotenv\n")
    assert resolve_api_key(None, dotenv) == "from-env"


@pytest.mark.parametrize(
    "text",
    [
        '# comment\n\nOTHER=x\nOLLAMA_API_KEY="quoted"\n',
        "export OLLAMA_API_KEY='quoted'\n",
        "OLLAMA_API_KEY = quoted  \r\n",
    ],
)
def test_dotenv_syntax(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    assert resolve_api_key(None, write_env(tmp_path, text)) == "quoted"


def test_missing_dotenv_or_key_means_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    assert resolve_api_key(None, tmp_path / ".env") is None
    assert resolve_api_key(None, write_env(tmp_path, "OTHER=x\n")) is None


def test_the_real_dotenv_is_hidden_from_tests() -> None:
    import coverlens.pipeline

    assert not coverlens.pipeline.DEFAULT_DOTENV.exists()
    assert resolve_api_key(None) is None
