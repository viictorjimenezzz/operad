# operad Benchmark

Reproducible comparison of operad's five optimizers — TGD, Momentum,
EvoGradient, OPRO, APE — against a prompt-sweep baseline and two frozen
baselines (no-train, hand-edit) across three tasks.

---

## Tasks

| Key  | Name               | Metric      | Examples | Description                                   |
|------|--------------------|-------------|----------|-----------------------------------------------|
| cls  | classification     | ExactMatch  | 100      | 10-class banking intent classification        |
| sum  | summarization      | Rouge1      | 50       | One-sentence doc summarization                |
| tool | tool_use           | ExactMatch  | 50       | Tool-call selection across 5 tools            |

All datasets are synthesized inline with a fixed seed (42) — no external
downloads required.

---

## Methods

| Method    | Description                                                   |
|-----------|---------------------------------------------------------------|
| no_train  | Frozen seed agent — lower bracket                             |
| hand_edit | Manually improved prompt — upper bracket                      |
| sweep     | Cartesian grid over temperature + task variants; best on train |
| tgd       | Textual Gradient Descent (gradient accumulation via Trainer)  |
| momentum  | TGD with rolling gradient history (MomentumTextGrad)          |
| evo       | Population-based mutation/selection (EvoGradient)             |
| opro      | LLM-as-optimizer over parameter history (OPROOptimizer)       |
| ape       | Sample-and-rank candidate rewrites (APEOptimizer)             |

`tgd`, `momentum`, `opro`, and `ape` require a live LLM (`config` must
be set via `OPERAD_API_KEY` or equivalent). `no_train`, `hand_edit`,
`sweep`, and `evo` run fully offline.

---

## Methodology

**Splits**: each dataset is split 60/20/20 (train/val/test) using
`random_split` with three seeds (0, 1, 2). Results are reported as
mean ± stddev over the three seeds.

**Training budget**: 2 epochs/generations by default (pass
`--train-epochs N` to change).

**Sweep selection**: the Cartesian grid is scored on the train split;
the best combination is evaluated on the test split.

**Token accounting**: `TokenCounter` records prompt + completion tokens
consumed during training. Evaluation tokens are not counted.

**Honest baselines**: the `no_train` baseline is the unmodified seed
agent. `hand_edit` is a manually improved prompt committed directly
as code — it is the ceiling a careful human can reach in minutes.
Any optimizer that does not beat `hand_edit` is not worth the API cost.

---

## Results

*Fill in after running `uv run python examples/benchmark/run.py --out report.json`.*

| task           | method    | metric      | mean | std  | tokens | latency |
|----------------|-----------|-------------|------|------|--------|---------|
| classification | no_train  | exact_match | —    | —    | —      | —       |
| classification | hand_edit | exact_match | —    | —    | —      | —       |
| classification | sweep     | exact_match | —    | —    | —      | —       |
| classification | tgd       | exact_match | —    | —    | —      | —       |
| classification | momentum  | exact_match | —    | —    | —      | —       |
| classification | evo       | exact_match | —    | —    | —      | —       |
| classification | opro      | exact_match | —    | —    | —      | —       |
| classification | ape       | exact_match | —    | —    | —      | —       |
| summarization  | …         | rouge1      | —    | —    | —      | —       |
| tool_use       | …         | exact_match | —    | —    | —      | —       |

---

## Headline Findings

*Fill in after running the full benchmark. Be honest — if TGD lost to
Sweep, say so and hypothesize why (token cost, task too easy for gradient
signal, etc.).*

**classification**: —

**summarization**: —

**tool_use**: —

---

## Reproducing

```bash
# Offline smoke (no LLM, ~5 examples per split, evo/sweep/baselines only)
uv run python examples/benchmark/run.py \
    --offline --max-examples 5 --seeds 0 \
    --methods no_train,hand_edit,sweep,evo

# Full run (live LLM, all methods, 3 seeds)
uv run python examples/benchmark/run.py --out report.json

# Specific subset
uv run python examples/benchmark/run.py \
    --tasks cls,sum \
    --methods no_train,tgd,evo \
    --seeds 0,1 \
    --train-epochs 3 \
    --out my_report.json
```

Set your LLM provider before running the full benchmark:

```bash
export ANTHROPIC_API_KEY=sk-...      # or OPENAI_API_KEY, etc.
```

Pass `--methods no_train,hand_edit,sweep,evo` to skip the LLM-dependent
optimizers (TGD, Momentum, OPRO, APE).
