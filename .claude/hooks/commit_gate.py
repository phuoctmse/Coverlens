"""PreToolUse hook: block `git commit` unless ruff and pytest pass."""

import json
import os
import re
import subprocess
import sys

COMMIT_RE = re.compile(r"(?:^|[;&|(]\s*)(?:rtk\s+)?git\s+commit\b")
PYTEST_NO_TESTS = 5

CHECKS: list[tuple[str, list[str]]] = [
    ("ruff check", ["uv", "run", "ruff", "check"]),
    ("ruff format --check", ["uv", "run", "ruff", "format", "--check"]),
    ("pytest", ["uv", "run", "pytest", "-q"]),
]


def main() -> int:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")
    if not COMMIT_RE.search(command):
        return 0

    project = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."
    for name, args in CHECKS:
        result = subprocess.run(
            args, cwd=project, capture_output=True, text=True, check=False
        )
        ok = result.returncode == 0 or (
            name == "pytest" and result.returncode == PYTEST_NO_TESTS
        )
        if not ok:
            output = (result.stdout + result.stderr).strip()
            tail = "\n".join(output.splitlines()[-30:])
            print(f"Commit blocked: `{name}` failed.\n{tail}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
