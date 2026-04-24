# 3 · 3 — `benchmark.Experiment` — content-addressed bundle

**Addresses.** R-research-1 (`Experiment`: bundle agent + dataset +
metrics + configs, capture traces, serialise the whole thing).

**Depends on.**
- 2-5 (benchmark foundation — `Dataset`, `Entry`, `evaluate`,
  `EvalReport`, `AggregatedMetric`).
- 2-1 (`agent.hash_content` — used as part of the content address).

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §6 (Experiment as the reproducibility
  primitive).
- `operad/benchmark/` (post-2-5) — `Dataset`, `evaluate`, `EvalReport`.
- `operad/core/agent.py` (post-2-1) — `Agent.hash_content`.
- `operad/runtime/trace.py` — `Trace`, `TraceObserver`.
- `operad/runtime/observers/base.py` — `registry.register/unregister`.
- `operad/core/graph.py` — `AgentGraph.to_json`.

---

## Proposal

An `Experiment` is a reproducibility container:

- one `agent` (the subject under test);
- one `Dataset` (the inputs + expected outputs);
- zero-or-more `Metric`s;
- the `EvalReport` and every `Trace` captured during `run()`.

Saving an experiment writes a content-addressed folder whose contents
hash to a single stable ID. Loading reconstitutes state verbatim.

### API

```python
# operad/benchmark/experiment.py

from pathlib import Path
from pydantic import BaseModel, Field

from ..core.agent import Agent
from ..metrics.base import Metric
from ..runtime.trace import Trace, TraceObserver
from .dataset import Dataset
from .evaluate import EvalReport, evaluate


class Experiment:
    """Agent × Dataset × Metrics + captured traces + final report.

    Address-addressable via `experiment_id`: a function of
    `agent.hash_content`, `dataset.hash_dataset`, and sorted metric
    names. Identical inputs produce identical IDs across machines.
    """

    def __init__(
        self,
        *,
        agent: Agent,
        dataset: Dataset,
        metrics: list[Metric],
        name: str = "",
    ) -> None:
        self.agent = agent
        self.dataset = dataset
        self.metrics = list(metrics)
        self.name = name
        self.report: EvalReport | None = None
        self.traces: list[Trace] = []

    @property
    def experiment_id(self) -> str: ...    # 16-hex, stable

    async def run(self, *, concurrency: int = 4) -> EvalReport: ...

    def save(self, folder: str | Path) -> Path: ...
    # returns the folder path; creates it if missing; deterministic layout:
    #   folder/manifest.json         (experiment metadata + IDs)
    #   folder/graph.json            (agent's AgentGraph.to_json)
    #   folder/state.json            (agent.state() dump)
    #   folder/dataset.ndjson        (dataset.save)
    #   folder/report.json           (self.report.model_dump)
    #   folder/traces/<run_id>.json  (one file per captured trace)

    @classmethod
    def load(cls, folder: str | Path) -> "Experiment": ...
```

### `experiment_id`

```python
def experiment_id(self) -> str:
    parts = {
        "agent": self.agent.hash_content,
        "dataset": self.dataset.hash_dataset,
        "metrics": sorted(m.name for m in self.metrics),
        "name": self.name,
    }
    return hash_json(parts)   # 16 hex, existing helper
```

### `run()`

1. Build the agent if not built (raise if `_built` is False — same
   policy as `evaluate`).
2. Register a `TraceObserver` scoped to this experiment only.
3. Call `evaluate(self.agent, self.dataset, self.metrics,
   concurrency=concurrency)`.
4. Capture every `Trace` the observer saw → `self.traces`.
5. Unregister the observer.
6. Store `self.report = report`.
7. Return `report`.

Observer registration is local, wrapped in `try/finally` for
unconditional cleanup.

### `save(folder)`

Write the six artefacts listed in the docstring above. Deterministic:

- `manifest.json` keys sorted, pretty-printed with `indent=2`.
- `traces/<run_id>.json` sorted by `run_id` alphabetically when
  writing for reproducible `ls` output.
- Strip `config.api_key` from `state.json` (same policy as 2-2's
  freeze).

Manifest shape:

```json
{
  "experiment_id": "3b1f...",
  "name": "baseline-run-1",
  "agent_class": "operad.agents.reasoning.Reasoner",
  "agent_hash_content": "...",
  "dataset_name": "...",
  "dataset_version": "...",
  "dataset_hash": "...",
  "metrics": ["exact_match", "latency_p50"],
  "created_at": 1.7e9,
  "trace_run_ids": ["run-001", "run-002", ...]
}
```

### `load(folder)`

Symmetric inverse:

- Read `manifest.json`; resolve `agent_class` via `importlib`.
- Reconstruct `agent` via `agent_class(**state.json)` (a stub —
  subclasses with non-trivial constructors require overriding; for
  v1, rely on the class exposing a `from_state(state_dict)`
  classmethod, which is agent.py's existing load path).
- `Dataset.load(dataset.ndjson)`.
- Rebuild `report` from `report.json`.
- Load each trace from `traces/`.
- `metrics` are **not** rehydrated automatically (protocols can't
  round-trip callables through JSON); caller re-supplies the metric
  list after load if they want to re-run.

### Re-export

```python
# operad/benchmark/__init__.py
from .experiment import Experiment
__all__ = [..., "Experiment"]
```

Not promoted to `operad.__all__`.

---

## Required tests

`tests/test_benchmark_experiment.py` (new):

1. **`experiment_id` stable.** Two `Experiment`s built with the same
   agent state, same dataset, same metric set ⇒ same `experiment_id`.
2. **`experiment_id` sensitive.** Mutating the agent (`AppendRule`
   op), or the dataset's rows, changes `experiment_id`.
3. **`run()` captures traces.** FakeLeaf; 3-entry dataset; after
   `await exp.run()`, `len(exp.traces) == 3` and each trace has a
   distinct `run_id`.
4. **`save()` writes expected layout.** `exp.save(tmp_path)` creates
   exactly `manifest.json`, `graph.json`, `state.json`,
   `dataset.ndjson`, `report.json`, and a `traces/` directory with
   3 `run-*.json` files.
5. **Round-trip.** `exp.save(tmp_path)` → `Experiment.load(tmp_path)`
   → the loaded experiment's `agent.hash_content` matches the
   original, `dataset.hash_dataset` matches, `report.summary` equals
   the original, and `len(loaded.traces) == 3`.
6. **API key scrubbed.** `Configuration(api_key="secret-xyz")`; after
   `save()`, the JSON files read as raw text contain no
   `"secret-xyz"` substring.
7. **`load()` skips metrics.** After `load`, `exp.metrics == []`
   (or equivalent placeholder; the caller re-supplies).

All offline; FakeLeaf + deterministic metrics.

---

## Scope

**New files.**
- `operad/benchmark/experiment.py`.
- `tests/test_benchmark_experiment.py`.

**Edited files.**
- `operad/benchmark/__init__.py` — re-export `Experiment`.

**Must NOT touch.**
- `operad/core/agent.py` — use `hash_content` as imported.
- `operad/runtime/trace.py` — use `TraceObserver` as imported.
- Other benchmark primitives.
- `operad/core/graph.py`, `operad/core/state.py` — read-only.

---

## Acceptance

- `uv run pytest tests/test_benchmark_experiment.py` green.
- `uv run pytest tests/` green.
- `from operad.benchmark import Experiment` works.
- `exp.save(folder)` + `Experiment.load(folder)` round-trips cleanly
  across a fresh-interpreter subprocess.
- No API keys in any saved file (`grep -r "api_key" folder/` yields
  no secret values; only field labels).

---

## Watch-outs

- **`hash_content` depends on 2-1.** This PR must land after 2-1 in
  Wave 3. State dependency is hard: the brief's acceptance depends
  on `agent.hash_content` being a real attribute. Call out in PR
  description; do not land before 2-1 merges.
- **`agent_class` loader.** `importlib.import_module` + `getattr`
  will fail for agent classes defined inside test files (module
  paths not addressable post-interpreter). Document: experiments
  saved from throwaway subclasses aren't portable across
  interpreters; experiments saved from library classes are. Test 5
  uses a library class (`Reasoner` or similar), not a ad-hoc test
  subclass.
- **Trace file naming.** `run_id` is already a UUID-ish string; use
  it verbatim as the filename. Sort for reproducible `ls`.
- **Observer race.** `TraceObserver` is registered globally; two
  overlapping `exp.run()` calls would capture each other's traces.
  Document "run() is not reentrant on the same Experiment or across
  concurrent Experiments." This is acceptable for v1; a scoped
  observer is a future improvement.
- **Metrics don't round-trip.** State the limitation explicitly:
  `save()` stores metric *names*, not callables. `load()` populates
  `exp.metrics = []`. If the caller wants to re-run, they re-supply.
  Alternative (deferred): a metric registry where `load()` looks up
  names — but that's extra surface and this PR doesn't need it.
- **`state.json` vs freeze.** 2-2 introduces `Agent.freeze(path)` —
  a *single-file* persistence format. `Experiment.save` writes a
  multi-file folder and does **not** use `freeze` internally (the
  experiment wants the artefacts separable for CI/reporting). Do
  not conflate the two paths.
- **Ordering guarantee.** `exp.traces` is sorted by `run_id` on
  both `run()` completion and `load()` so test assertions on
  `traces[0].run_id` are stable.
- **Write atomicity.** `save()` writes files one by one. For v1,
  that's fine (single-writer, test context). Don't introduce
  staging or tmp-file swapping unless a future brief asks for it.
