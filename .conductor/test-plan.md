# Test & examples refactor — end-to-end runnability

**Goal.** The repo currently has 77 flat `tests/test_*.py` files and 19
`examples/*.py` files with inconsistent entry-points. Refactor both so
that:

- `uv run pytest tests/` completes offline in under 60 seconds, green,
  with no skipped tests outside `tests/integration/`.
- `uv run pytest tests/<subdir>` scopes cleanly to a concern area.
- `uv run python examples/<name>.py` works for every example either
  with a running local LLM (network examples) or offline (schema /
  mermaid examples) — the distinction surfaces via a clear first-line
  banner, not a traceback.
- There is one command (`make verify` or `scripts/verify.sh`) that
  runs the whole offline suite + every offline example end-to-end and
  reports pass/fail per artefact.

No feature changes. No new behaviour. Only reorganisation, deduping,
and test-driver ergonomics.

---

## Current state

```
tests/
  conftest.py
  _cli_fixtures.py
  _spy_strands.py
  cassettes/                          # recorded NDJSON
  fixtures/
    sample_trace.jsonl
  integration/
    test_anthropic.py / test_batch.py / test_gemini.py / test_huggingface.py
    test_llamacpp.py / test_lmstudio.py / test_ollama.py / test_openai.py
    test_sandbox.py / test_sandbox_pool.py
  test_*.py                           # 77 flat files
examples/
  _config.py
  *.py                                # 19 entry-point scripts (mixed patterns)
  task.json / config-react.yaml
```

Pain points:

1. **Flat test layout.** A change in `operad/agents/memory/` means
   grepping 77 filenames to find relevant tests.
2. **Duplicated coverage.** `test_metrics_contains.py`,
   `test_metrics_deterministic.py`, `test_metrics_regex.py`,
   `test_metrics_rouge.py` each cover one metric — better merged into
   one `test_metrics.py` with parametrised cases. `test_cost.py`
   vs `test_metrics_cost.py`. `test_rendering.py` vs `test_renderers.py`.
   `test_runtime_slots.py` vs `test_slots_rate_limit.py`. Etc.
3. **Mixed scopes in one file.** `test_agent.py`, `test_agent_init.py`,
   `test_agent_introspection.py`, `test_agent_state.py`,
   `test_agent_features.py` all probe `Agent`; some overlap.
4. **Example inconsistency.** Some examples have `if __name__ ==
   "__main__":`, some don't. Some read `OPERAD_LLAMACPP_HOST`, others
   hardcode `127.0.0.1:8080`. Some crash without a running server;
   others print a helpful skip message. No uniform `--help`.
5. **No single "run everything" command.** `demo.py` runs the
   Rich showcase but doesn't exercise the per-example smoke path.

---

## Proposed test layout

```
tests/
  conftest.py                         # shared fixtures (unchanged core)
  _helpers/
    __init__.py
    cli_fixtures.py                   # renamed from _cli_fixtures.py
    spy_strands.py                    # renamed from _spy_strands.py
    fake_leaf.py                      # move FakeLeaf + stubs out of conftest
  cassettes/                          # (unchanged)
  fixtures/
    sample_trace.jsonl                # (unchanged)

  core/
    test_agent.py                     # basics: construct, state, clone, diff
    test_agent_features.py            # C1/C2/C3/O2/O6/E1/E3 bundle (hash_content, forward_in/out, validate, explain, summary, __rich__, >>)
    test_build.py                     # symbolic trace, type-check, errors
    test_build_freeze.py              # freeze/thaw round-trip + version guard
    test_build_error_mermaid.py       # BuildError.__str__ fragment
    test_configuration.py             # flat config, validators, batch flag
    test_operad_output.py             # envelope shape + hashes
    test_graph_export.py              # to_mermaid, to_json
    test_rendering.py                 # all renderers + structuredio + default_sampling (merged)
    test_ops.py                       # typed mutation ops
    test_errors.py                    # BuildError + BuildReason
    test_toplevel_surface.py          # from operad import * audit

  runtime/
    test_slots.py                     # concurrency + rate limiting (merged)
    test_retry.py                     # backoff wrapper
    test_streaming.py                 # stream=True + ChunkEvent
    test_trace.py                     # Trace.load/save/replay
    test_trace_diff.py                # per-step comparison
    test_trace_schema_drift.py        # drift detection
    test_tracing_watch.py             # watch() ctx manager
    test_replay.py                    # replay(trace, metrics)
    test_observers.py                 # base + jsonl + rich (merged, non-otel)
    test_observer_otel.py             # otel-only (skips without extra)
    test_sandbox.py                   # SandboxPool + launcher (merged)

  agents/
    test_composition.py               # Pipeline + Parallel + Switch + deep nesting (merged)
    test_reasoning.py                 # all reasoning leaves + react + router + reflector + retriever (merged)
    test_tool_user.py                 # typed Tool[Args, Result] + ToolUser
    test_coding.py                    # coding domain + PRReviewer (merged)
    test_conversational.py            # conversational + talker (merged)
    test_memory.py                    # memory domain + memory store (merged)
    test_safeguard.py                 # input sanitizer + output moderator

  algorithms/
    test_best_of_n.py
    test_debate.py
    test_evolutionary.py
    test_self_refine.py
    test_sweep.py
    test_verifier_loop.py
    test_auto_researcher.py

  benchmark/
    test_benchmark.py                 # Entry + Dataset + AggregatedMetric + evaluate

  metrics/
    test_deterministic.py             # ExactMatch, Contains, RegexMatch, Rouge1, JsonValid, Latency (merged)
    test_rubric_critic.py             # LLM-judge variant
    test_cost.py                      # CostTracker + metrics_cost (merged)

  models/
    test_models.py                    # resolver dispatch + schema deprecation (merged)
    test_model_backends.py            # per-backend resolve (mocked)

  cassettes_feat/
    test_cassette_replay.py           # renamed from test_cassette_demo.py
    test_cassette_miss_diff.py        # drift-naming diff

  cli/
    test_cli.py                       # operad run|trace|graph|tail

  examples/
    test_examples_offline.py          # import + mermaid_export + custom_agent (offline only)

  integration/                        # (unchanged — one file per backend, all skip by default)
    test_anthropic.py / test_batch.py / test_gemini.py / test_huggingface.py
    test_llamacpp.py / test_lmstudio.py / test_ollama.py / test_openai.py
    test_sandbox.py / test_sandbox_pool.py
```

---

## Consolidation rules

Apply these mechanically per file group. Every merge preserves the
*assertions* verbatim; only the file they live in moves.

### Merges (keep all assertions)

| New file                                    | Absorbs                                                              |
| ------------------------------------------- | -------------------------------------------------------------------- |
| `core/test_agent.py`                        | `test_agent.py`, `test_agent_init.py`, `test_agent_introspection.py`, `test_agent_state.py` |
| `core/test_rendering.py`                    | `test_rendering.py`, `test_renderers.py`, `test_structuredio.py`, `test_default_sampling.py` |
| `core/test_configuration.py`                | `test_configuration.py`, `test_configs.py`                           |
| `runtime/test_slots.py`                     | `test_runtime_slots.py`, `test_slots_rate_limit.py`                  |
| `runtime/test_observers.py`                 | `test_observers.py` (rich + jsonl + base protocol)                   |
| `runtime/test_sandbox.py`                   | `test_sandbox.py`, `test_sandbox_pool.py`                            |
| `agents/test_composition.py`                | `test_pipeline.py`, `test_parallel.py`, `test_switch.py`, `test_composition.py`, `test_deep_nesting.py` |
| `agents/test_reasoning.py`                  | `test_reasoning_components.py`, `test_reasoning_examples.py`, `test_react.py`, `test_reflector.py`, `test_retriever.py`, `test_router.py` |
| `agents/test_tool_user.py`                  | `test_tool_user.py`, `test_typed_tool.py`                            |
| `agents/test_coding.py`                     | `test_coding_components.py`, `test_pr_reviewer.py`                   |
| `agents/test_conversational.py`             | `test_conversational_components.py`, `test_talker.py`                |
| `agents/test_memory.py`                     | `test_memory_components.py`, `test_memory_store.py`                  |
| `metrics/test_deterministic.py`             | `test_metrics_base.py`, `test_metrics_contains.py`, `test_metrics_deterministic.py`, `test_metrics_regex.py`, `test_metrics_rouge.py` |
| `metrics/test_cost.py`                      | `test_cost.py`, `test_metrics_cost.py`                               |
| `models/test_models.py`                     | `test_models.py`, `test_schema_deprecation.py`                       |

### Deletions (redundant or superseded)

Scan each file for unique high-signal assertions. If a merged file
already covers the same property (e.g. two tests that both check
`ExactMatch` returns 1.0 on identical strings), keep the one with the
tighter assertion. Flag candidates for deletion:

- `test_paths.py` — if every `set_path` invariant is already covered by
  `test_sweep.py` (which exercises dotted-path mutation), retire it.
  Otherwise fold a minimal subset into `core/test_ops.py`.
- Any `test_agent_*.py` file whose assertions duplicate what
  `core/test_agent.py` picks up.
- Parametrised metric tests with identical inputs under different
  names.

Rule of thumb: if deleting a test leaves *any* line of product code
without direct coverage, keep it (possibly merged). Never delete for
aesthetic reasons alone.

### Keep as-is

- `test_benchmark.py`, `test_safeguard.py`, `test_auto_researcher.py`,
  `test_best_of_n.py`, `test_debate.py`, `test_evolutionary.py`,
  `test_self_refine.py`, `test_sweep.py`, `test_verifier_loop.py` —
  move into the right subdir, no merges.
- `test_trace.py`, `test_trace_diff.py`, `test_trace_schema_drift.py`,
  `test_replay.py`, `test_tracing_watch.py` — each probes a distinct
  file; keep separate under `runtime/`.
- `test_cassette_demo.py`, `test_cassette_miss_diff.py` — move to
  `cassettes_feat/`; rename `test_cassette_demo.py` →
  `test_cassette_replay.py` so the name describes what it tests.

---

## `tests/conftest.py` + shared helpers

Current `conftest.py` is the single source of truth for `FakeLeaf`,
cassette fixture, and strands spy. After the move:

- `tests/conftest.py` stays at the repo root-of-tests (pytest collects
  it); it just re-imports helpers from `tests/_helpers/`.
- Any fixture used in only one subdir moves to a local
  `tests/<subdir>/conftest.py`.
- `_cli_fixtures.py` / `_spy_strands.py` rename to underscore-free
  modules under `_helpers/`; they're helpers, not conftests.

Acceptance: `uv run pytest tests/ --collect-only` produces the same
set of test IDs before and after the move (modulo path renames).
Capture before/after to a file and diff.

---

## Examples refactor

Every file in `examples/*.py` must follow one template:

```python
"""<one-line description>.

<paragraph: what it demonstrates, what knobs matter>.
Run:
    uv run python examples/<name>.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio

from ._config import local_config  # or similar shared helper


async def main(offline: bool = False) -> None:
    ...


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="Run without contacting any LLM server.")
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
```

Per-file rules:

- **Offline-capable examples** (`mermaid_export.py`, `custom_agent.py`
  with `--offline`, any example that can swap in a `FakeLeaf`) must
  run to completion without network access.
- **Network examples** must print a one-line banner at start naming
  the backend / host / model they'll hit, and fail with a clean
  `SystemExit(1)` if the endpoint isn't reachable (not a raw
  traceback).
- **All examples** must import from `examples._config` rather than
  hardcoding host strings.
- **`task.json`** stays — it's the input payload used by the CLI
  example.

### Examples index

Add `examples/README.md` listing every example with:

```
| Script                    | Needs LLM? | What it shows                     |
| ------------------------- | ---------- | --------------------------------- |
| `mermaid_export.py`       | no         | Build a composite and print graph.|
| `custom_agent.py`         | yes/no     | Minimal user-defined leaf.        |
| ...                       |            |                                   |
```

### Offline smoke in CI

`tests/examples/test_examples_offline.py` imports each
offline-capable example and calls `main(offline=True)`. The test file
itself is ~40 LOC and guards against bitrot:

```python
@pytest.mark.parametrize("name", ["mermaid_export", "custom_agent", ...])
def test_example_runs_offline(name):
    mod = importlib.import_module(f"examples.{name}")
    asyncio.run(mod.main(offline=True))
```

---

## One command to verify everything

Add `scripts/verify.sh` (or a `Makefile` target — pick one):

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Type check (if mypy/pyright is set up; skip if not).
# 2. Full offline test suite, fail-fast.
uv run pytest tests/ -q --maxfail=1

# 3. Each offline example runs to completion.
for f in examples/mermaid_export.py examples/custom_agent.py; do
    echo "== $f =="
    uv run python "$f" --offline
done

# 4. demo.py — offline stages only.
uv run --extra observers python demo.py --offline

echo "✅ verify complete."
```

Run locally with `scripts/verify.sh`. CI runs this job on every PR.
Integration tests stay gated by `OPERAD_INTEGRATION=<backend>` and do
not run here.

---

## Acceptance

- `uv run pytest tests/ -q` green. Total < 60s on a warm cache
  (currently ~40s; the reorg shouldn't add runtime).
- `uv run pytest tests/ --collect-only` enumerates the same set of
  test IDs as before the reorg (modulo path segments). Diff saved to
  PR description.
- `uv run pytest tests/core/` / `tests/runtime/` / `tests/agents/`
  etc. each scope cleanly (only the relevant subset runs).
- Every example in `examples/` has a top-line docstring and an
  `if __name__ == "__main__":` block with `--offline` support where
  applicable.
- `uv run python examples/<name>.py --offline` for every offline-
  capable example exits 0.
- `scripts/verify.sh` exits 0 on a fresh checkout with no env vars
  set.
- `examples/README.md` lists every example.

---

## Step-by-step execution plan

Split across up to three PRs; each lands independently and is
internally mechanical.

### PR A — Test folder reorg (pure move)

1. Create the subdirs listed above, each with an empty `__init__.py`.
2. For each consolidation in the merge table: open the source files,
   append their test bodies into the merged target, delete the
   sources. Capture a `pytest --collect-only` snapshot before and
   after; diff must be isomorphic under path rename.
3. Update `tests/conftest.py` imports if any fixtures moved.
4. Run `uv run pytest tests/` green.

No behaviour change. Pure mechanical move.

### PR B — Helpers + cross-subdir fixtures

1. Move `tests/_cli_fixtures.py` → `tests/_helpers/cli_fixtures.py`.
2. Move `tests/_spy_strands.py` → `tests/_helpers/spy_strands.py`.
3. Extract `FakeLeaf` and related stubs from `conftest.py` into
   `tests/_helpers/fake_leaf.py`; `conftest.py` re-imports.
4. For each subdir with unique fixtures, add a local `conftest.py`.
5. Run `uv run pytest tests/` green.

### PR C — Examples refactor + verify script

1. For each `examples/*.py`:
   - Add `if __name__ == "__main__":` + `argparse` if missing.
   - Wire `--offline` where the example supports it; print a clear
     banner otherwise.
   - Switch hardcoded hosts to `examples._config` helpers.
2. Add `examples/README.md` with the table.
3. Add `tests/examples/test_examples_offline.py` parametrised over
   offline-capable examples.
4. Add `scripts/verify.sh`. Run it locally to confirm exit 0.
5. Update `README.md` "Run the demo" section if the `--offline` flag
   on `demo.py` is new.

---

## Watch-outs

- **Cassette paths.** Cassette JSONL files are keyed by path. After a
  test moves to a subdir, the implicit cassette name (if the fixture
  derives from `request.node.nodeid`) changes. Either:
  - pin cassette paths explicitly in each test via the `cassette`
    fixture's `path=` kwarg, or
  - re-record cassettes in one sweep (`OPERAD_CASSETTE=record uv run
    pytest tests/ -q`).
  The latter is easier; PR A's merge window is the right time to
  re-record.
- **`conftest.py` discovery.** Pytest walks up from every test file
  looking for `conftest.py`. Subdir-local conftests are additive, not
  overriding; fixtures defined at the root apply everywhere. Keep
  shared fixtures at the root; only put genuinely subdir-specific
  state in local conftests.
- **Parametrised tests and IDs.** When merging per-metric tests into
  one `test_deterministic.py`, use `@pytest.mark.parametrize` with
  `ids=[...]` so `pytest -k ExactMatch` still works.
- **Integration tests untouched.** `tests/integration/` stays flat;
  it's already organised by backend and small enough that a subdir
  reorg adds noise without value.
- **`test_examples.py`** (current flat file) — decide per-test
  whether it belongs under `tests/examples/` or is redundant with the
  parametrised offline runner. Likely most assertions are redundant
  once the offline runner exists.
- **`demo.py --offline`.** If `demo.py` doesn't currently support
  offline mode, add it in PR C; otherwise the verify script won't
  complete on a fresh checkout. Quick path: in offline mode, swap
  every `Configuration` for a `FakeLeaf`-wrapping stub and skip the
  invocation stage (keep the prompt-render and Mermaid-graph stages).
- **No feature changes.** If any merge surfaces a bug or gap, file it
  separately; don't fix in these PRs. The point is reorg.
