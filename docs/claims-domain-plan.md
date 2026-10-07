# Second domain: insurance claims (held-out test)

Status: agreed 2026-10-07.

## Why

The `ott_web` dev set is small (52 requirements, accuracy 95% CI about
[85%, 98%]) and every threshold and prompt was chosen on it. A second,
business-heavy domain that nothing was tuned on tells us whether the pipeline
generalizes, doubles the data behind every metric, and proves the core is
domain-agnostic (a new domain must need YAML and data only, no core change).

## Decisions (user, 2026-10-07)

- **Domain:** claims handling for a fictional insurer, *Quillmoor Mutual*
  (personal auto and home). Fully synthetic; no real company's data.
- **Size:** about 100 acceptance criteria in 20 stories, about 120 cases.
- **Location:** `data/claims/`, built once by a reproducible generator and then
  read-only like `data/ott_web/`, with sha256 pins in the contract test.
- **Labelling rule:** a criterion is covered only when the cited cases,
  together, check every condition it states. A case that checks part of a
  compound criterion leaves it a gap. (Stricter than the OTT key, which
  counted partial coverage; results are reported per domain.)
- **Held-out thresholds:** Tier 1 thresholds are chosen without labels:
  `gap_threshold: 0` (Tier 1 never concludes a certain gap) and an orphan
  threshold read from the unlabelled score distribution. Tier 2 keeps 0.75.
  The prompt stays `judge-v1`. Nothing is tuned on the claims answer key.

## What the dataset must contain

| Kind | Purpose |
|---|---|
| Direct covers | baseline |
| Paraphrased covers (low word overlap) | retrieval and judge recall |
| Multi-case covers (two cases together) | citation of several cases |
| Partial covers of compound criteria | the "too lenient" error |
| Boundary traps (wrong side of a threshold, wrong role) | the "too lenient" error |
| Same-topic traps near true gaps | the "too lenient" error |
| Decoys (ref points at a criterion they do not cover) | mis-referenced detection |
| Orphans (cover nothing, claim nothing) | orphan detection |

Dimensions for pairwise coverage: policy type, claim type, channel, customer
tier, amount band, with constraints (auto vs home claim types).

## Milestones

1. **Housekeeping and scope:** README (Tier 2 is no longer empty), CLAUDE.md
   scope (phase 2 adds the claims domain), plan status of D3.
2. **Dataset:** `eval/datasets/build_claims.py` (eval code may hold labels)
   writes `data/claims/{user_stories.md,test_cases.xlsx,answer_key.json}`;
   contract test pins the hashes and checks the key's internal consistency.
3. **Domain pack:** `domains/claims/pack.yaml` (columns, dimensions, tags,
   label-free thresholds, glossary, pairwise, forbidden core terms) with the
   same pack-versus-data tests as OTT. No change under `src/coverlens/core/`.
4. **Held-out evaluation:** `python -m eval` on claims with the fake judge and
   with `llama3.1:8b`; the user reviews the disagreements (C4 workflow).
5. **Results:** `docs/experiments/claims-results.md`: per-domain and pooled
   metrics with intervals, Tier 1 canary, Tier 2 precision, error types.
