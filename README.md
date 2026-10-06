# Coverlens

Coverlens measures whether an existing test suite covers the requirements of a
new feature. It reads a spec (user stories with acceptance criteria, in
markdown) and optionally a test suite (.xlsx), and writes a gap report. It
never generates tests.

## Install

```
uv sync
```

## Run

```
uv run coverlens run \
  --domain domains/ott_web/pack.yaml \
  --spec data/ott_web/user_stories.md \
  --suite data/ott_web/test_cases.xlsx \
  --out out/ --fake
```

`--fake` uses an offline word-overlap judge instead of the LLM. Without
`--suite`, every requirement is reported as a gap.

To use the LLM judge, run Ollama locally, pull the model once and drop `--fake`:

```
ollama pull llama3.1:8b
uv run coverlens run --domain ... --spec ... --suite ... --out out/
```

Options: `--model` (default `llama3.1:8b`), `--ollama-url` (default
`http://localhost:11434`), `--cache-dir` (default `.coverlens_cache/`). Every
LLM reply is cached by a hash of the full request, so rerunning unchanged
input makes no LLM calls; the run prints how many calls it made.

## Output

- `out/coverage_report.xlsx`
  - **Gap report**: one row per acceptance criterion with its status
    (covered / gap / uncertain), the deciding tier, cited cases, candidates and
    rationale.
  - **Coverage**: summary, per-story rollup, orphan cases (claim and cover
    nothing), mis-referenced cases (claim a criterion they do not cover) and,
    when the pack declares `pairwise`, dimension pair coverage: which value
    pairs (e.g. Browser x Network) the suite exercises, the missing pairs, and
    how many more combinations would cover them.
- `out/coverage_report.json`: the same report as JSON.

## How it decides

1. **Tier 1** (refs, tags, BM25): concludes only "certain gap" or "orphan
   case", never "covered", and hands each other criterion a short list of
   candidate cases.
2. **Tier 2**: an empty hook for now.
3. **Tier 3**: an LLM judge (local Llama via Ollama), which must cite the case
   IDs it relies on. `--fake` replaces it offline.

Everything domain-specific (column names, dimensions, tags, glossary,
thresholds) lives in a domain pack such as `domains/ott_web/pack.yaml`.

## Evaluate

```
uv run python -m eval --fake
```

Scores the run against `data/ott_web/answer_key.json` (gap and coverage
precision/recall, citation accuracy, candidate recall, orphans, decoys) and
exits 1 if the canary fails: Tier 1 must never call a covered requirement a
gap. Only `eval/` reads the answer key.

## Develop

```
uv run pytest
uv run ruff check
uv run ruff format
```
