# 1 · 1 — Restructure: foundation for the next iteration

**Addresses.** R1, R2, R3, R4, R6 (no-op), plus two user-added folder
consolidations: collapse `operad/models/` into a single `operad/core/models.py`
and move `operad/testing/*` into `operad/utils/`.

This is the **only Wave-1 task**. All Wave-2 briefs assume this has landed.
No Wave-2 brief may start before this is merged to `main`.

---

## Required reading

- `METAPROMPT.md` (sub-agent onboarding).
- `ISSUES.md` §E for merged work context.
- `VISION.md` — the `torch.nn`-for-agents bet. The class-attribute contract,
  components-vs-algorithms split, and symbolic `build()` trace are
  non-negotiable.
- `operad/core/agent.py` — read it end to end before touching invoke/stream.
- `operad/core/output.py` — the hash helpers you are about to dedupe.
- `operad/testing/cassette.py`, `operad/testing/hashing.py` — the files you
  are moving.
- `operad/models/*.py` — the files you are collapsing.
- `operad/__init__.py` — the file you are stratifying.
- `tests/conftest.py` — imports `operad.testing.cassette` and must be updated.

---

## Proposal

### 1. Move `operad/testing/*` → `operad/utils/`

```
operad/testing/cassette.py  →  operad/utils/cassette.py
operad/testing/hashing.py   →  operad/utils/hashing.py
```

Delete `operad/testing/` (including its `__init__.py`). Update every import
site:

- `tests/conftest.py`
- Any test module that references `from operad.testing.cassette import ...`
- Any test module that references `from operad.testing.hashing import ...`
- `operad/core/output.py` (if it imports from testing/hashing)

### 2. Collapse `operad/models/` into a single `operad/core/models.py`

Fold these files into one:

```
operad/models/__init__.py     (defines resolve_model)
operad/models/anthropic.py
operad/models/bedrock.py
operad/models/llamacpp.py
operad/models/lmstudio.py
operad/models/ollama.py
operad/models/openai.py
operad/models/params.py
```

Order inside the new `operad/core/models.py`:
1. `params.py` content (shared parameter mapping) at top.
2. Per-backend constructors grouped by backend, in alphabetical order.
3. `resolve_model(cfg: Configuration) -> strands.models.Model` at the
   bottom.

Delete `operad/models/` directory entirely. Update every import site:

- `operad/__init__.py` — `from .models import resolve_model` →
  `from .core.models import resolve_model`
- `operad/core/agent.py` — if it imports anything from models (grep first)
- Examples and tests that import `operad.models.*`

### 3. Dedupe hash helpers (R2)

`operad/utils/hashing.py` is the single home for:

- `hash_str`, `hash_json`, `hash_config`, `hash_schema`
- `hash_model`, `hash_prompt`, `hash_input` (cassette keyers, already
  there in testing/hashing).

Remove duplicates from `operad/core/output.py`. That file keeps only:
- `OperadOutput` (the envelope).
- Module-level constants `OPERAD_VERSION_HASH`, `PYTHON_VERSION_HASH`, the
  `_RUN_GRAPH_HASH` ContextVar.

All callers of `hash_*` functions must import from `operad.utils.hashing`.
The call site inside `operad/core/agent.py:_build_envelope` is the main
one — rewrite its imports.

### 4. Promote `Example` to its own file (R3)

Move the `Example` class from `operad/core/agent.py` (currently lines
54–60) into a new file `operad/core/example.py`:

```python
# operad/core/example.py
from __future__ import annotations
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, ConfigDict

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class Example(BaseModel, Generic[In, Out]):
    """Typed few-shot demonstration: one `(input, output)` pair."""
    input: In
    output: Out
    model_config = ConfigDict(arbitrary_types_allowed=True)
```

`operad/core/__init__.py` re-exports `Example`. `agent.py` imports from
`.example`. Every test that did `from operad.core.agent import Example`
now does `from operad.core.example import Example` (or the top-level
re-export).

### 5. Consolidate `Agent.invoke` and `Agent.stream` (R1)

Today:

- `invoke` is ≈ 100 LOC (agent.py:527–627).
- `stream` is ≈ 150 LOC (agent.py:665–809).

Duplication: path computation, ContextVar setup (`_RUN_ID`, `_PATH_STACK`,
`_RETRY_META`, `_RUN_GRAPH_HASH`), start/end/error observer notify,
envelope construction, is_root detection, graph hash computation.

Extract the shared path into `_invoke_envelope`:

```python
async def _invoke_envelope(
    self,
    x: In,
    *,
    executor: Callable[[In], Awaitable[Out]],   # or an async generator bridge for stream
) -> OperadOutput[Out]:
    # 1. path computation (parent_entry, attr_name_hint)
    # 2. is_root + run_id + graph_hash + ContextVar setup
    # 3. notify "start"
    # 4. KEEP the existing inline validation (isinstance + _built). Task 2-1
    #    will replace this block with `self.validate(x)` after 1-1 lands —
    #    do NOT pre-emptively factor into validate() here.
    # 5. y = await executor(x)
    # 6. post-check isinstance(y, self.output) (stays inline for Wave 1)
    # 7. build envelope
    # 8. notify "end"
    # 9. reset ContextVars in finally
    # 10. return envelope
```

Both `invoke` and `stream` shrink to thin wrappers:

- `invoke(x)`: `return await self._invoke_envelope(x, executor=self.forward)`.
- `stream(x)`: streaming needs to yield `ChunkEvent`s as they come, so it
  can't just call `_invoke_envelope` and wait. Factor the envelope helper
  so the streaming path uses the same setup/teardown via a queue-bridged
  executor that pushes chunks to the caller. One reasonable shape:

  ```python
  async def stream(self, x):
      queue: asyncio.Queue = asyncio.Queue()
      async def _driver():
          async def _stream_exec(_x):
              # internally runs _stream_forward with on_chunk=put_into_queue
              ...
          env = await self._invoke_envelope(x, executor=_stream_exec)
          await queue.put(env); await queue.put(_DONE)
      asyncio.create_task(_driver())
      while True:
          item = await queue.get()
          if item is _DONE: break
          yield item
  ```

  If this bridge ends up heavier than the duplication, ship invoke via
  `_invoke_envelope` and keep a second, thinner helper `_stream_envelope`
  that shares the same ContextVar setup + envelope builder in common
  sub-helpers. The goal is **one implementation of path computation,
  ContextVar setup, and envelope construction** — not necessarily a single
  monolithic helper.

**Validation stays inline for Wave 1.** Do **not** introduce `validate(x)`
here — that's 2-1's job. 2-1 will replace the inline isinstance/_built
block with a single `self.validate(x)` call.

### 6. Stratify `operad/__init__.py` (R4)

New top-level surface (≈ 18 names):

```python
# operad/__init__.py  (after)
from .core import (
    Agent, AgentDiff, AgentGraph, AgentState, Backend, Change,
    Configuration, Example, OperadOutput,
    build_agent, abuild_agent,
)
from .agents import Pipeline, Parallel
from .benchmark import Dataset, evaluate   # note: moves in 2-5, not here
from .metrics import Metric
from .runtime.trace import Trace
from .utils.errors import BuildError, BuildReason
from . import tracing

__all__ = [
    "Agent", "AgentDiff", "AgentGraph", "AgentState", "Backend",
    "BuildError", "BuildReason", "Change", "Configuration", "Dataset",
    "Example", "Metric", "OperadOutput", "Parallel", "Pipeline", "Trace",
    "abuild_agent", "build_agent", "evaluate", "tracing",
]
```

> **Dataset/evaluate caveat.** `Dataset` and `evaluate` currently live at
> `operad/datasets.py` and `operad/eval.py`. They **stay there** in Wave 1;
> task 2-5 moves them to `operad/benchmark/`. For this PR, keep the
> existing imports in `__init__.py`:
> ```python
> from .datasets import Dataset
> from .eval import evaluate
> ```
> 2-5 will update those two lines when it moves the files.

Everything currently re-exported at top-level that is **not** in the list
above must be removed from `operad/__init__.py` entirely (no shim, no
deprecation warning — per "no backwards-compat"). Consumers access those
names via their subpackage:

- `operad.agents.reasoning.Reasoner`, `operad.agents.reasoning.Actor`, …
- `operad.agents.coding.CodeReviewer`, …
- `operad.agents.conversational.Talker`, …
- `operad.agents.memory.BeliefExtractor`, …
- `operad.algorithms.BestOfN`, `operad.algorithms.Debate`, …
- `operad.metrics.ExactMatch`, `operad.metrics.Rouge1`, …
- `operad.runtime.observers.JsonlObserver`, `operad.runtime.SlotRegistry`,
  `operad.runtime.trace_diff`, …
- `operad.utils.ops.AppendExample`, …

Each subpackage's `__init__.py` must expose its own names (most already
do; verify and extend).

### 7. R6 — no-op

Do **not** defer `import strands`. The module-level import at
`operad/core/agent.py` stays. Mention this explicitly in the PR
description so reviewers know the bet is not to chase import-time cost.

### 8. Import edit sweep

After the moves above, grep and update every stale import in:

- `operad/` (agent.py, algorithms/, agents/, runtime/, utils/)
- `tests/` (especially `tests/conftest.py`)
- `examples/*.py`
- `demo.py`
- `operad/cli.py`

Forbidden strings after this PR: `operad.testing`, `operad.models.` (as a
package path), `from operad.core.agent import Example`.

---

## Required tests

1. `uv run pytest tests/` — green, same 412+ tests.
2. `tests/test_toplevel_surface.py` (new):
   - `from operad.testing import *` raises `ModuleNotFoundError`.
   - `len(operad.__all__) <= 20`.
   - Representative "moved" names are still importable from their
     subpackage: `from operad.agents.reasoning import Reasoner`,
     `from operad.algorithms import BestOfN`, `from operad.utils.ops
     import AppendExample`.
3. `uv run python -c "import operad"` exits 0.
4. `uv run --extra observers python demo.py` reaches the live-run stage
   offline (the llama-server step is gated by its own env var).

---

## Scope

**New files.**
- `operad/utils/hashing.py` (moved).
- `operad/utils/cassette.py` (moved).
- `operad/core/models.py` (consolidated).
- `operad/core/example.py` (new).
- `tests/test_toplevel_surface.py` (new).

**Edited files.**
- `operad/__init__.py` (stratified).
- `operad/core/agent.py` (Example removed, invoke/stream consolidated).
- `operad/core/output.py` (hash helpers deleted; import from utils).
- `operad/core/__init__.py` (re-export `Example`).
- `operad/utils/__init__.py` (re-export hashing + cassette names).
- Every subpackage `__init__.py` whose scope is widened.
- `tests/conftest.py` (cassette fixture path update).
- Every `operad.testing.*` / `operad.models.*` import across the repo.

**Deleted files.**
- `operad/testing/__init__.py`, `operad/testing/cassette.py`,
  `operad/testing/hashing.py`, directory `operad/testing/`.
- `operad/models/__init__.py`, the six backend files, `params.py`,
  directory `operad/models/`.

**Do NOT (out of scope for this PR):**
- Add any new Agent methods (no `hash_content`, `validate`, `explain`,
  `__rich__`, `summary`, `>>`, `forward_in`, `forward_out`) — that's 2-1.
- Change `Configuration` — that's 3-4.
- Move `datasets.py` / `eval.py` — that's 2-5.
- Introduce new backends (Gemini, batch, HF) — that's 2-10.
- Dedupe backwards-compat shims of any kind: just delete the deprecated
  path.
- Delete `operad/missing.py` (TODO inventory) — it's still a source of
  truth.

---

## Acceptance

- Offline tests green.
- `grep -rn "operad.testing\|operad.models\." operad/ tests/ examples/ demo.py`
  returns no hits outside cassette JSON payloads (recorded metadata blobs
  are allowed to contain the strings as data).
- `operad/__init__.py`'s `__all__` is at most 20 entries.
- Single `operad/core/models.py` file exists; no `operad/models/`
  directory.
- `Example` class no longer defined in `agent.py` — only imported.
- `Agent.invoke` and `Agent.stream` share a single envelope-construction
  code path (`_invoke_envelope` or equivalent common helpers).

---

## Watch-outs

- The cassette fixture (`tests/conftest.py`) is the critical test-path
  import that will break first if you miss it; run `pytest tests/ -x` to
  fail fast.
- `_RUN_GRAPH_HASH` is a `ContextVar` in `operad/core/output.py` — don't
  move it; it's not a hash helper, it's runtime state.
- The `_invoke_envelope` helper should not eagerly compute
  `_compute_graph_hash(self)` for non-root invocations; respect the
  current `is_root` check (only root recomputes the graph hash).
- Strands imports: keep `import strands` at `operad/core/agent.py`
  module level; do not lazy-load (R6).
- `operad/__init__.py`'s `__all__` ordering convention in the repo is
  alphabetical — preserve it for the new, smaller list.
- When removing names from `operad/__init__.py`, double-check they are
  still importable from their subpackage; add the re-export if missing.
- The "structural" composites `Pipeline`, `Parallel` are currently under
  `operad.agents` (`operad/agents/__init__.py` re-exports them). Keep
  the top-level alias.
