# Phase 1 · Stream B — Agent state, clone, mutation helpers

**Goal.** Give `Agent` a first-class serialisable state so Stream F's
`Evolutionary` and Stream C's `Observer` can snapshot, diff, and mutate
agents without private-attribute access.

**Owner:** one agent.
**Blocks.** Stream F (`Evolutionary` depends on `clone`/`state`).
**Addresses:** B-1.

---

## Scope

### Files you will create
- `operad/core/state.py` — `AgentState` Pydantic model + helpers.
- `tests/test_agent_state.py`.

### Files you will edit
- `operad/core/agent.py` — add `state()`, `load_state()`, `clone()`,
  and `__repr__`.
- `operad/core/__init__.py` — export `AgentState`.
- `operad/__init__.py` — export `AgentState`.

### Files to leave alone
- Everything outside `operad/core/` except re-exports.

---

## Design direction

### `AgentState` shape

```python
class AgentState(BaseModel):
    class_name: str                    # type(agent).__name__, diagnostic
    role: str
    task: str
    rules: list[str]
    examples: list[dict[str, Any]]     # dumped (input, output) pairs
    config: Configuration | None
    input_type_name: str               # agent.input.__name__, diagnostic
    output_type_name: str
    children: dict[str, "AgentState"] = {}

    model_config = ConfigDict(arbitrary_types_allowed=True)
```

Children nest recursively, keyed by attribute name (reuse
`_children`). Examples are dumped as plain dicts because typed
round-trip across processes needs the caller's In/Out classes — the
Agent already knows its contract at `load_state` time.

### `state()` method

Walks the agent tree (breadth-first, like `_tree`), captures each
agent's local state, nests children under the parent's `children`
dict keyed by the attribute name from `_children`.

### `load_state(s)` method

Mutates the instance in place:
1. Reassign `role`, `task`, `rules`, `examples`, `config`.
2. For each child, look up by attribute name and recurse.
3. Error clearly if the structure differs
   (`BuildError("prompt_incomplete", "load_state shape mismatch")`).
4. Reset `_built = False` and `_graph = None` — caller must rebuild.

Do NOT touch `input` / `output` types; those are structural, not state.
If the caller wants to change types they should construct a new agent.

### `clone()` method

Deep copy. Implementation sketch:
1. `new = type(self).__new__(type(self))` to skip `__init__`.
2. `object.__setattr__(new, "_children", {})` and `_built = False`.
3. Copy simple fields.
4. For each child in `self._children`, call `child.clone()` and attach
   via `setattr(new, name, cloned)` so `__setattr__` re-registers.
5. Deep-copy `config` via `self.config.model_copy(deep=True)` if set.

### `__repr__`

```python
def __repr__(self) -> str:
    return (
        f"{type(self).__name__}("
        f"input={self.input.__name__}, "
        f"output={self.output.__name__}, "
        f"children={list(self._children)})"
    )
```

---

## Tests

- `tests/test_agent_state.py`:
  - Round-trip: `a.load_state(a.state())` is a no-op on field values.
  - Clone independence: mutations on the clone do not touch the original.
  - Clone preserves nested structure (children, order, types).
  - `load_state` with a mismatched child name raises a `BuildError`.
  - Clone resets `_built = False`; rebuilding the clone produces a
    graph with the same shape as the original's.

---

## Acceptance

- `uv run pytest tests/` green.
- Stream F can call `agent.clone()` → mutate fields → `abuild()` →
  score → keep the best, without reaching into private attributes.

---

## Watch-outs

- Do NOT try to clone `strands.Agent` internal state. `clone()`
  produces a fresh unbuilt agent; the caller rebuilds.
- Do NOT implement mutation mini-ops here (`add_rule`, `set_task`,
  etc.). Those live in Stream F's `operad/algorithms/mutations.py`.
- `Example` is typed by Pydantic `In` / `Out` generics; `.model_dump()`
  on a list of them needs care. Test the round-trip carefully.
- `Configuration` has `extra="forbid"` and should be `model_copy`-able
  without surprises; verify.
