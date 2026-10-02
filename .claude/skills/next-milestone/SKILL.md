---
name: next-milestone
description: Propose the next small, test-first milestone toward the phase 1 pipeline
disable-model-invocation: true
argument-hint: "[focus area]"
---

# Next milestone

Plan the next **milestone**: the smallest step that leaves the repo with one more passing test and moves phase 1 closer to `coverlens run ... --fake` working end to end. Write the plan, then implement it once the user approves.

## Steps

1. **Read state.** `git log --oneline -15`, the file tree of `src/`, `tests/`, `domains/`, `eval/`, and `uv run pytest -q --collect-only`. Done when you can say which pipeline stages exist and which tests pass.
2. **Pick.** If `$ARGUMENTS` names a focus area, take the next step there. Otherwise take the first missing stage in this default order:
   1. Core models (story, test case, verdict) as pydantic models
   2. Domain pack loader (`pack.yaml` → typed config)
   3. Input adapters: spec markdown, suite `.xlsx`
   4. Tier 1 verifier (ID/tag match + BM25 top-k)
   5. `FakeVerifier`
   6. Output writers: Excel ("Gap report", "Coverage") and JSON
   7. CLI wiring with `--fake`
   8. LLM cache
   9. Ollama Tier 3 judge
   10. Eval harness + canary
   A stage too big for one sitting (roughly 1–2 hours, one or two modules, one test file) gets cut into slices; plan only the first slice.
3. **Write the plan.** Done when every section below is filled.

## Plan

- **Goal**: one sentence.
- **Files**: paths to create or change.
- **Test first**: each test as name + arrange / act / assert, in one line each.
- **Done when**: the specific tests pass and `ruff check` and `ruff format --check` are clean.
- **Rules in play**: the `CLAUDE.md` project rules this milestone touches, by name.
- **Commit message**: one line.
