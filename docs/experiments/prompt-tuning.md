# Prompt tuning for the Tier 3 judge (llama3.1:8b)

Date: 2026-10-06. Data: the `ott_web` dev set (52 requirements, 57 cases),
scored with `uv run python -m eval`. Model `llama3.1:8b`, temperature 0,
seed 42, one call per open requirement (51 calls; Tier 1 settles 1).

| Template | Change | Correct / 52 | Gap P | Gap R | Covered P | Covered R | Decoys | Time |
|---|---|---|---|---|---|---|---|---|
| judge-v1 | baseline instructions | 46 | 6/9 | 6/9 | 40/43 | 40/43 | 2/3 | 220 s |
| judge-v2 | + decision rules, 4 worked examples from an unrelated product, free-text `analysis` field first | 47 | 6/8 | 6/9 | 41/44 | 41/43 | 1/3 | 169 s |
| judge-v3 | v2 with `analysis` as a list of `{case_id, checks, covers}` | 46 | 7/11 | 7/9 | 39/41 | 39/43 | 1/3 | 298 s |
| judge-v4 | v2 without the `analysis` field | 40 | 7/17 | 7/9 | 33/35 | 33/43 | 2/3 | 165 s |

The canary passed and no verdict was UNCERTAIN in every run.

## Findings

- v1, v2 and v3 are within one requirement of each other, which is noise on
  52 items: each change fixed a few requirements and broke others, including
  obvious ones (US-12.AC1 "Safari plays FairPlay" flipped to gap in v2 and v4).
- In v2 the free-text `analysis` field was degenerate in 51/51 replies (the
  model wrote `":[{"` and stopped), so v2's small gain came from the rules and
  examples alone. Yet removing that dead field (v4) cost 7 requirements: the
  model is very sensitive to prompt and schema wording.
- Errors went both ways. Too strict: near-verbatim matches called gaps
  (TC-005 sign-out, TC-042 slot freed after 60 s, TC-046 error after 30 s).
  Too lenient: same-topic cases called coverage (TC-046 network loss for a
  failed license request, TC-016 pause/resume for "cannot seek past the live
  edge"). The lenient errors hide real gaps, which is the costlier mistake.

## Decision

Keep judge-v1. Further wording changes on this model and this small set risk
fitting the eval set rather than improving the judge. Next experiment:
majority voting over several samples to damp the run-to-run flips.
