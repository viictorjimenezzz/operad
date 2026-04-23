# ISSUES — Known risks, footguns, and gaps

Catalogue of problems identified in the codebase. Each issue carries a
severity tag and a strategy pointer; full implementation direction
lives in the per-stream briefs under `.conductor/`.

**Status log.**
- **2026-04-23** — Every §A, §B, §C, §D issue below was resolved in
  the Phase-1 / Phase-2 / feature PRs merged into `main` (commits
  `a484c49` through `f2bae35`). Kept for historical context.
- **2026-04-23 (post-merge review)** — §E issues are the new findings
  surfaced after the implementation landed. These are the active
  work items; see `.conductor/feature-*.md` and `.conductor/fix-polish.md`.

Severity key:
- **High** — silent correctness risk; user sees wrong behaviour without warning.
- **Med** — honest failure modes but rough DX, dead knobs, or inconsistencies.
- **Low** — polish, docs, or test coverage.

---

## A. Silent correctness risks

### A-1 · Composite-branches-on-payload footgun · High
**Where.** `operad/core/build.py:131, 143, 223` — the tracer's sentinel
is `child.input.model_construct()`, which fills fields with their
Pydantic defaults.
**Problem.** If a composite's `forward()` does
`if x.flag: self.a(x) else: self.b(x)`, only the default branch is
traced. The other edge never lands in `AgentGraph`, and no error fires.
At runtime, behaviour silently differs from the traced graph.
**Strategy.** Wrap the sentinel in a subclass-based proxy (preserving
`isinstance`) that raises `BuildError("payload_branch", ...)` when a
composite reads a payload field *value* during tracing. VISION.md §5.3
and §7 both plan for this.
**Address in:** `.conductor/1-A-core-correctness.md`.

### A-2 · Shared-child mutation leakage · Med
**Where.** `operad/core/build.py:146-163`.
**Problem.** If the same `Agent` instance is attached to two parents,
`_find_attr_name` returns the first match and mutations on the shared
instance affect both edges. Nothing mutates at trace time today, but
the footgun is waiting.
**Strategy.** Emit `warnings.warn` during `abuild_agent` when a child
`id(...)` appears in more than one parent. Document "do not share
instances between parents" in the contributor checklist.
**Address in:** `.conductor/1-A-core-correctness.md`.

### A-3 · `_init_strands` fires before `_trace` validates · Med
**Where.** `operad/core/build.py:231-234`.
**Problem.** `_init_strands` walks the tree before `_trace` runs. If
tracing fails for a type reason, strands has already been initialised
on every leaf, so retry-after-fix leaves stale partial state.
**Strategy.** Reorder the passes in `abuild_agent` to
`validate → trace → init_strands`. Note that a leaf-rooted agent will
still need strands for the root's own `forward` in `_trace`, so the
reorder needs to handle that case — see the stream brief.
**Address in:** `.conductor/1-A-core-correctness.md`.

### A-4 · `reasoning_tokens` is declared-but-unused · Med
**Where.** `operad/core/config.py:34` declares it; no backend threads it.
**Strategy.** Either wire through OpenAI's reasoning-token parameter and
document backend support, or delete the field and push users to `extra`.
Stream A decides.
**Address in:** `.conductor/1-A-core-correctness.md`.

### A-5 · Bedrock silently drops `top_k` / `seed` · Med
**Where.** `operad/models/bedrock.py`.
**Strategy.** Thread both via strands' `additional_request_fields` if
supported, or raise a clear `BuildError` explaining the backend
mismatch. No silent drops.
**Address in:** `.conductor/1-A-core-correctness.md`.

### A-6 · `extra` dict semantics differ per backend · Med
**Where.** `operad/models/{llamacpp,bedrock}.py` splat; `ollama.py`
wraps as `options`; `openai.py` and `lmstudio.py` ignore it.
**Strategy.** Document the exact semantics per backend in a table at
the top of `operad/models/__init__.py`. Where possible converge —
OpenAI's SDK supports `extra_body` for example. Users must get the
same behaviour from the same key wherever feasible.
**Address in:** `.conductor/1-A-core-correctness.md`.

### A-7 · `Latency.score()` is a stub returning `0.0` · Med
**Where.** `operad/metrics/deterministic.py`.
**Problem.** `Latency.score()` returns `0.0` while `measure()` is the
real API. The protocol is satisfied in shape but not in meaning.
**Strategy.** Make `score()` return a normalised scalar (e.g.
`1.0 / (1.0 + latest_measurement)`), keep `measure()` for raw capture,
and document the pairing.
**Address in:** `.conductor/1-A-core-correctness.md`.

---

## B. API / surface gaps vs. the `torch.nn` analogy

### B-1 · No `Agent.state()` / `load_state()` / `clone()` · High for Evolutionary
**Where.** `operad/core/agent.py`.
**Problem.** The analogy promises weights-equivalent serialisation.
`Evolutionary` (VISION §7 north-star) cannot mutate-and-score without
these. There is also no public `__repr__`.
**Strategy.** Add an `AgentState` Pydantic model (role, task, rules,
examples, config, input/output type names, nested children) and three
methods on `Agent`: `state()`, `load_state(s)`, `clone()`.
**Address in:** `.conductor/1-B-agent-state.md`.

### B-2 · `Metric` protocol is not batch-aware or trace-attributed · Med
**Where.** `operad/metrics/base.py`.
**Problem.** Single-pair `score` call only. No `score_batch`, no
cost/token attribution, no correlation with observer events.
**Strategy.** Extend the protocol with an optional `score_batch`
default-implemented via `score`; leave room for a future `on_trace`
hook when observers (Stream C) are in.
**Address in:** `.conductor/2-D-metrics-evaluation.md`.

### B-3 · No `timeout`, retry/backoff, or streaming on `Configuration` · Med
**Where.** `operad/core/config.py`.
**Strategy.** Add `timeout: float | None`, `max_retries: int = 0`,
`backoff_base: float = 0.5`. Thread them into backends where
supported. Streaming is a separate surface and may defer.
**Address in:** `.conductor/1-A-core-correctness.md` (wiring the
fields only; retry logic lands later).

### B-4 · `api_key` handling is inconsistent · Low
**Where.** `operad/models/lmstudio.py` forces `"lm-studio"` if unset.
**Strategy.** Document the fallback in the adapter's module docstring
and leave it (LM Studio genuinely accepts any non-empty key). No code
change unless you're already in the file.
**Address in:** `.conductor/1-A-core-correctness.md`.

### B-5 · No `CLAUDE.md` · Low but high leverage
**Problem.** Claude Code agents working on this repo have no
codebase-specific orientation beyond `AGENTS.md`.
**Strategy.** Add `CLAUDE.md` at the repo root that summarises the
layout, points to `METAPROMPT.md`, and names the `FakeLeaf` test
pattern.
**Address in:** `.conductor/2-K-docs-examples.md`.

---

## C. Coverage gaps vs. VISION.md §7

### C-1 · Missing leaves: `ToolUser`, `Retriever`, `Reflector`, `Router` · High
**Strategy.** Add under `operad/agents/reasoning/components/`. `Router`
is the delicate one — implement it as a leaf emitting a typed `Choice`
and pair with a `Switch` composite that dispatches on the leaf's
output. This preserves the no-payload-branching invariant.
**Address in:** `.conductor/2-E-reasoning-leaves.md`.

### C-2 · Missing patterns: `Debate`, `VerifierLoop` · Med
**Strategy.** These are iterative, so they are *algorithms*, not
composites. ReAct's single-pass nature is correct.
**Address in:** `.conductor/2-F-algorithms.md`.

### C-3 · Missing algorithms: `Evolutionary`, `SelfRefine`, `TalkerReasoner`, `AutoResearch` · Med
**Strategy.** Plain classes in `operad/algorithms/`. `Evolutionary` is
the north-star — depends on Stream B.
**Address in:** `.conductor/2-F-algorithms.md`.

### C-4 · Missing domains: `coding/`, `conversational/`, `memory/` · Med
**Strategy.** Each gets its own stream (G, H, I). Mirror the shape of
`reasoning/`: `<domain>/components/` for leaves, `<domain>/*.py` for
composed patterns.
**Address in:** `.conductor/2-G-coding-domain.md`,
`.conductor/2-H-conversational-domain.md`,
`.conductor/2-I-memory-domain.md`.

### C-5 · No observer protocol · High for production use
**Strategy.** Add `operad/runtime/observers/` with a `Observer`
protocol, a JSONL writer, a Rich TUI, and an OTel stub. One small
hook point in `Agent.invoke`.
**Address in:** `.conductor/2-C-observers.md`.

### C-6 · No dataset-level `evaluate(...)` · Med
**Strategy.** New `operad/eval.py` with
`evaluate(agent, dataset, metrics) -> EvalReport` returning a tidy
row list plus per-metric mean.
**Address in:** `.conductor/2-D-metrics-evaluation.md`.

### C-7 · No `configs/` loader or CLI · Low
**Strategy.** YAML → Pydantic → instantiated agent; two subcommands
(`operad run`, `operad trace`).
**Address in:** `.conductor/2-J-cli-configs.md`.

### C-8 · No launchers (process, macOS Terminal) · Low
**Strategy.** Defer. Revisit after the observer protocol lands.

---

## D. Content, polish, and coverage

### D-1 · `examples/` has only `parallel.py` · Low
**Strategy.** One example per major abstraction: Pipeline, ReAct,
BestOfN, custom Agent, Mermaid export, eval loop.
**Address in:** `.conductor/2-K-docs-examples.md`.

### D-2 · Every leaf ships with empty `examples` · Med
**Strategy.** Populate one or two canonical typed few-shot
demonstrations on each leaf. This is the first in-repo demonstration
of the feature.
**Address in:** `.conductor/2-K-docs-examples.md`.

### D-3 · Weak coverage on exception paths, deep nesting, non-llamacpp integration · Med
**Strategy.** Offline error-path tests + integration-test skeletons
for openai, ollama, lmstudio mirroring the existing llamacpp one.
**Address in:** `.conductor/2-L-integration-tests.md`.

### D-4 · `ReAct.__init__` uses an untyped `config` parameter · Low
**Where.** `operad/agents/reasoning/react.py:89`.
**Strategy.** Type it as `Configuration`. Trivial fix; roll into
Stream A or K.

---

---

## E. Post-merge review (active work)

Issues surfaced after the Phase-1/2 merges landed. Each points at the
brief that picks it up.

### E-1 · Examples disagree on `Configuration` · Med
**Where.** Every file under `examples/`.
**Problem.** Model defaults vary (`"default"`, `"demo"`, `"offline"`,
hard-coded `"qwen2.5-7b-instruct"`); host defaults to
`127.0.0.1:8080` for network examples and `127.0.0.1:0` for offline
examples. A user cannot just `uv run python examples/<any>.py`.
**Strategy.** Ship a single canonical setup (`google/gemma-4-e4b` on
`127.0.0.1:9000`) and a shared helper `examples/_config.py` that
every network example imports.
**Address in:** `.conductor/feature-examples-and-demo.md`.

### E-2 · Domain schema files inconsistent · Low
**Where.** `coding/types.py`, `memory/shapes.py`; inline schemas in
`conversational/talker.py` and `reasoning/react.py` +
`reasoning/components/*.py`.
**Problem.** Three different conventions for the same job.
**Strategy.** Standardise on `schemas.py` in every domain, with
`DeprecationWarning` shims at the old paths for one release.
**Address in:** `.conductor/feature-schemas-standardization.md`.

### E-3 · No `structuredio` toggle · Med
**Where.** `operad/core/agent.py::Agent.forward` always passes
`structured_output_model` to strands; `render_input` always renders
XML.
**Problem.** Backends without native structured output, or users
wanting to inspect the wire string, have no opt-out.
**Strategy.** `Configuration.structuredio: bool = True`; when False,
render as XML and parse the textual response. A test must assert
field descriptions surface on both paths.
**Address in:** `.conductor/feature-structuredio.md`.

### E-4 · `timeout` / `max_retries` / `backoff_base` declared but not
implemented · Med
**Where.** `operad/core/config.py:38-40` declares them;
`operad/models/params.py` threads them only to the OpenAI client.
`Agent.forward` has no retry loop.
**Problem.** Flaky endpoints kill real-world usage on first transient
error.
**Strategy.** Add `operad/runtime/retry.py` with exponential backoff;
wrap strands calls in `Agent.forward`; surface `retries` in observer
metadata.
**Address in:** `.conductor/feature-retry-backoff.md`.

### E-5 · `hash_config` hashes host verbatim (may carry auth) · Low
**Where.** `operad/core/output.py:71`.
**Problem.** Host values like `user:pass@host:port` leak credentials
into the hash (which is stable and potentially logged).
**Strategy.** Strip `user:pass@` prefix before hashing.
**Address in:** `.conductor/fix-polish.md`.

### E-6 · Leaf-rooted `build()` skips output validation · Low
**Where.** `operad/core/build.py:343`.
**Problem.** When the root is a default-forward leaf, `_trace` is
skipped — correct for graph capture, but the output type is first
verified only at `invoke`. Late failure.
**Strategy.** Cheap sentinel-output check at build time.
**Address in:** `.conductor/fix-polish.md`.

### E-7 · `Metric.score_batch` dispatched via `hasattr` · Low
**Where.** `operad/eval.py:36-41`.
**Problem.** Not a formal Protocol member; type checkers miss it.
**Strategy.** Promote to a `MetricBase` class with a default
implementation; subclass from concrete metrics.
**Address in:** `.conductor/feature-typed-dataset.md`.

### E-8 · No streaming support · Med
**Where.** `operad/core/agent.py::forward` awaits the full result;
`AgentEvent` has no `"chunk"` kind.
**Problem.** VISION-aligned but unshipped. TUIs can't show mid-run
state; users waiting 30 s for a long reasoner see nothing.
**Strategy.** `Configuration.stream: bool`; `Agent.stream(x)`
async-iterator; new observer `"chunk"` event.
**Address in:** `.conductor/feature-streaming.md`.

### E-9 · No Markdown renderer, no chat-template awareness · Med
**Where.** `operad/core/render.py` is XML-only.
**Problem.** VISION §7 promises both. Some models do better with
Markdown or their native chat template.
**Strategy.** Split `render.py` into a package with `xml.py`,
`markdown.py`, `chat.py`; add `Configuration.renderer` selector.
**Address in:** `.conductor/feature-markdown-renderer.md`.

### E-10 · `test_sandbox.py::test_timeout_kills_process` emits
`RuntimeWarning` · Low
**Where.** `tests/test_sandbox.py`.
**Problem.** An `AsyncMock` coroutine is never awaited. Test passes
but CI logs are noisy and the warning hides real issues.
**Strategy.** Fix the mock plumbing so the coroutine is consumed;
optionally enforce `-W error::RuntimeWarning` in pytest config.
**Address in:** `.conductor/fix-polish.md`.

### E-11 · Tracing is opt-in; no default visibility surface · Med
**Where.** `operad/runtime/observers/*`, `operad/runtime/trace.py`.
**Problem.** `TraceObserver`, `JsonlObserver`, `RichDashboardObserver`
all exist but require manual registration. "See what my agents are
doing" is not one line.
**Strategy.** `operad.tracing.watch()` context manager + `OPERAD_TRACE`
env-var auto-attach + `operad tail <trace.jsonl>` CLI subcommand.
**Address in:** `.conductor/feature-tracing-watch.md`.

### E-12 · No per-Agent default sampling config · Med
**Where.** Every leaf in `operad/agents/reasoning/components/`.
**Problem.** A `Classifier` and a `Reasoner` should have different
default temperatures, but they don't. Users must re-specify sampling
every time.
**Strategy.** `default_sampling: ClassVar[dict]` on each leaf,
merged into `Configuration` at `__init__` for fields the user did
not set explicitly (`model_fields_set`).
**Address in:** `.conductor/feature-default-sampling.md`.

### E-13 · No typed `Dataset` primitive · Med
**Where.** `operad/eval.py` accepts raw `list[tuple[In, Out]]`.
**Problem.** Eval reports have no `hash_dataset`, so reproducibility
is a two-of-three story (graph, input — but not dataset).
**Strategy.** `operad/datasets.py` with `Dataset[In, Out]`, NDJSON
I/O, and a stable `hash_dataset`. Thread into `EvalReport`.
**Address in:** `.conductor/feature-typed-dataset.md`.

### E-14 · Native Anthropic backend missing · Low
**Where.** `operad/models/`.
**Problem.** Every hosted provider today is OpenAI-compatible; Claude
users go via an indirect shim.
**Strategy.** Add `operad/models/anthropic.py` (strands' AnthropicModel),
extend `Backend` Literal, thread `reasoning_tokens` to Anthropic's
extended-thinking budget.
**Address in:** `.conductor/feature-anthropic-backend.md`.

### E-15 · Single-shot sandbox (~100 ms / call); no pool · Low
**Where.** `operad/runtime/launchers/sandbox.py`.
**Problem.** Every tool call spawns a fresh Python interpreter. A
tool-heavy workload is dominated by cold-start overhead.
**Strategy.** `SandboxPool` that holds long-lived workers speaking a
JSON-lines protocol; `PooledSandboxedTool` wrapper.
**Address in:** `.conductor/feature-process-pool-launcher.md`.

### E-16 · No Trace-vs-Trace diff · Low
**Where.** `operad/runtime/trace.py`.
**Problem.** Two `Trace`s from the same graph have no structured
comparison. Hunting regressions after a prompt change is manual.
**Strategy.** `trace_diff(prev, next) -> TraceDiff` mirroring
`Agent.diff(other)`'s shape.
**Address in:** `.conductor/feature-trace-diff.md`.

---

## How to use this file

- When you open a PR, cite the issue numbers you address in the
  description.
- If you find a new issue while working, add it here in the matching
  section (most likely §E or a new §F) and include the update in
  your PR.
- If a fix is out of scope for your stream, leave a one-line note in
  `.conductor/notes/` (create the folder if needed) and keep moving.
- When every active issue is resolved, mark the §E entries "RESOLVED"
  with a commit hash and append a new section for the next round.
