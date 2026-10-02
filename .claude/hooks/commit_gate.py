"""PreToolUse hook: block `git commit` unless ruff and pytest pass.

Fails closed: if the hook itself crashes, the commit is blocked too.
"""

import json
import os
import re
import subprocess
import sys

# Claude Code blocks the tool call only on exit code 2; any other non-zero code
# is a non-blocking error and the command still runs.
BLOCK = 2
CHECK_TIMEOUT_S = 90  # three checks must fit in the 300 s hook timeout

COMMIT_RE = re.compile(
    r"(?:^|[;&|({!`])\s*"  # start of a (sub)command; ^ also matches after \n
    r"(?:[A-Za-z_]\w*=\S*\s+)*"  # VAR=value prefixes
    r"(?:(?:rtk|env)\s+)?"
    r"(?:\S*[\\/])?git(?:\.exe)?"  # git, git.exe, or a path to either
    r"(?:\s+-[cC]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*"  # global options before the verb
    r"\s+commit(?![\w-])",
    re.MULTILINE,
)

CHECKS: list[tuple[str, list[str]]] = [
    ("ruff check", ["uv", "run", "ruff", "check"]),
    ("ruff format --check", ["uv", "run", "ruff", "format", "--check"]),
    ("pytest", ["uv", "run", "pytest", "-q"]),
]


def is_commit(command: str) -> bool:
    return COMMIT_RE.search(command) is not None


def failed_check(project: str) -> str | None:
    """Run every check; return a failure report, or None if all pass."""
    for name, args in CHECKS:
        result = subprocess.run(
            args,
            cwd=project,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=CHECK_TIMEOUT_S,
            check=False,
        )
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip()
            tail = "\n".join(output.splitlines()[-30:])
            return f"Commit blocked: `{name}` failed.\n{tail}"
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
        if not is_commit(command):
            return 0
        project = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."
        failure = failed_check(project)
    except Exception as exc:  # noqa: BLE001 -- fail closed: a broken gate must block
        print(f"Commit blocked: commit gate crashed: {exc!r}", file=sys.stderr)
        return BLOCK
    if failure:
        print(failure, file=sys.stderr)
        return BLOCK
    return 0


if __name__ == "__main__":
    sys.exit(main())
