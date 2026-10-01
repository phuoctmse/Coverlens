---
name: mentor-review
description: Mentor-review the code the user wrote for the current milestone
disable-model-invocation: true
argument-hint: "[paths | git ref]"
---

# Review

A **mentor** review: the user wrote this code to relearn Python, so the review teaches rather than fixes. Findings go in the reply; the working tree stays exactly as the user left it.

## Steps

1. **Scope.** If `$ARGUMENTS` names paths or a git ref, review those. Otherwise review everything changed since the last commit: `git status --short` and `git diff HEAD`, untracked files included. Done when you hold the list of files in scope.
2. **Gate.** Run `uv run ruff check`, `uv run ruff format --check`, `uv run pytest -q`. Record each result. Pytest exit code 5 (no tests collected) is a blocker: every milestone ends with a passing test.
3. **Audit.** Dispatch the `rules-auditor` subagent on the same scope, in the background, while you do step 4.
4. **Read.** Read every file in scope in full. Hunt for: correctness bugs and unhandled edge cases; tests that pass without pinning behaviour; type hints that are missing or say less than they could; Python a fluent 3.14 programmer would write differently (`pathlib`, dataclasses / pydantic models, comprehensions, `match`, `Protocol`, `enum`).
5. **Report.** Merge the gate results, the auditor's FAILs and your own findings. Done when every file in scope appears in the report, even if only as "no findings".

## Report

Group findings by severity:

- 🔴 **Blocker**: failing gate, rule violation from the auditor, or a bug.
- 🟡 **Should fix**: works, but fragile, unclear or weakly typed.
- 🟢 **Lesson**: idiomatic Python worth learning; optional.

Each finding: `path:line`, what is wrong and why it matters, then a **hint**: the first rung of the hint → skeleton → full answer ladder from `CLAUDE.md`. Climb the ladder for a finding only when the user asks about that finding.

Close with a verdict: **ready to commit** (suggest a one-line commit message) or **not yet** (name the blockers).
