# Held-out results: claims domain

Date: 2026-10-07. Data: `data/claims` (100 criteria, 120 cases, fictional
insurer). Pipeline unchanged from `ott_web`: `llama3.1:8b`, prompt `judge-v1`,
Tier 2 overlap 0.75. Tier 1 `gap_threshold` 0 (blind); `orphan_threshold` 5.5
(not blind, see the pack). Stricter labelling than OTT: covered only when every
stated condition is checked.

## Scores

| | ott_web (dev, 52) | claims (held-out, 100) |
|---|---|---|
| Accuracy | 92% [85%, 98%] | **79% [71%, 87%]** |
| Gap precision / recall | 86% / 67% | 73% / 63% |
| Covered precision / recall | 93% / 98% | 81% / 88% |
| Citation accuracy | 100% | 100% |
| Candidate recall (Tier 1) | 100% | 100% |
| Orphans | 3/3 | 4/4 (not blind) |
| Decoys flagged | 2/3 | 4/7 |
| Tier 2 precision | 25/25 | **28/31** |
| LLM calls / run time (fresh) | 26 / 31 s | 69 / 87 s |

Pooled: 127 / 152 correct (84%). The offline fake judge scored 60/100 on claims.

## What the held-out set showed

1. **Accuracy fell from 92% to 79%**, and the intervals do not overlap. Part of
   the fall is the stricter labelling rule, part is a domain the prompt and
   thresholds never saw. The dev-set number overstated quality.
2. **Errors are mostly lenient: 13 of 21** (the judge called a gap covered),
   which hides real gaps. They fall on the trap kinds built for this:
   decoys (CL-01.AC4, CL-03.AC1, CL-06.AC2), partial covers (CL-07.AC2,
   CL-10.AC3, CL-18.AC4, CL-20.AC4), same-topic cases (CL-07.AC4, CL-11.AC5,
   CL-16.AC4), and plainly unrelated citations (CL-03.AC5 cites a flood case
   for wear and tear, CL-19.AC5 cites a rental case for an appeal deadline).
3. **Tier 2 is not 100% precise on new data: 3 false covers in 31.** All three
   are criteria with a condition the case leaves out (CL-03.AC1 "only on
   policies that include collision", CL-07.AC4 "delay in days", CL-10.AC3
   "only senior adjusters"): high word overlap, missing condition.
4. **8 strict errors** reject direct covers (e.g. CL-13.AC1 bank account on
   file, CL-14.AC1 80% repair cost, CL-20.AC1 police report view logged).
5. Tier 1 retrieval held up: every covered criterion had a covering case among
   its candidates, and the canary passed with the blind threshold.

## Next

- The lenient errors and the Tier 2 misses point the same way: judging
  compound criteria condition by condition (C2) is the lever with evidence
  behind it. Measure it on both domains.
- Human review of the 21 disagreements (C4) before treating 79% as final.
