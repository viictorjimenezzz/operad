# ISSUES — Known risks, footguns, and gaps

Catalogue of problems identified in the current codebase (operad v0.1.0
as of 2026-04-23). Each issue carries a severity tag and a strategy
pointer; full implementation direction lives in the per-stream briefs
under `.conductor/`.

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

## How to use this file

- When you open a PR, cite the issue numbers you address in the
  description.
- If you find a new issue while working, add it here in the matching
  section and include the update in your PR.
- If a fix is out of scope for your stream, leave a one-line note in
  `.conductor/notes/` (create the folder if needed) and keep moving.
