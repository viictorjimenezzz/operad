# operad.core — the foundation

Everything else in `operad/` is built on this submodule. `core/`
exposes the `Agent` base class, the structural-composition machinery,
the `build()` symbolic tracer that produces an `AgentGraph`, the
backend dispatcher, the `Configuration` object, and the freeze/diff
plumbing for content-addressable identity.

If you internalize the four idioms in
[`../README.md`](../README.md) (typed `Agent[In, Out]`, `build()` as
compile step, composition by tree, `Parameter` handles), this is the
code that makes them work.

---

## Files

| File             | Role                                                                              |
| ---------------- | --------------------------------------------------------------------------------- |
| `agent.py`       | `Agent[In, Out]` base, child registration, `parameters()`, hooks, `register_*_hook`. |
| `build.py`       | `build_agent` / `abuild_agent`, `Tracer`, sentinel proxy that catches payload-branching at trace time. |
| `graph.py`       | `to_mermaid`, `to_json`, `from_json` graph exporters.                             |
| `config.py`      | `Configuration`, `Backend`, `Sampling`, `Resilience`, `IOConfig`, `Runtime` knobs. |
| `models.py`      | Backend dispatcher: `Configuration` → `strands.models.Model` per backend.         |
| `output.py`      | `OperadOutput[Out]` envelope — typed response + reproducibility metadata.         |
| `example.py`     | `Example[In, Out]` typed few-shot pair (DSPy-style).                              |
| `freeze.py`      | `freeze_agent(path)` / `thaw_agent(path)` / `thaw_pair`. API keys stripped.       |
| `state.py`       | `AgentState` — declared-attribute snapshot for `state()` / `load_state()`.        |
| `diff.py`        | `AgentDiff` + `Change` — structural diff between two agents.                      |
| `gradmode.py`    | `requires_grad` plumbing on `Agent` (consumed by `optim/`).                       |
| `fields.py`      | Helpers for class-attribute defaults (`role`/`task`/`rules`/`examples`).          |
| `render.py`      | XML / Markdown / chat-template renderers for the system prompt.                   |

## Public API

Re-exported at `operad.core` and again at top-level `operad`:

```python
from operad import (
    Agent,
    AgentGraph, Edge, Node,
    Configuration, Backend, Sampling, Resilience, IOConfig, Runtime,
    Example,
    OperadOutput,
    AgentState, AgentDiff, Change,
    abuild_agent, build_agent,
    freeze_agent, thaw_agent, thaw_pair,
    to_json, to_mermaid, from_json,
)
```

## Smallest meaningful example

```python
from pydantic import BaseModel
from operad import Agent, Configuration

class Q(BaseModel): text: str
class A(BaseModel): answer: str

class Concise(Agent[Q, A]):
    input  = Q
    output = A
    role   = "You are terse."
    task   = "Answer in one sentence."

leaf = Concise(config=Configuration(backend="llamacpp",
                                    host="127.0.0.1:8080",
                                    model="qwen2.5-7b"))
await leaf.abuild()        # symbolic trace + type check; no token generated
out = await leaf(Q(text="What is 2+2?"))
print(out.response.answer, out.run_id, out.hash_input)
```

`Pipeline(a, b)` and `Parallel({"x": a, "y": b}, ...)` (defined under
`operad/agents/`) compose leaves into trees. `build()` walks the tree
once, type-checks every parent-to-child handoff, and returns an
`AgentGraph` you can export, hash, replay, or feed to `backward()`.

## How to extend

| What                          | Where                                                                                  |
| ----------------------------- | -------------------------------------------------------------------------------------- |
| New leaf agent                | A subclass of `Agent[In, Out]`, declared in `operad/agents/<domain>/components/`.       |
| New backend adapter           | `operad/core/models.py` — extend the dispatcher; honor `Configuration.backend`.         |
| New renderer                  | `operad/core/render.py` — register on `Agent.format_system_message`.                    |
| New mutation primitive        | `operad/utils/ops.py` — implement `Op.apply(agent)` + an undo function.                 |
| New trainable field           | Add a `Parameter` subclass under `operad/optim/parameter.py`; expose via class attribute on the agent. |

### Footgun: composite `forward` must route, not branch on payload

`build()` uses sentinel inputs (`_PayloadBranchAccess` /
`_PayloadBranchDunder` in `build.py`) during symbolic tracing. If a
composite's `forward` reads payload values to decide which child to
call, the sentinel proxy raises `BuildError` pointing at the offending
access. Inspect payload values inside leaves or post-invoke; composites
just orchestrate.

## Related

- [`../utils/`](../utils/README.md) — errors, hashing, ops, cassette.
- [`../runtime/`](../runtime/README.md) — observers and traces that
  fire on every `Agent.invoke`.
- [`../agents/`](../agents/README.md) — `Pipeline`, `Parallel`, and
  the leaf component library.
- [`../optim/`](../optim/README.md) — what `Parameter` handles read
  off your agents.
- Top-level [`../../INVENTORY.md`](../../INVENTORY.md) — full catalog
  of the `Agent` API surface (every method, every hash field).
