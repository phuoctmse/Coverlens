"""Tests for the Claude Code hooks in .claude/hooks/."""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
BLOCK = 2


def load_hook(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


commit_gate = load_hook("commit_gate")
protect_data = load_hook("protect_data")


def feed_stdin(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any] | str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def fake_run(returncodes: list[int]) -> Any:
    calls = iter(returncodes)

    def run(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, next(calls), "out", "err")

    return run


# --- commit_gate: command matching -------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x",
        "  git commit -m x",
        "git add .\ngit commit -m x",
        "git add . && git commit -m x",
        "git add .; git commit -m x",
        "cd src || git commit",
        "git -C . commit -m x",
        "git -c user.name=a commit -m x",
        "git --no-pager commit -m x",
        "git.exe commit -m x",
        "/usr/bin/git commit -m x",
        "GIT_AUTHOR_NAME=a git commit -m x",
        "rtk git commit -m x",
        "env git commit -m x",
        "git commit --amend --no-edit",
        "$(git commit -m x)",
        "{ git commit -m x; }",
    ],
)
def test_commit_commands_are_detected(command: str) -> None:
    assert commit_gate.is_commit(command)


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git log --oneline -5",
        "git commit-tree HEAD^{tree}",
        'echo "git commit"',
        "grep -r 'git commit' .",
        "uv run pytest -q",
    ],
)
def test_other_commands_are_not_detected(command: str) -> None:
    assert not commit_gate.is_commit(command)


# --- commit_gate: main --------------------------------------------------------


def test_non_commit_command_runs_no_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_stdin(monkeypatch, {"tool_input": {"command": "git status"}})
    monkeypatch.setattr(subprocess, "run", fake_run([]))
    assert commit_gate.main() == 0


def test_commit_allowed_when_all_checks_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_stdin(monkeypatch, {"tool_input": {"command": "git commit -m x"}})
    monkeypatch.setattr(subprocess, "run", fake_run([0, 0, 0]))
    assert commit_gate.main() == 0


def test_commit_blocked_when_a_check_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_stdin(monkeypatch, {"tool_input": {"command": "git commit -m x"}})
    monkeypatch.setattr(subprocess, "run", fake_run([0, 1]))
    assert commit_gate.main() == BLOCK


def test_commit_blocked_when_a_check_crashes(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_uv(*_: Any, **__: Any) -> None:
        raise FileNotFoundError("uv")

    feed_stdin(monkeypatch, {"tool_input": {"command": "git commit -m x"}})
    monkeypatch.setattr(subprocess, "run", missing_uv)
    assert commit_gate.main() == BLOCK


def test_unreadable_payload_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_stdin(monkeypatch, "not json")
    assert commit_gate.main() == BLOCK


# --- protect_data ---------------------------------------------------------------


def run_protect_data(
    monkeypatch: pytest.MonkeyPatch, project: Path, file_path: str
) -> int:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    feed_stdin(monkeypatch, {"tool_input": {"file_path": file_path}})
    return protect_data.main()


@pytest.mark.parametrize(
    "relative",
    [
        "data/ott_web/answer_key.json",
        "src/../data/x.md",
        pytest.param(
            "DATA/x.md",
            marks=pytest.mark.skipif(
                sys.platform != "win32", reason="case-insensitive paths only"
            ),
        ),
    ],
)
def test_edits_under_data_are_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, relative: str
) -> None:
    assert run_protect_data(monkeypatch, tmp_path, str(tmp_path / relative)) == BLOCK


def test_extended_length_path_prefix_is_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = "\\\\?\\" + str(tmp_path / "data" / "x.md")
    assert run_protect_data(monkeypatch, tmp_path, path) == BLOCK


@pytest.mark.parametrize("relative", ["src/coverlens/core/x.py", "data2/x.md", "out/x"])
def test_edits_elsewhere_are_allowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, relative: str
) -> None:
    assert run_protect_data(monkeypatch, tmp_path, str(tmp_path / relative)) == 0


def test_protect_data_blocks_unreadable_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feed_stdin(monkeypatch, "not json")
    assert protect_data.main() == BLOCK
