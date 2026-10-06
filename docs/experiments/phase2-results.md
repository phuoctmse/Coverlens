# Phase 2 results

Dev set: `ott_web` (52 requirements, 57 cases), model `llama3.1:8b`, prompt
`judge-v1`. Cost measured with a fresh cache. Quality compared with
`python -m eval --compare` (paired bootstrap, 95%).

| Step | Correct / 52 | Accuracy 95% CI | LLM calls | Prompt / output tokens | Run time |
|---|---|---|---|---|---|
| Phase 1 baseline | 46 | [79%, 96%] | 51 | 26,243 / 2,764 | 168.6 s |
| + 127.0.0.1 instead of localhost | 46 | same | 51 | 26,243 / 2,764 | 53.9 s |
| + B1 Tier 2 overlap rule | 48 | [85%, 98%] | 26 | 13,495 / 1,434 | 31.0 s |

## A1 (cost metrics)

Ollama spent 62.2 s of a 168.6 s run. The rest was connection set-up:
`localhost` tried IPv6 first and waited ~2 s per call (2.04 s vs 0.003 s per
request, measured). Defaulting to `127.0.0.1` cut the run to 53.9 s with
identical tokens, so identical answers.

## B1 (Tier 2 overlap rule)

- Tier 2 settled 25 requirements, all correctly (25/25), so 26 instead of 51
  reached the LLM: 49% fewer calls and tokens, run time 53.9 s -> 31.0 s.
- Against the baseline: fixed US-01.AC4 and US-10.AC3 (both "too strict"
  LLM errors), broke none. Accuracy 88% -> 92%, change +3.8%, 95% CI
  [+0.0%, +9.6%]: within noise, as expected on 52 requirements. Held to the
  plan's bar: no loss, nothing broken.
- Canary PASS. New baseline: `eval/baselines/llama3.1-8b_judge-v1_tier2.json`.

## B2 (Ollama runtime tuning)

Fresh caches, same 26 calls and 13,495 prompt tokens each run; verdicts
identical to the B1 baseline at every setting (48/52, nothing broken).

| num_ctx | VRAM used | Warm call median | Notes |
|---|---|---|---|
| 8192 | 6,936 MiB | 0.81-0.95 s | |
| 4096 | 6,420 MiB | 0.93 s | measured right after a reload |
| 2048 | 6,162 MiB | 0.83-0.93 s | |

Run order decided the speed, not `num_ctx`: whichever setting ran right after
a model reload was slower (0.93-0.95 s per call), a warm model gave 0.81-0.83 s
at both 2048 and 8192. Prompts are at most 712 tokens, far below every window.

Decisions:
- Keep `num_ctx` 8192: a smaller window saves VRAM (-774 MiB at 2048) but no
  time, and leaves less room for larger suites. `--num-ctx` is available.
- Guard against silent truncation: a reply whose prompt plus output fills the
  window is treated as an error (UNCERTAIN), since Ollama does not document
  what it does with an overlong prompt.
- `keep_alive` 30m instead of Ollama's default 5m: a reload measured 4.7-7.9 s,
  paid again whenever two runs are more than 5 minutes apart.

## C4 (label review of disagreements)

With Tier 2 and `judge-v1`, the pipeline disagreed with the key on 4 of 52
requirements. The user reviewed all 4 on 2026-10-07 (`eval/label_review.yaml`)
and confirmed the key every time, so all 4 are judge errors:

| Requirement | Key | Judge | Error type |
|---|---|---|---|
| US-06.AC3 | gap | covered | too lenient: same menu, different check |
| US-10.AC4 | gap | covered | too lenient: reaches the limit, never exceeds it |
| US-11.AC3 | covered | gap | too strict: near-verbatim case rejected |
| US-11.AC4 | gap | covered | too lenient: network loss taken for a license failure |

The reviewed key equals the raw key, so 48/52 (92%) stands. Three of the four
remaining errors are lenient ones, which hide real gaps; that is the error to
target next (C2 checklist judging, or a stronger model).
