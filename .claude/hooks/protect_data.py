"""PreToolUse hook: block file edits under data/ (read-only pipeline input).

Fails closed: if the hook itself crashes, the edit is blocked too.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# Claude Code blocks the tool call only on exit code 2.
BLOCK = 2

# Windows extended-length prefixes (\\?\C:\... and //?/C:/...) that resolve() keeps.
EXTENDED_PREFIXES = ("\\\\?\\", "//?/")


def strip_extended_prefix(path: str) -> str:
    for prefix in EXTENDED_PREFIXES:
        if path.startswith(prefix):
            return path[len(prefix) :]
    return path


def is_under_data(payload: dict[str, Any]) -> str | None:
    """Return the offending path if the tool call targets data/, else None."""
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not file_path:
        return None

    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")
    target = Path(strip_extended_prefix(file_path))
    if not target.is_absolute():
        target = Path(payload.get("cwd") or project) / target

    data_dir = os.path.normcase(str((project / "data").resolve())) + os.sep
    if os.path.normcase(str(target.resolve())).startswith(data_dir):
        return file_path
    return None


def main() -> int:
    try:
        blocked = is_under_data(json.load(sys.stdin))
    except Exception as exc:  # noqa: BLE001 -- fail closed
        print(f"Blocked: data/ guard crashed: {exc!r}", file=sys.stderr)
        return BLOCK
    if blocked:
        print(
            f"Blocked: {blocked} is under data/, which is read-only input. "
            "Write outputs to out/ instead.",
            file=sys.stderr,
        )
        return BLOCK
    return 0


if __name__ == "__main__":
    sys.exit(main())
