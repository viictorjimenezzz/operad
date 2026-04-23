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
- **`await agent(x)` returns `OperadOutput[Out]`.** Reach into
  `.response` for the typed payload; `hash_*` / `run_id` / `agent_path`
  / `latency_ms` / `prompt_tokens` live on the envelope. Composite
  `forward` methods still return plain `Out`, so children unwrap
  `.response` at each call site (see `operad/agents/pipeline.py`).
- **Components vs. algorithms.** `In -> Out` contract → component
  (subclass `Agent[In, Out]`, lives in `agents/`). Loop-with-metric
  feedback whose natural API is not `__call__(x)` → algorithm (plain
  class with `run(...)`, lives in `algorithms/`).
- **Three renderers.** `format_system_message` selects between
  `"xml"` (default; XML-tagged sections), `"markdown"` (headings +
  schema table), and `"chat"` (`list[{"role","content"}]` for backends
  with native chat templates). Pick via `Configuration(renderer=...)`
  or set `renderer: ClassVar[str] = "markdown"` on any subclass.
  Modules live under `operad/core/render/`.
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
- **Inspect a built agent.** `agent.operad()` prints every leaf's
  rendered prompt; `agent.diff(other)` compares two agents. In Jupyter
  / VS Code notebooks, evaluating a built agent renders its Mermaid
  graph inline via `_repr_html_` (requires a Mermaid-aware front-end,
  e.g. `jupyterlab-mermaid` or the VS Code Jupyter extension).
- **Cassette replay for LLM-backed tests.** Name the `cassette` fixture
  in a test that exercises a default-forward leaf; the fixture
  monkeypatches `Agent.forward` to serve responses from
  `tests/cassettes/<test_name>.jsonl`. Default mode is **replay** —
  missing keys raise `CassetteMiss`. To refresh a cassette against a
  real backend:
  `OPERAD_CASSETTE=record OPERAD_INTEGRATION=llamacpp \
   uv run pytest tests/<file> -v`.
  Cassette files store hashes + the serialised response only (never
  the rendered prompt or API keys), so they are safe to commit. Use
  `FakeLeaf` for pure-offline unit tests with no LLM in the loop;
  reach for cassettes when you need a *specific* model response that
  would otherwise require the network.
- **One-liner tracing.** `with operad.tracing.watch(jsonl="run.jsonl"):`
  attaches the Rich TUI (optional `observers` extra) and an NDJSON event
  log for the duration of the block, unregistering only what it added.
  Setting `OPERAD_TRACE=/tmp/run.jsonl` at `import operad.tracing` time
  auto-attaches the JSONL writer. Replay post-mortem with
  `uv run operad tail run.jsonl [--speed=0]`.

## Where to find

- Core abstractions — `operad/core/`
- Component library — `operad/agents/<domain>/`
- Orchestrators — `operad/algorithms/`
- Known issues and footguns — [ISSUES.md](ISSUES.md)
- Vision / design rationale — [VISION.md](VISION.md)
- Stream briefs for in-flight work — `.conductor/`
- Sub-agent onboarding — [METAPROMPT.md](METAPROMPT.md)
