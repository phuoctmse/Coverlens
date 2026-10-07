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

## C2: checklist judging (not merged)

`--judge checklist`: one LLM call splits the criterion into conditions, a
second lists the cases that check each condition; COVERED only when every
condition has a case. Code on branch `c2-checklist`.

| | single (baseline) | checklist | paired comparison |
|---|---|---|---|
| ott_web accuracy | 92% | 83% | -9.6%, CI [-19.2%, +0.0%]: within noise, fixed 1, broke 6 |
| claims accuracy | 79% | 75% | -4.0%, CI [-13.0%, +6.0%]: within noise, fixed 10, broke 14 |
| claims covered precision | 81% | 74% | |
| claims gap recall | 63% | 34% | |
| claims LLM calls / tokens in | 69 / 38,110 | 137 / 49,542 | |

It fixed the strict errors (10 on claims) but made the judge more lenient,
not less. Splitting cuts each condition loose from the others, so each part is
easy to match on its own, and the judge pairs parts from unrelated cases. For
CL-04.AC5 "the deductible is waived once third-party liability is confirmed"
it matched "liability confirmed" to QT-077 and "deductible is waived" to
QT-018 (a case that subtracts the deductible): the relation between the
conditions, which is what the criterion is about, was never checked.

Decision: not merged. A checklist would need each case checked against all
conditions together, which is the single-verdict judge again.

## Runaway call found along the way

The claims checklist run took 482 s for 181 s of LLM time: one call
(CL-15.AC1) hung until the 300 s HTTP timeout on every run, and failed calls
are not cached, so every rerun paid it again. Likely cause: no cap on output
tokens (`num_predict`), letting a degenerate reply run on.

## Output cap (`num_predict` 512), merged

Cause confirmed by replaying the hanging call with the candidates in cascade
order: without a cap the reply never ended (timed out at 120 s); with
`num_predict` 512 it stopped after 512 tokens (8 s), failed to parse, and the
criterion came back UNCERTAIN in about 17 s. The transport now treats a reply
that reaches `num_predict` as an error, so the verifier answers UNCERTAIN at
once instead of retrying a reply that will be cut again. Replies normally use
under 100 tokens.

Re-running both domains with the cap (fresh cache, `judge-v1`, Tier 2):

| | before | with cap | paired comparison |
|---|---|---|---|
| ott_web | 48/52 | 50/52 | +3.8%, within noise; fixed 2, broke 0 |
| claims | 79/100 | 81/100 | +2.0%, within noise; fixed 2, broke 0 |

No reply reached the cap, yet four verdicts flipped (all towards the key): the
new option alone changed the decoding slightly. This is the model's
sensitivity to configuration seen throughout phase 2, not an improvement.
New baselines: `eval/baselines/*_np512.json`.

## Stronger model: gpt-oss:120b on Ollama Cloud (free plan)

Probe on one hard criterion (CL-06.AC2) with the three starter models that
answered on the free plan: gpt-oss:120b 2.1 s, valid JSON; gemma4:31b invalid
JSON twice (UNCERTAIN); nemotron-3-ultra 54 s. gpt-oss:120b was run in full
(`--ollama-url https://ollama.com --model gpt-oss:120b --num-predict 4096`,
prompt `judge-v1`, Tier 2 unchanged), compared with the llama3.1:8b baselines:

| | llama3.1:8b | gpt-oss:120b | paired comparison |
|---|---|---|---|
| ott_web | 50/52 | 51/52, 98% [94%, 100%] | +1.9%, within noise; fixed 1, broke 0 |
| claims | 81/100 | **92/100, 92% [86%, 97%]** | **+11.0%, CI [+3.0%, +19.0%]: a real gain**; fixed 15, broke 4 |
| claims gap precision / recall | 73% / 63% | 100% / 77% | |
| claims covered precision / recall | 81% / 88% | 89% / 100% | |
| claims cost | 69 calls, local | 69 calls, 42,222 in / 21,035 out tokens, 145 s | |

The first change in the project to clear the paired bootstrap. Remaining claims
errors are all "covered" on a gap: three come from the Tier 2 overlap rule
(CL-03.AC1, CL-07.AC4, CL-10.AC3), which is now the weakest link; five from the
judge (partial covers CL-05.AC2 and CL-05.AC5, boundary CL-17.AC3, and two
labels that look debatable: CL-03.AC5, CL-06.AC2). Baselines:
`eval/baselines/*gpt-oss-120b*`.

## gpt-oss:120b without Tier 2 (`--no-tier2`)

| | with Tier 2 | without Tier 2 | paired comparison |
|---|---|---|---|
| ott_web | 51/52 | 51/52 | no change |
| claims | 92/100 | 95/100, 95% [90%, 99%] | +3.0%, within noise; fixed CL-03.AC1, CL-07.AC4, CL-10.AC3 (the three Tier 2 false covers), broke none |
| extra LLM calls | | ott +25, claims +31 | |

Decision: Tier 2 stays on by default (with llama3.1:8b it cut calls in half and
did not lose accuracy); with a strong cloud judge, pass `--no-tier2`.
Baselines: `eval/baselines/*gpt-oss-120b_judge-v1_notier2.json`.

## C4 review of the claims disagreements

With the best configuration (gpt-oss:120b, `judge-v1`, `--no-tier2`) the
pipeline disagreed with the key on 5 of 100 criteria. The user reviewed all 5 on
2026-10-07 (`eval/reviews/claims.yaml`) and confirmed the key each time, so
95/100 stands. All five are lenient judge errors: a precondition taken for a
check (CL-03.AC5), a missing exception or second limit (CL-05.AC2,
CL-05.AC5), a neighbouring rule taken for this one (CL-06.AC2), and a boundary
never crossed (CL-17.AC3).
