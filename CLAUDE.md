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

## Common tasks

- **Add a leaf.** Follow `operad/agents/reasoning/components/reasoner.py`.
- **Add a domain.** Copy the shape of `operad/agents/reasoning/`.
- **Run tests.** `uv run pytest tests/`.
- **Run an example.** `uv run python examples/<name>.py` (start a local
  llama-server first for network-requiring ones).
- **Integration tests.**
  `OPERAD_INTEGRATION=llamacpp OPERAD_LLAMACPP_HOST=127.0.0.1:8080 \
   OPERAD_LLAMACPP_MODEL=<model> uv run pytest tests/integration -v`.
- **Inspect a built agent.** `agent.operad()` prints every leaf's
  rendered prompt; `agent.diff(other)` compares two agents. In Jupyter
  / VS Code notebooks, evaluating a built agent renders its Mermaid
  graph inline via `_repr_html_` (requires a Mermaid-aware front-end,
  e.g. `jupyterlab-mermaid` or the VS Code Jupyter extension).

## Where to find

- Core abstractions — `operad/core/`
- Component library — `operad/agents/<domain>/`
- Orchestrators — `operad/algorithms/`
- Known issues and footguns — [ISSUES.md](ISSUES.md)
- Vision / design rationale — [VISION.md](VISION.md)
- Stream briefs for in-flight work — `.conductor/`
- Sub-agent onboarding — [METAPROMPT.md](METAPROMPT.md)
