# In-repo benchmark: TextGrad vs Sweep vs no-training

## Goal
The single highest-leverage credibility move in the repo: ship a runnable benchmark that compares operad's textual-gradient training against (a) `Sweep` over the same parameter knobs, (b) hand-edited prompts (frozen baseline), on three real tasks. Report F1/accuracy, latency, token-spend, and **failure modes**. This is what turns "we have five optimizers" into "here's evidence one of them is worth the complexity."

## Context
- `examples/` — no benchmarks today.
- `operad/optim/` — TGD, Momentum, EvoGradient, OPRO, APE.
- `operad/algorithms/sweep.py` — for the Sweep baseline.
- `operad/benchmark/` — `Dataset`, `Entry`, `evaluate`, `Experiment`. Use these as the harness.
- This is also the destination for the optimizer-fleet ablation referenced in the review (Section 2.4).

## Scope

**In scope:**
- `examples/benchmark/` (new directory) with three tasks:
  - `task_classification.py` — small AG-News-style or banking-intent dataset (synthesized inline if size matters).
  - `task_summarization.py` — shortform summarization with ROUGE-1.
  - `task_tool_use.py` — a tool-call task scored by exact-match on the chosen tool + args.
- `examples/benchmark/run.py` — runs all three tasks across {no-train, hand-edit, Sweep, TGD, Momentum, EvoGradient, OPRO, APE}, saves a `report.json` with per-cell metrics, prints a Markdown summary.
- `examples/benchmark/README.md` — explains the methodology, the seeds, the headline numbers, and *honest negative results* where TGD didn't beat Sweep.
- Top-level `README.md` — short pointer linking to the benchmark and a one-paragraph honest summary of what it shows.
- `scripts/verify.sh` — exercise the offline mode of the benchmark on a tiny subset (e.g. 5 examples per task) so it doesn't bloat CI.

**Out of scope:**
- Adding new optimizers.
- Adding new metrics beyond what the harness already supports.
- Tuning the agents to make TGD look better than it is.
- Anything outside `examples/benchmark/`, `README.md`, `scripts/verify.sh`.

**Owned by sibling iter-4 tasks — do not modify:**
- `apps/studio/`, `apps/dashboard/`, `apps/demos/agent_evolution/`, `Makefile`, `tests/runtime/test_otel_langfuse.py`, `operad/algorithms/sweep.py` (4-6 owns), `apps/dashboard/operad_dashboard/contracts.py` (4-2 owns).

## Implementation hints
- Datasets should be small and reproducible: ~50-200 examples each; if you need to synthesize, fix a seed and document it.
- Run each method N=3 times with different seeds; report mean ± stddev. Single runs are not credible.
- "No-training" baseline = the seed agent. "Hand-edit" baseline = a manually improved version of the seed agent (commit it as a separate frozen artifact). These two baselines bracket what TGD must beat.
- Report token-spend honestly. TGD is expensive at training time; Sweep's exploration cost should be apples-to-apples.
- Markdown summary template:
  | task | method | metric | mean | std | tokens | latency |
  Include a `headline_findings` paragraph with the one-line takeaway per task. **Be honest** — if TGD lost, say so and hypothesize why.

## Acceptance
- All three tasks run in `--offline` mode under `verify.sh`.
- Full run (live LLM) produces a `report.json` and a Markdown summary.
- README links the benchmark.
- Headline findings published — even if they're inconvenient.
