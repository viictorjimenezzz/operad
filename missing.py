"""Gaps between the shipped codebase and VISION.md §7.

This file is a machine-readable checklist. Each `TODO_*` block names an
unrealised capability, why it matters, and where it should live. Grep
for `TODO_` to find the next piece of fundamental work.

Status of briefs under `.conductor/` at 2026-04-23 — all implemented:
    Phase 1: A (core correctness), B (Agent state)
    Phase 2: C (observers), D (metrics/eval), E (reasoning leaves),
             F (algorithms), G (coding), H (conversational), I (memory),
             J (CLI), K (docs/examples), L (integration tests)
    Features: agent introspection, OperadOutput, Trace + replay + cost,
              cassette, sweep, mutation ops, federated example, sandbox.

Everything below is FUNDAMENTAL package work (not new agents) that
VISION.md still expects before the library feels solid.
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────
# RENDERING & I/O SHAPE
# ─────────────────────────────────────────────────────────────────────

TODO_STRUCTURED_IO = """
Add `structuredio: bool = True` to `Configuration`.

When True (default, today's behaviour): pass the Pydantic instance
directly to strands via `structured_output_model`; let strands handle
schema injection and parsing.

When False: render input as XML (current `render_input` path), emit
the output schema verbatim, parse the model's textual response back
into `Out`. Useful for backends that don't support native structured
output or when the user wants to see the exact wire string.

In both cases: `Field(description=...)` and the output schema must
reach the model. Add an offline test that asserts field descriptions
appear in the rendered payload on *both* paths.

Where: operad/core/config.py, operad/core/agent.py (forward dispatch),
operad/core/render.py (may need a JSON-mode renderer sibling).
"""

TODO_MARKDOWN_RENDERER = """
Add a Markdown renderer alongside the XML one and a mechanism to pick
between them per-agent (`Agent.format_system_message` is already
overridable; give it a first-class toggle on Configuration or on the
Agent class via `renderer: Literal["xml", "markdown", "chat_template"]`).

VISION.md §7 calls out `render.py: additional renderers`.

Where: operad/core/render.py (+ a `markdown.py`), wiring in
`Agent.format_system_message`.
"""

TODO_CHAT_TEMPLATE_AWARE = """
Some backends (llama.cpp with --chat-template, Ollama, LM Studio) do
better when the system/user split respects the model's native template
(ChatML, Mistral, Gemma). Investigate detecting the template from the
model name or the backend's /props endpoint and route the rendered
prompt into the correct role fields instead of concatenating.

Where: operad/core/render.py + per-backend hints in operad/models/*.
"""


# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION & RUNTIME PLUMBING
# ─────────────────────────────────────────────────────────────────────

TODO_DEFAULT_CONFIG_PER_AGENT = """
Allow each Agent subclass to declare an opinionated default sampling
profile (temperature, top_p, max_tokens) that merges with the user's
Configuration at construction time.

Design sketch:

    class Classifier(Agent[In, Out]):
        default_sampling: ClassVar[dict[str, Any]] = {"temperature": 0.1}

    class Reasoner(Agent[In, Out]):
        default_sampling: ClassVar[dict[str, Any]] = {"temperature": 0.7}

At __init__, merge `default_sampling` into `config` (overrides follow
the user's explicit Configuration fields, so user wins). This makes
the starter pack work well out of the box.

Caveat: backend selection (host, port, api_key) stays the caller's
choice. Only sampling knobs live in the class default.

Where: operad/core/agent.py (__init__ merge), per-leaf class bodies.
"""

TODO_RETRY_BACKOFF_IMPL = """
`Configuration.timeout`, `max_retries`, `backoff_base` are declared and
partially threaded to the OpenAI adapter. They are not honoured by
llamacpp/lmstudio/ollama/bedrock, and there is no retry loop in
`Agent.forward`.

Implement: an exponential-backoff retry wrapper around the strands
`invoke_async` call, observable via the `AgentEvent.metadata` dict so
retries appear in the trace.

Where: operad/core/agent.py:forward (wrap strands call), possibly a
small helper `operad/runtime/retry.py`.
"""

TODO_STREAMING = """
No streaming support today. strands exposes stream tokens; operad
swallows them by awaiting the final result. Add a `stream: bool` toggle
on Configuration and an `Agent.stream(x)` async-iterator method that
yields partial `OperadOutput`-like envelopes.

Observer events for streaming need a new `kind="chunk"` variant so
dashboards can show mid-run state.

Where: operad/core/agent.py, operad/runtime/observers/base.py.
"""

TODO_CONFIG_HASH_AUTH = """
`hash_config` excludes `api_key` but `host` may contain credentials
(e.g. `user:pass@host:port`). Either strip credentials from the host
before hashing or document the risk prominently.

Where: operad/core/output.py:hash_config.
"""


# ─────────────────────────────────────────────────────────────────────
# TRACING VISIBILITY & DX
# ─────────────────────────────────────────────────────────────────────

TODO_TRACING_WATCH = """
`TraceObserver` + `JsonlObserver` + `RichDashboardObserver` exist, but
the user has to wire them manually. Add a one-liner convenience:

    with operad.tracing.watch():      # auto-attaches Rich + Jsonl
        out = await agent(x)

Plus an env-var auto-attach (`OPERAD_TRACE=/tmp/traces.jsonl`) so users
get traces by setting one variable.

Also add `operad tail <trace.jsonl>` subcommand to replay an NDJSON log
through a live Rich display.

Where: new operad/tracing.py (module-level watch() context manager),
operad/cli.py (tail subcommand).
"""

TODO_TRACE_DIFF = """
Given two `Trace`s from the same graph, produce a human-readable diff:
per-step input/output deltas, hash changes, latency deltas. Pairs with
`Agent.diff(other)` for a full regression-hunting story.

Where: new operad/runtime/trace_diff.py.
"""


# ─────────────────────────────────────────────────────────────────────
# SCHEMA / TYPE HYGIENE
# ─────────────────────────────────────────────────────────────────────

TODO_SCHEMAS_STANDARDIZATION = """
Today the schema-file naming is inconsistent:

  operad/agents/coding/types.py           ← OK, but differs from others
  operad/agents/memory/shapes.py          ← differs again
  operad/agents/reasoning/react.py        ← types inline with composition
  operad/agents/conversational/talker.py  ← types inline with composition

Standardise on `schemas.py` in each domain (and in each component
subfolder if it has >1 shape). Update the Stream-K examples / CLAUDE.md
to reflect the convention.

Where: everywhere under operad/agents/*.
"""

TODO_TYPED_DATASET = """
`evaluate(agent, dataset, metrics)` takes `list[tuple[In, Out]]`. Add
a typed `Dataset[In, Out]` primitive with:

  - a content hash (`hash_dataset`) for reproducibility
  - `save` / `load` via NDJSON
  - `__iter__`, `__len__`, indexing
  - version tags so evaluation reports can cite the dataset version

This lets `EvalReport` carry `hash_dataset` alongside `hash_graph`,
completing the reproducibility story.

Where: operad/datasets.py (new module).
"""

TODO_METRIC_SCORE_BATCH = """
`Metric.score_batch` is currently dispatched via `hasattr` in eval.py.
Promote it to a formal Protocol member with a default implementation:

    async def score_batch(self, pairs):
        return [await self.score(p, e) for p, e in pairs]

Where: operad/metrics/base.py.
"""


# ─────────────────────────────────────────────────────────────────────
# EXAMPLES / DX
# ─────────────────────────────────────────────────────────────────────

TODO_EXAMPLES_SHARED_CONFIG = """
Examples diverge in how they build `Configuration`:

  best_of_n.py / pipeline.py / custom_agent.py → llamacpp, host env,
    model=$OPERAD_LLAMACPP_MODEL (default "default")
  memory_demo.py → model="qwen2.5-7b-instruct" hard-coded
  observer_demo.py / evolutionary_demo.py → model="demo"
  eval_loop.py / mermaid_export.py → offline host "127.0.0.1:0"
  federated.py → mix of llamacpp + openai

Pick one canonical runnable setup (e.g. llama-server on 127.0.0.1:9000
serving google/gemma-4-e4b) and add a shared helper:

    # examples/_config.py
    def local_config() -> Configuration:
        return Configuration(
            backend="llamacpp",
            host=os.environ.get("OPERAD_LLAMACPP_HOST", "127.0.0.1:9000"),
            model=os.environ.get("OPERAD_LLAMACPP_MODEL", "google/gemma-4-e4b"),
        )

All network-backed examples import and use it. Offline-only examples
(eval_loop, mermaid_export, evolutionary_demo) keep their FakeLeaf
setup with a clear comment at the top.

Where: new examples/_config.py, update every example/*.py.
"""

TODO_DEMO_SCRIPT = """
Add `demo.py` at the repo root: a single runnable script that shows,
in one iterm2 window with Rich output, what operad offers:

  1. Build a small ReAct-style graph; print the Mermaid.
  2. Show `agent.operad()` output — the actual prompt sent to the model.
  3. Attach a Rich observer; run one invocation with animated progress.
  4. Dump the Trace as JSON; show cost estimate.
  5. Mutate the agent with an Op; show `agent.diff(mutated)`.

Target: fish shell + iterm2. No deep dependencies beyond what operad
already has under the `observers` optional extra.

Where: demo.py at repo root.
"""


# ─────────────────────────────────────────────────────────────────────
# BACKEND & LAUNCHER COVERAGE
# ─────────────────────────────────────────────────────────────────────

TODO_PROCESS_POOL_LAUNCHER = """
`SandboxedTool` spawns a fresh Python interpreter per call (~100 ms).
A process pool reusing workers drops that to <5 ms. Needed for any
real agent-with-tools workload.

VISION.md §7 lists `launchers/` with `asyncio (default) / process /
macOS Terminal` — only asyncio and single-shot process exist.

Where: operad/runtime/launchers/process_pool.py (new).
"""


# ─────────────────────────────────────────────────────────────────────
# TEST SUITE HYGIENE
# ─────────────────────────────────────────────────────────────────────

TODO_SANDBOX_TIMEOUT_WARNING = """
`tests/test_sandbox.py::test_timeout_kills_process` triggers a
`RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was
never awaited`. The test passes but the warning indicates an AsyncMock
leak. Fix the mock plumbing so the coroutine is consumed.

Where: tests/test_sandbox.py.
"""

TODO_LEAF_ROOT_INIT_SEMANTICS = """
`_trace` is skipped when the root is a default-forward leaf (build.py
line 343). That is correct for graph-capture but means a leaf-root
never gets its output type-checked at build() time — the first
`invoke` discovers type mismatches. Add a cheap output-shape validation
for leaf roots too (construct a sentinel output, run isinstance check
on the declared output class).

Where: operad/core/build.py:abuild_agent.
"""


# ─────────────────────────────────────────────────────────────────────
# OPEN VISION §7 ITEMS STILL UNBUILT
# ─────────────────────────────────────────────────────────────────────

TODO_AUTORESEARCHER = """
VISION.md north-star milestone #2: "`AutoResearcher` on 8 concurrent
llama-server slots: plan → retrieve → read → write → verify → reflect,
all local, all observable in a live dashboard, with per-agent metrics
feeding an outer best-of-N loop."

Blocked on: `Retriever` (present), `Reflector` (present), `Evolutionary`
(present). Not yet assembled.

Where: new operad/algorithms/auto_research.py or a dedicated
operad/agents/research/ domain — pick after the fundamentals above
land.
"""


__all__ = [name for name in globals() if name.startswith("TODO_")]
