"""PreToolUse hook: block file edits under data/ (read-only pipeline input)."""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not file_path:
        return 0

    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")
    target = Path(file_path)
    if not target.is_absolute():
        target = Path(payload.get("cwd") or project) / target

    data_dir = os.path.normcase(str((project / "data").resolve())) + os.sep
    if os.path.normcase(str(target.resolve())).startswith(data_dir):
        print(
            f"Blocked: {file_path} is under data/, which is read-only input. "
            "Write outputs to out/ instead.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
