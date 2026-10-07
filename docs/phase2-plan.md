# Phase 2 plan: quality at low cost

Status: proposed 2026-10-06. Owner: the repo user; Claude implements.

## Goal

Make the Tier 3 judge both more accurate and cheaper, and make every claim of
"better" or "cheaper" measurable. No paid API, no new runtime dependencies,
everything stays local.

## Principles

1. **Measure cost like quality.** Every change reports LLM calls, tokens and
   seconds next to the eval scores.
2. **Rules before the LLM.** Whatever a cheap rule can decide safely never
   reaches the LLM; the LLM handles only the hard cases.
3. **No measurement, no merge.** A change ships only if eval shows a gain
   outside run-to-run noise (see A2). Majority voting failed this test in
   phase 1 and was not merged (`docs/experiments/prompt-tuning.md`).
4. **Spend human time only where the machine and the key disagree.**
5. **Stay inside the brief:** local Ollama model, the dependency list in
   `CLAUDE.md`, `data/` read-only, `answer_key.json` only in `eval/`.

## Baseline (end of phase 1, `llama3.1:8b`, prompt `judge-v1`)

| Metric | Value |
|---|---|
| Correct verdicts | 46 / 52 |
| Gap precision / recall | 6/9, 6/9 |
| Covered precision / recall | 40/43, 40/43 |
| Candidate recall (Tier 1) | 43/43 |
| Canary (Tier 1 false gaps) | 0 |
| LLM calls, first run / rerun | 51 / 0 |
| Wall time, first run | 220 s |

## Milestones

Order is by value for cost. Each milestone ends with passing tests, ruff clean,
an eval run where relevant, and a commit.

### A1. Cost metrics per LLM call

- **Why:** today eval only counts calls; we cannot compare cost per change.
- **How:** Ollama's `/api/chat` reply carries `prompt_eval_count`,
  `eval_count` and `total_duration`. The transport returns them with the text;
  the cache stores them in each entry (the key is unchanged, older entries stay
  readable). `CachedClient` sums usage for real calls in this run. CLI and eval
  print calls, cache hits, prompt tokens, output tokens, LLM seconds and wall
  seconds.
- **Files:** `verifiers/ollama.py`, `cache/llm_cache.py`, `pipeline.py`,
  `cli.py`, `eval/__main__.py`, tests.
- **Done when:** the fake Ollama server returns usage fields and the CLI test
  sees them summed; a rerun reports 0 tokens spent.
- **Cost:** low. No new dependency.

### A2. Confidence intervals and paired comparison in eval

- **Why:** v1, v2 and v3 differed by one requirement; we need to tell signal
  from noise without guessing.
- **How:** bootstrap over requirements (stdlib `random`, fixed seed, 2,000
  resamples) gives 95% intervals for accuracy, gap and covered precision/recall.
  `python -m eval --save out/eval.json` stores per-requirement correctness;
  `--compare BASE.json` runs a paired bootstrap on the accuracy difference and
  says whether the change is a real gain, a real loss, or within noise.
- **Files:** `eval/metrics.py`, `eval/bootstrap.py`, `eval/__main__.py`, tests.
- **Done when:** intervals are reproducible with the seed; a synthetic test
  shows a 1-in-52 change judged as noise and a large change judged as real.
- **Cost:** low. No new dependency.

### B1. Rule-based Tier 2: overlap can conclude COVERED

- **Why:** the offline overlap judge was right on 25/25 of its "covered"
  calls on the dev set. Replayed from the cache, overlap-first then LLM scored
  **48/52 with 26 LLM calls** (baseline 46/52 with 51).
- **How:** an `OverlapVerifier` in the Tier 2 slot. If one candidate contains
  at least `tier2.min_overlap` of the requirement's terms (pack setting,
  default 0.75, the value the fake judge already used before any measurement),
  it returns COVERED citing that case; otherwise `None` and Tier 3 decides. It
  never concludes GAP. `FakeVerifier` reuses the same scoring.
- **Rule change:** `CLAUDE.md` says "Tier 2 is an empty hook for now"; this
  milestone updates that line and the design decisions.
- **Files:** `verifiers/overlap.py`, `verifiers/fake.py`, `core/pack.py`,
  `domains/ott_web/pack.yaml`, `pipeline.py`, `CLAUDE.md`, tests.
- **Done when:** Tier 2 never returns GAP (test); against the saved baseline,
  `--compare` reports no loss and no requirement broken; Tier 2 covered
  precision 100% on the dev set; canary PASS; LLM calls at most 26.
- **Why not "a proven quality gain":** A2 put the baseline accuracy at 88%
  with a 95% interval of [79%, 96%]. On 52 requirements a gain of 2 with none
  broken stays inside paired-bootstrap noise, so quality is held to "no loss"
  and the proven gain is the cost cut. Proving small quality gains needs the
  larger C3 set.
- **Risk:** the threshold could fit this small dataset. Mitigation: it was
  fixed before the measurement; re-check on the C3 data when it exists.
- **Cost:** low. No new dependency.

### B2. Ollama runtime tuning

- **Why:** cheaper and faster calls at the same verdicts.
- **How:** use A1 to find the longest prompt; set `num_ctx` to 4096 if every
  prompt fits with margin (it is part of the cache key, so one recompute).
  Send `keep_alive` so the model stays loaded between runs (not part of the
  key: it cannot change an answer).
- **Files:** `verifiers/ollama.py`, tests.
- **Done when:** A2 shows no accuracy loss and A1 shows lower seconds per call.
  If seconds do not drop, revert and record the result.
- **Cost:** very low.

### C4. Label review of disagreements only

- **Why:** the answer key was built by an AI; at least one label is disputed
  (US-10.AC4). Reviewing all 52 is wasteful; reviewing the 4-6 disagreements
  is not.
- **How:** `python -m eval --disagreements` prints each requirement where the
  pipeline and the key differ, with the criterion text, the cited and candidate
  cases' text, and the judge's rationale. The reviewer records decisions in
  `eval/label_review.yaml` (requirement, key label, reviewed label, note,
  reviewer, date). Eval reports metrics against both the raw key and the
  reviewed key. `data/` is not touched.
- **Files:** `eval/label_review.py`, `eval/label_review.yaml`,
  `eval/__main__.py`, tests.
- **Done when:** the review file validates (known requirement IDs, labels
  covered or gap); the user has reviewed the current disagreements (~15 min).
- **Cost:** low code, ~15 minutes of human time.

### D3. Git pre-commit hook for commits made outside Claude

**Status: dropped by the user on 2026-10-07.**

- **Why:** the Claude Code hook only gates commits Claude runs; the user's own
  commits skip ruff and pytest.
- **How:** `.githooks/pre-commit` (plain Python, no dependency) reuses the
  checks in `.claude/hooks/commit_gate.py`. Enabled once per clone with
  `git config core.hooksPath .githooks`, documented in the README.
- **Files:** `.githooks/pre-commit`, `.claude/hooks/commit_gate.py`,
  `README.md`, tests.
- **Done when:** a commit from the terminal with a ruff error is blocked; a
  clean one passes.
- **Known limit:** checks the working tree, not exactly the staged content.
- **Cost:** low.

## Targets for the bundle

| Metric | Baseline | Target |
|---|---|---|
| Correct verdicts | 46 / 52 | no loss and nothing broken (`--compare`); small gains need C3 to prove |
| Canary | PASS | PASS |
| LLM calls, first run | 51 | at most 26 |
| Cost visibility | calls only | calls, tokens, seconds |
| Human review | none | disagreements reviewed and recorded |

## Later, after this bundle

| Item | Needs |
|---|---|
| C3. Harder eval set: paraphrased cases and same-topic traps | Synthetic data under `eval/` (not `data/`) |
| C1. Hybrid retrieval: BM25 + `nomic-embed-text` via Ollama `/api/embed`, fused with reciprocal rank fusion | C3, to show a gain; a 270 MB model download |
| C2. Split compound criteria into a checklist before judging | C3; costs about 2x calls, offset by B1 |
| B3. Compare quantizations (q4 vs q6) of `llama3.1:8b` | A1, A2 |
| D1, D2, D4. Type checker, test coverage, GitHub Actions | User approval for dev dependencies |

## Not planned

- Cross-encoder rerankers or NLI models: need `torch`/`transformers`, against
  the dependency rule.
- Paid APIs.
- More prompt wording changes or majority voting on `llama3.1:8b`: measured in
  phase 1 with no gain.
