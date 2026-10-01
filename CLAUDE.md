# Coverlens

Python framework that measures whether a test suite sufficiently covers a new feature.
Input: a spec (user stories in markdown) + optionally an existing test suite (.xlsx).
Output: a gap report (Excel with "Gap report" and "Coverage" sheets, plus a JSON copy). It never generates tests.

Current scope: PHASE 1 only — run end to end on the OTT web domain (`domains/ott_web/`).

## How we work in this repo

- The user writes the code themselves to relearn Python. Claude acts as a mentor: explain the concept, give a skeleton or hints, then review the user's files. Escalate hint → skeleton → full answer only when the user asks. Do not write implementation files unless explicitly asked.
- Chat with the user in Vietnamese. Everything in the repo (code, identifiers, comments, docs, data) is in English.
- Work in small milestones; each ends with a passing test and a commit.

## Project rules

- Core is domain-agnostic. Everything domain-specific (dimensions, constraints, glossary, Excel column mapping) lives in a YAML domain pack. Code in `src/coverlens/core/` must never contain domain words (e.g. region, DRM, browser, entitlement); a contract test enforces this.
- Exactly three extension points, as `typing.Protocol`: `InputAdapter`, `Verifier` (backend), `OutputWriter`.
- Verifier cascade: Tier 1 is algorithmic (ID/tag match + BM25, top-k) and may only conclude "certain gap" or "orphan case", never "covered". Tier 2 is an empty hook for now. Tier 3 is an LLM judge with forced structured output.
- The LLM backend is a local Llama model via Ollama (no paid API). Every LLM call is cached by hash of (model, prompt); rerunning unchanged input must make 0 calls.
- Every "covered" verdict must cite at least one case ID.
- `FakeVerifier` keeps the whole test suite offline.
- All data is synthetic or public. Never use or invent data resembling a real company's internal data.
- `data/ott_web/` is read-only input. `answer_key.json` may be used ONLY by `eval/` code, never as pipeline input.
- Keep dependencies small: openpyxl, pyyaml, allpairspy, pydantic (+ pytest, ruff for dev). No web UI.
- Out of scope for phase 1: training, OpenAPI adapter, a second domain, Playwright.
- If the brief is ambiguous or conflicts, ask instead of guessing.

## Layout

```
src/coverlens/{core,adapters,verifiers,writers,cache}/   package code
domains/ott_web/pack.yaml                                 domain pack
data/ott_web/                                             input data (do not modify)
eval/                                                     eval harness + canary
tests/                                                    pytest tests
```

## Commands

```
uv sync                      # install dependencies
uv run pytest                # tests
uv run ruff check            # lint
uv run ruff format           # format
uv run coverlens run --domain domains/ott_web/pack.yaml --spec data/ott_web/user_stories.md --suite data/ott_web/test_cases.xlsx --out out/ [--fake]
```

Run ruff and pytest before every commit. Python 3.14 (user's choice; the original brief said 3.12), type hints everywhere.
