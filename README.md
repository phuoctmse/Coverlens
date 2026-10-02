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

## Output

- `out/coverage_report.xlsx`
  - **Gap report**: one row per acceptance criterion with its status
    (covered / gap / uncertain), the deciding tier, cited cases, candidates and
    rationale.
  - **Coverage**: summary, per-story rollup, orphan cases (claim and cover
    nothing) and mis-referenced cases (claim a criterion they do not cover).
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

## Develop

```
uv run pytest
uv run ruff check
uv run ruff format
```
