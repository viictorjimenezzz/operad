# PLAN — Implementation plan for §E issues

Companion to `ISSUES.md` §E and the briefs under `.conductor/feature-*.md`.
This plan sequences the active work, names coordination points, and
shows how each solution stays aligned with `VISION.md` and
`AGENTS.md`.

---

## 1. Guiding principles

Every brief must satisfy four non-negotiable constraints inherited
from the canon:

- **`torch.nn` analogy preserved** — `Agent[In, Out]` is the only
  component primitive; algorithms remain plain classes. No brief
  promotes an algorithm to an `Agent` or vice versa.
- **Composite purity preserved** — composites route on structure (or
  on the typed output of a child `Router`); no brief introduces
  payload-field branching inside a composite `forward`.
- **Construction stays side-effect-free** — `__init__` never contacts
  a provider; `build()` remains the single compile step. E-4 (retry)
  and E-8 (streaming) both wrap the *runtime* path, not the build
  path.
- **Surgical changes** — each brief touches a tight file list.
  Adjacent code is not "improved" in passing; unrelated rough edges
  are logged in `ISSUES.md`, not fixed in-stream.

Any solution that weakens one of these in exchange for local
convenience should be rejected in review.

---

## 2. Dependency map

The 16 §E issues split into four mutually-exclusive file-conflict
classes.

| Class | Touches | Issues |
| --- | --- | --- |
| **Core surface** | `operad/core/agent.py`, `operad/core/config.py`, `operad/core/render.py`/`render/`, `operad/runtime/observers/base.py` | E-3, E-4, E-8, E-9, E-12 |
| **Reproducibility** | `operad/eval.py`, `operad/metrics/base.py`, `operad/datasets.py` (new), `operad/runtime/trace.py`, `operad/runtime/trace_diff.py` (new) | E-7, E-13, E-16 |
| **Adoption / additive** | new files only | E-11, E-14, E-15 |
| **Polish / cross-cutting** | scattered one-liners | E-1, E-2, E-5, E-6, E-10 |

Within the **core surface** class, the strict conflict chain is:

```
E-12 (Agent.__init__ merge)
  └── parallel with →
E-3  (Agent.forward dispatch on structuredio, format_system_message can return str | list)
  ├── E-4  (retry wrapper around the forward body)   [rebases lightly]
  ├── E-9  (renderer dispatch in format_system_message) [rebases lightly]
  └── E-8  (stream method; wraps strands streaming)  [needs both E-3 and E-9]
```

Within **reproducibility**:

```
E-13 (Dataset + EvalReport hashes) pairs with
E-7  (formal Metric.score_batch)   — same PR is cleanest
E-16 (trace_diff)                  — independent; no code overlap
```

Everything else is truly independent and can merge in any order.

---

## 3. Rollout in four waves

The plan runs four sequential waves. Inside a wave, agents merge in
parallel.

### Wave A — mechanical & additive (no ordering constraints)

Run concurrently. Nothing blocks anything.

| Brief | Issue | Scope |
| --- | --- | --- |
| `feature-schemas-standardization.md` | E-2 | Rename `types.py` / `shapes.py` → `schemas.py` with deprecation shims |
| `feature-default-sampling.md` | E-12 | `default_sampling: ClassVar[dict]` on leaves; merge in `Agent.__init__` |
| `feature-anthropic-backend.md` | E-14 | New `operad/models/anthropic.py`; extend `Backend` literal |
| `feature-process-pool-launcher.md` | E-15 | New `operad/runtime/launchers/pool.py` |
| `feature-trace-diff.md` | E-16 | New `operad/runtime/trace_diff.py` |
| `feature-tracing-watch.md` | E-11 | New `operad/tracing.py` + `operad tail` CLI |
| `fix-polish.md` | E-5, E-6, E-10 | Strip host auth before hashing; leaf-root output check; kill `AsyncMock` warning |

Why first: no merge risk, clears the smallest issues off the board,
and E-11 / E-12 land in time to be used by later waves.

### Wave B — core surface changes (ordered within)

Merge **E-3 first, then E-4 in parallel with E-9, then E-8 last.**
E-3 establishes the dispatch shape inside `Agent.forward`; E-4 adds a
retry wrapper around its body; E-9 extends `format_system_message` to
return `str | list[dict]`; E-8 then layers streaming on top.

| Order | Brief | Issue |
| --- | --- | --- |
| 1 | `feature-structuredio.md` | E-3 |
| 2a | `feature-retry-backoff.md` | E-4 |
| 2b | `feature-markdown-renderer.md` | E-9 |
| 3 | `feature-streaming.md` | E-8 |

Coordination rules (see §4).

Why second: these are the load-bearing surface changes. Everything
else either predates them (Wave A) or builds on them (Wave C, D).

### Wave C — reproducibility

| Brief | Issue | Scope |
| --- | --- | --- |
| `feature-typed-dataset.md` | E-13 + E-7 | `Dataset[In, Out]`; `MetricBase` with `score_batch`; `EvalReport.hash_dataset` |

Why third: `Dataset` benefits from `structuredio` (E-3) being stable,
because it round-trips typed rows through the same serialisation path.

### Wave D — showcase

| Brief | Issue | Scope |
| --- | --- | --- |
| `feature-examples-and-demo.md` | E-1 | Shared `examples/_config.py`; `demo.py` exercises every Wave A/B/C feature |

Why last: the demo should actually show off the Wave-A/B/C features
(`default_sampling`, `tracing.watch`, `streaming`, `Dataset` + eval,
`Agent.diff`, `trace_diff`). Landing this earlier means re-recording
`demo.py` each wave.

---

## 4. Coordination points (file-level)

Hand-off rules for files that appear in more than one brief.

### `operad/core/agent.py`

- **E-12 owns `__init__`** (sampling merge).
- **E-3 owns `forward` dispatch on `structuredio`.**
- **E-4 owns the retry wrapper** *inside* the `forward` body. It must
  wrap the strands call the way E-3 left it, not the original form.
- **E-9 owns `format_system_message`** return-type widening. It must
  not touch `forward`.
- **E-8 owns the new `stream` method.** Does not edit existing
  `forward` or `invoke`; it calls them via a streaming-specific
  helper.

If two briefs in Wave B are ready at the same time: E-3 merges first,
then the next rebase takes ~5 minutes of conflict resolution. Do not
attempt to merge E-4 or E-9 before E-3.

### `operad/core/config.py`

New fields land in this order:
1. **Wave B-1 (E-3):** `structuredio: bool = True`.
2. **Wave B-2a (E-4):** no new fields — `timeout`/`max_retries`/
   `backoff_base` already exist; only wiring changes.
3. **Wave B-2b (E-9):** `renderer: Literal["xml", "markdown", "chat"] = "xml"`.
4. **Wave B-3 (E-8):** `stream: bool = False`.
5. **Wave A (E-14):** `Backend` literal extended with `"anthropic"`.

`Configuration(extra="forbid")` means every rebase must re-export
through `operad.core.config` and update `operad.__init__.py`.

### `operad/runtime/observers/base.py`

- **E-4 adds** `metadata["retries"]` / `metadata["last_error"]` on
  terminal events.
- **E-8 adds** `kind="chunk"` to the `AgentEvent.kind` literal.
- These are additive; expect trivial merges.

### Examples directory

- **E-2** rewrites schema imports first.
- **E-1** updates every example to use `examples/_config.py` last.
- These should NOT run concurrently. E-2 merges first; E-1 rebases.

### `CLAUDE.md` and `README.md`

Multiple briefs touch both. Resolve by making each PR append a new
subsection rather than inlining into existing ones. Final polish pass
in Wave D consolidates.

---

## 5. Alignment with VISION and AGENTS — per issue

A compact review that each brief's solution respects the canon.

| Issue | Solution | Alignment |
| --- | --- | --- |
| E-1 | Shared `_config.py` + `demo.py` | AGENTS "surgical": one helper, not a refactor |
| E-2 | `schemas.py` with deprecation shims | VISION §6 layout convention made consistent |
| E-3 | `structuredio: bool` on Configuration | Knob on Configuration stays Pydantic; no new wrapper object (VISION §5.2) |
| E-4 | Retry in runtime layer | Preserves build-time purity; runtime concern stays in runtime |
| E-5 | Strip host auth from `hash_config` | Preserves reproducibility-hash determinism |
| E-6 | Cheap output-type check at build | Matches VISION "catch errors before a token is generated" |
| E-7 | `MetricBase` with `score_batch` default | Upgrades Protocol without breaking the existing `Metric` implementations |
| E-8 | `Agent.stream(x)` as a new method | Preserves `__call__`/`invoke` shape; streaming is opt-in |
| E-9 | Renderer package with selector | `format_system_message` stays overridable — same VISION §5.2 hook |
| E-10 | Fix AsyncMock plumbing | Test hygiene, no behavioural change |
| E-11 | `operad.tracing.watch()` context manager | Observability stays protocol-based; no global mutable state |
| E-12 | `default_sampling` per leaf class | Mirrors `nn.Module` hyperparameter defaults — matches VISION §4 table |
| E-13 | `Dataset[In, Out]` plain class | `torch.utils.data.Dataset` analogue; not an Agent, not an algorithm |
| E-14 | New backend adapter | Follows the per-file-per-backend pattern in `operad/models/` |
| E-15 | `SandboxPool` in launchers | Launchers are a runtime concern (VISION §6) |
| E-16 | `trace_diff` free function | Mirrors `Agent.diff`; static-vs-dynamic symmetry |

No brief introduces:

- A DSL, YAML schema, or blueprint system (VISION §8 non-goal).
- Hidden provider fallbacks (VISION §8 non-goal).
- A static-type-checker shell-out (VISION §8 non-goal).

Every brief has offline tests that use `FakeLeaf` or mocks; no brief
demands live LLM access for its unit suite. Integration tests stay
gated by `OPERAD_INTEGRATION=<name>`.

---

## 6. Testing strategy

Three bars, tightening across waves:

### Bar 1 — Brief acceptance (per-PR)

Each brief names offline tests that must pass before merge. These are
the contract between the brief's author and the maintainer.

### Bar 2 — Full suite after each wave

```bash
uv run pytest tests/                 # offline, all
uv run python -c "import operad"     # import smoke
uv run python examples/mermaid_export.py   # offline smoke
```

If anything regresses, roll back the most recent merge and fix
before proceeding to the next wave.

### Bar 3 — End-to-end at Wave-D completion

```bash
OPERAD_LLAMACPP_HOST=127.0.0.1:9000 \
OPERAD_LLAMACPP_MODEL=google/gemma-4-e4b \
uv run python demo.py                      # full showcase
uv run python examples/best_of_n.py        # parallel reasoners
uv run python examples/pipeline.py         # typed edges
uv run python examples/router_switch.py    # Switch branching
```

Every example runs against the canonical local setup with no edits.
Integration tests (`OPERAD_INTEGRATION=...`) are optional but
recommended for openai, anthropic, and ollama.

### Vision-regression checklist

After each wave, sanity-check against the VISION invariants:

1. `agent.build()` is still side-effect-free to construct (no
   `__init__` contacts the network).
2. A composite that reads `x.field` at trace time still raises
   `BuildError("payload_branch", ...)` (sentinel proxy intact).
3. Algorithms in `operad/algorithms/` are still plain classes with
   `run(...)`, not `Agent` subclasses.
4. `Agent[In, Out]` still type-checks in an IDE (Pydantic generics
   unchanged).
5. `agent.operad()` still prints every default-forward leaf's
   rendered prompt with zero tokens generated.

A regression in any of these is a showstopper — halt the wave and
triage.

---

## 7. Risk register

| Risk | Likelihood | Severity | Mitigation |
| --- | --- | --- | --- |
| E-3 and E-9 merge-conflict on `format_system_message` | Med | Med | Strict Wave-B ordering; E-3 merges first |
| Streaming × retry interaction produces duplicated chunks | Med | Low | V1 documents: retry mid-stream re-emits under a new `run_id` |
| `structuredio=False` parse path fails on malformed output | High | Med | Raise `BuildError("output_mismatch")`; add a parser-failure test |
| Schema rename (E-2) breaks downstream importers | Low | High | Deprecation shims at old paths for one release |
| Cassette hashes break when `format_system_message` returns a list (E-9) | Med | Med | Hash joined-text or the sorted JSON dump of messages — document in `operad/testing/hashing.py` |
| Sandbox pool worker deadlock on stderr overflow | Low | High | Drain stdout *and* stderr in reader tasks; never block on write |
| `Configuration(extra="forbid")` blocks rebases when a new field lands | High | Low | Update `operad/__init__.py` exports in the same PR |
| Demo script (Wave D) out of date by the time it ships | Med | Low | Wave D runs last; demo authored against frozen Wave-C main |

---

## 8. Done criteria

All 16 §E issues are "done" when:

1. Each brief's acceptance criteria pass.
2. `uv run pytest tests/` is green with `-W error::RuntimeWarning`.
3. `uv run python demo.py` runs end-to-end against gemma-4-e4b on
   `127.0.0.1:9000` and produces legible Rich output.
4. `trace_diff(t, t2)` on two runs of the same graph surfaces a
   non-empty delta when any leaf changed.
5. `Dataset(...).hash_dataset` + `EvalReport.hash_graph` +
   `OperadOutput.hash_input` together identify a reproducible run
   triple.
6. `ISSUES.md §E` entries are marked RESOLVED with commit hashes.

Once all six criteria hold, mint the next version (`0.2.0`) and
freeze the vision checkpoint.

---

## 9. What this plan does NOT do

- It does not sequence new agents or domains. New reasoning leaves,
  new algorithms, and the `AutoResearcher` north-star (#2 in VISION)
  wait until §E closes.
- It does not touch the Phase-1 / Phase-2 work already merged. Those
  stay as-is unless a §E brief specifically edits them.
- It does not introduce new observers, metrics, or backends beyond
  those named in the briefs. Adoption-widening is Wave A scope; any
  further additions are a separate iteration.

Solid fundamentals first, then the showpiece demos — in that order.
