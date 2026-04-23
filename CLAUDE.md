# operad — Claude Code orientation

See [METAPROMPT.md](METAPROMPT.md) for sub-agent onboarding. This file
is a quick map for humans and one-off Claude sessions.

## Layout

```
operad/
  core/              Agent, Example, Configuration, build, graph, render
  agents/            typed components (torch.nn-style library)
    pipeline.py      structural operators
    parallel.py
    reasoning/
      components/    Reasoner, Actor, Extractor, Evaluator,
                     Classifier, Planner, Critic
      react.py       Reason-Act-Observe-Evaluate composition
  algorithms/        plain orchestrators with metric feedback
                     (BestOfN, Candidate, Score)
  metrics/           Metric protocol + deterministic scorers
  models/            per-backend adapters
  runtime/           slot registry + observers
  utils/errors.py    BuildError + BuildReason
tests/               offline suite + opt-in integration
examples/            narrative examples, one per abstraction
```

## Conventions

- **Components declare their contract as class attributes** (`input`,
  `output`, `role`, `task`, `rules`, `examples`). Instances override via
  constructor kwargs only — no wrapper object, no hidden state.
- **Composites are pure routers.** `forward` on a composite routes
  between children; it never inspects payload *values*.
- **`build()` before invoke.** Leaves need `config`; composites do not.
  `build()` symbolically traces the tree, type-checks each edge, and
  wires `strands.Agent` for leaves — all before a single token.
- **Components vs. algorithms.** `In -> Out` contract → component
  (subclass `Agent[In, Out]`, lives in `agents/`). Loop-with-metric
  feedback whose natural API is not `__call__(x)` → algorithm (plain
  class with `run(...)`, lives in `algorithms/`).
- **Offline tests use `FakeLeaf`** from `tests/conftest.py`. Tests that
  hit a real model go to `tests/integration/` and are gated by
  `OPERAD_INTEGRATION`.
- **`Agent.invoke` returns `OperadOutput[Out]`.** The typed payload is
  at `.response`; the envelope also carries `run_id`, `agent_path`,
  timings, and seven `hash_*` reproducibility fields. `forward` still
  returns bare `Out` — only composites need to unwrap children via
  `(await child(x)).response`. Attach a `TraceObserver` to capture a
  full run as a `Trace`; the `Trace` is the reproducibility artefact
  for any production run (save/load to JSON or NDJSON; re-score
  against new metrics via `replay()` without touching an LLM).

## Common tasks

- **Add a leaf.** Follow `operad/agents/reasoning/components/reasoner.py`.
- **Add a domain.** Copy the shape of `operad/agents/reasoning/`.
- **Run tests.** `uv run pytest tests/`.
- **Run an example.** `uv run python examples/<name>.py` (start a local
  llama-server first for network-requiring ones).
- **Integration tests.**
  `OPERAD_INTEGRATION=llamacpp OPERAD_LLAMACPP_HOST=127.0.0.1:8080 \
   OPERAD_LLAMACPP_MODEL=<model> uv run pytest tests/integration -v`.

## Where to find

- Core abstractions — `operad/core/`
- Component library — `operad/agents/<domain>/`
- Orchestrators — `operad/algorithms/`
- Known issues and footguns — [ISSUES.md](ISSUES.md)
- Vision / design rationale — [VISION.md](VISION.md)
- Stream briefs for in-flight work — `.conductor/`
- Sub-agent onboarding — [METAPROMPT.md](METAPROMPT.md)
