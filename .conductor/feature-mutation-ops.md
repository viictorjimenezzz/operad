# Feature · `operad/utils/ops.py` — typed delta-mutation ops

Library of small, typed operations that mutate an agent in place.
Powers `Evolutionary` (Stream F), `Sweep` (feature-sweep.md), and
ad-hoc prompt tweaking.

**Covers Part-3 item.** #7 (delta-mutation library), relocated to
`operad/utils/ops.py` per feedback.

**Supersedes the `operad/algorithms/mutations.py` plan** from Stream F.
See the note at the top of `.conductor/2-F-algorithms.md`.

---

## Required reading

`METAPROMPT.md`, `ISSUES.md`, and:
- `.conductor/1-B-agent-state.md` — Ops mutate using the public
  state surface where possible.
- `.conductor/2-F-algorithms.md` — primary consumer (Evolutionary).
- `.conductor/feature-sweep.md` — secondary consumer (Sweep).

---

## Proposal sketch

### `Op` protocol

```python
@runtime_checkable
class Op(Protocol):
    """A typed, in-place mutation of an agent subtree."""
    name: str
    def apply(self, agent: Agent[Any, Any]) -> None: ...
```

No return; mutation is in place on the given agent. Ops are Pydantic
dataclasses (or plain `@dataclass`) so they're cheap to construct and
easy to serialise for `AgentDiff` and Evolutionary's change-log.

### Starter set

```python
@dataclass
class AppendRule:
    path: str         # dotted, e.g. "reasoner"
    rule: str
    name: str = "append_rule"
    def apply(self, agent):
        target = _resolve(agent, self.path)
        target.rules = [*target.rules, self.rule]

@dataclass
class ReplaceRule:
    path: str
    index: int
    rule: str

@dataclass
class DropRule:
    path: str
    index: int

@dataclass
class EditTask:
    path: str
    task: str

@dataclass
class TweakRole:
    path: str
    role: str

@dataclass
class DropExample:
    path: str
    index: int

@dataclass
class AppendExample:
    path: str
    example: Example[Any, Any]

@dataclass
class SetTemperature:
    path: str
    temperature: float
    def apply(self, agent):
        target = _resolve(agent, self.path)
        if target.config is None:
            raise ValueError(f"cannot set temperature on composite {self.path}")
        target.config = target.config.model_copy(update={"temperature": self.temperature})

@dataclass
class SetModel:
    path: str
    model: str

@dataclass
class SetBackend:
    path: str
    backend: Backend
    host: str | None = None
```

Keep the set *small and opinionated*. Don't add every conceivable
mutation; we ship the ones Evolutionary and Sweep actually need.

### Dotted-path resolver

`_resolve(agent, "a.b.c")` walks `_children` by attribute name.
Factor into `operad/utils/paths.py` so Sweep and introspection reuse
it.

---

## Research directions

- **Pydantic dataclass vs. BaseModel.** BaseModel gives JSON
  serialisation for free, which helps `AgentDiff` and Evolutionary
  change-logs. Measure the overhead; prefer BaseModel if it stays
  under 1µs per construction.
- **Composition of Ops.** Users will want "apply these three Ops
  atomically". A `CompoundOp(ops: list[Op])` is trivial; include it.
- **Validation.** `SetTemperature` on a composite (no config) should
  raise early, not silently succeed. Every Op's `apply` should fail
  loud and fast on shape errors.
- **Idempotence.** `AppendRule` with the same rule twice adds the
  rule twice (correct — appending is not a set operation). Document
  this; it's the natural semantics.
- **Relationship to `Agent.load_state`.** An Op is an in-place
  tweak; `load_state` is a full replacement. Both exist; they do not
  compete.

---

## Integration & compatibility requirements

- **Hard dependency on Stream B.** `Agent.state()` / `clone()` must
  exist so the caller can safely apply an Op to a clone without
  touching the original.
- **No imports from `operad/algorithms/` or `operad/agents/`.**
  `utils/ops.py` is a leaf module; algorithms and agents import it,
  not the other way round. Breaking this inverts the dependency
  graph.
- **Shared path resolver.** `operad/utils/paths.py` owns
  `_resolve(agent, dotted_path)`. Sweep, Evolutionary, and any
  future consumer imports it. Do NOT duplicate.
- **Coordinate with Stream F.** Stream F's brief plans a
  `operad/algorithms/mutations.py` — that plan is cancelled. Update
  that stream's brief if it hasn't been already (and open a PR that
  reflects the relocation, crediting this feature brief).
- **Op names are stable strings.** `name` is a public identifier
  used in logs and change-logs. Once shipped, don't rename.

---

## Acceptance

- `uv run pytest tests/` green.
- `tests/test_ops.py`: each Op in the starter set applies correctly
  and raises cleanly on shape errors.
- `AppendRule("reasoner", "x").apply(agent)` changes
  `agent.reasoner.rules`; no other attribute is touched.
- `SetTemperature` on a composite raises `ValueError`.
- Evolutionary (Stream F) imports from `operad.utils.ops`, not from
  `operad.algorithms.mutations` (that module does not exist).

---

## Watch-outs

- Do NOT introduce random choice inside an Op. Choosing *which* Op to
  apply (and its arguments) is the *caller's* job. Ops themselves
  are deterministic.
- Do NOT allow an Op to change `input` / `output` types. Those are
  structural; mutating them silently breaks `build()`.
- Keep the set short. Each Op has a cost in maintenance and doc
  surface.
