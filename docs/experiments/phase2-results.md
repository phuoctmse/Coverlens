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
