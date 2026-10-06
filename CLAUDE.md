# Coverlens

Python framework that measures whether a test suite sufficiently covers a new feature.
Input: a spec (user stories in markdown) + optionally an existing test suite (.xlsx).
Output: a gap report (Excel with "Gap report" and "Coverage" sheets, plus a JSON copy). It never generates tests.

Current scope: PHASE 1 only — run end to end on the OTT web domain (`domains/ott_web/`).

## How we work in this repo

- Claude writes the code (implementation and tests) directly.
- Chat with the user in Vietnamese. Everything in the repo (code, identifiers, comments, docs, data) is in English.
- Work in small milestones; each ends with a passing test and a commit.

## Project rules

- Core is domain-agnostic. Everything domain-specific (dimensions, constraints, glossary, Excel column mapping) lives in a YAML domain pack. Code in `src/coverlens/core/` must never contain domain words (e.g. region, DRM, browser, entitlement); a contract test enforces this.
- Exactly three extension points, as `typing.Protocol`: `InputAdapter`, `Verifier` (backend), `OutputWriter`.
- Verifier cascade: Tier 1 is algorithmic (ID/tag match + BM25, top-k) and may only conclude "certain gap" or "orphan case", never "covered". Tier 2 is a rule-based overlap judge that may only conclude "covered" (threshold in the pack; it never concludes "gap"). Tier 3 is an LLM judge with forced structured output.
- The LLM backend is a local Llama model via Ollama (no paid API). Every LLM call is cached by hash of (model, model digest, system prompt, prompt, options, output schema, template version); rerunning unchanged input must make 0 calls.
- Every "covered" verdict must cite at least one case ID.
- `FakeVerifier` keeps the whole test suite offline.
- All data is synthetic or public. Never use or invent data resembling a real company's internal data.
- `data/ott_web/` is read-only input. `answer_key.json` may be used ONLY by `eval/` code, never as pipeline input.
- Keep dependencies small: openpyxl, pyyaml, allpairspy, pydantic (+ pytest, ruff for dev). No web UI.
- Out of scope for phase 1: training, OpenAPI adapter, a second domain, Playwright.
- If the brief is ambiguous or conflicts, ask instead of guessing.

## Design decisions (agreed 2026-10-01)

- Unit of coverage is the acceptance criterion (e.g. `US-01.AC1`). Story status is rolled up from its ACs: all covered → covered, some → partial, none → gap.
- Verdict statuses: `COVERED`, `GAP`, `UNCERTAIN` (LLM failure, invalid JSON after one retry, or invalid citation). Each verdict records the deciding tier. No `PARTIAL` in phase 1.
- A `COVERED` verdict may only cite case IDs from the candidates shown to the judge.
- Tier 1 is plain functions in core, not a Protocol:
  - "certain gap" = no case's requirement ref points at the AC and the top BM25 score is below `τ_gap`;
  - "certain orphan" = the case has no ref, no tag, and its top BM25 score against every AC is below `τ_orphan`;
  - everything else → top-k candidates for the next tier.
- Thresholds and the tag → story map live in the domain pack. Tags only add candidates; they are never evidence of coverage.
- Canary: Tier 1 must produce 0 false "certain gap" verdicts on the eval set.
- Tier 2 and Tier 3 both implement `Verifier`; `judge()` returns `Verdict | None`, where `None` passes to the next tier. Tier 2 is the overlap rule (phase 2, B1); a pack without `tier2` falls back to a no-op verifier. A cascade orchestrator in core runs Tier 1, then the verifiers in order.
- The LLM judge sees case content only (title, preconditions, steps, expected result), never the requirement ref.
- The report separates orphan cases (claim nothing, cover nothing) from mis-referenced cases (reference an AC but do not cover it).
- Pairwise coverage only measures, it never outputs test cases: pack dimension values + constraints define the required value pairs (enumerated exactly; allpairspy with a constraint filter was found to miss valid pairs), and the "Coverage" sheet reports which pairs the suite exercises plus allpairspy's estimate of how many more combinations would cover the rest.

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
uv run python -m eval --fake   # score against answer_key.json; exits 1 if the Tier 1 canary fails
```

Run ruff and pytest before every commit. Python 3.14 (user's choice; the original brief said 3.12), type hints everywhere.
