# 1-1 — Parameter foundation

**Wave.** 1 (no prior-wave dependencies).
**Parallel with.** 1-2.
**Unblocks.** Every wave-2 task.

## Context

`operad.optim` treats the mutable attributes of an `Agent` — `role`,
`task`, `rules`, `examples`, `config.sampling.temperature`, etc. — as
"trainable parameters" in the `torch.nn.Parameter` sense. Before we
can build losses, gradients, optimizers, or a training loop, we need
the `Parameter` primitive itself, plus the structured gradient type
that flows through the system.

Read `operad/optim/README.md` §"Parameter" and `.context/NEXT_ITERATION.md`
§2 before starting.

## Scope — in

- `operad/optim/parameter.py`
  - `ParameterKind` — a `Literal` enum of the supported kinds
    (`"role"`, `"task"`, `"rules"`, `"examples"`, `"temperature"`,
    `"top_p"`, `"top_k"`, `"model"`, `"backend"`, `"renderer"`,
    `"rule_i"`, `"example_i"`, `"extra"`).
  - `ParameterConstraint` — a small sealed set of constraint types:
    `TextConstraint` (max length, forbidden substrings),
    `NumericConstraint` (bounds, step), `VocabConstraint` (allowed
    values), `ListConstraint` (max count, per-item constraint).
    One concrete Pydantic model per constraint with a discriminated
    union `ParameterConstraint = Union[...]` for typing.
  - `TextualGradient` — the structured critique Pydantic model:
    `message: str`, `by_field: dict[str, str] = {}`,
    `severity: float = 1.0`, `target_paths: list[str] = []`.
    Include a `null_gradient() -> TextualGradient` classmethod or
    module function returning the "no update needed" default.
  - `Parameter` — generic over the value type `T`:
    - fields: `path: str`, `kind: ParameterKind`, `value: T`,
      `requires_grad: bool = True`, `grad: TextualGradient | None = None`,
      `constraint: ParameterConstraint | None = None`,
      `momentum_state: dict[str, Any] = {}`
    - classmethod `from_agent(agent, path: str, kind: ParameterKind, ...)`
      that reads the current value by dotted-path (reuse
      `operad.utils.paths.resolve_parent`).
    - method `read() -> T` — re-reads the live value from the agent
      (useful if the agent was mutated between construction and
      optimizer step).
    - method `write(new: T)` — writes back to the agent via
      `resolve_parent` + `setattr`.
    - method `zero_grad()` — `self.grad = None`.
  - Type-specialized subclasses: `TextParameter`, `RuleListParameter`,
    `ExampleListParameter`, `FloatParameter`, `CategoricalParameter`.
    These narrow `value`'s type and carry a fitting default `constraint`.
- `operad/optim/__init__.py` — export `Parameter`,
  `TextualGradient`, `ParameterConstraint`, `ParameterKind`, and the
  five subclasses.
- `tests/optim/test_parameter.py`
  - Test round-trip read/write against a `FakeLeaf`-style agent for
    every kind.
  - Test `Parameter` preserves identity under `state()`/`load_state()`
    cycles (i.e., writing a new `value` to a parameter updates the
    agent; cloning the agent and re-deriving the parameter yields
    the same `value`).
  - Test `ParameterConstraint` validation: numeric bounds clip,
    vocab rejects unknown values, list length limits, text max length.
  - Test `TextualGradient.null_gradient()` is treated as "no update."
  - Test `zero_grad()` clears `grad`.
- `operad/optim/README.md` — append a short "Implemented" section
  noting `Parameter` / `TextualGradient` are now available.

## Scope — out

- Do **not** add `parameters()` / `named_parameters()` / `mark_trainable`
  to `Agent`. That is slot 2-1's job.
- Do not implement Loss, Rewrite, Backprop, Tape, Optimizer, or
  Trainer. Those are later waves.
- Do not touch files outside `operad/optim/`, `tests/optim/`.

## Dependencies

- `operad.utils.paths.resolve_parent`, `operad.utils.paths.set_path` —
  reuse for path-based get/set.
- `operad.core.agent.Agent` — for type-only imports under
  `TYPE_CHECKING`.
- `pydantic.BaseModel` — for every data type.

## Design notes

- `Parameter` stores a **reference** to the root agent (or a weakref)
  so `read()` / `write()` can operate. Use a weakref to avoid
  cycles; provide a helper `Parameter.attach(agent)` that sets the
  back-reference.
- **Do not** store the live value separately from the agent — that
  creates a dual source of truth. `Parameter.value` is a read-through
  cache refreshed on `read()`; `write()` updates the agent's
  attribute.
- `momentum_state` is a free-form dict; each optimizer owns its own
  namespace inside it (e.g., `param.momentum_state["momentum"]["history"]`).
- **Generics:** use `typing.Generic[T]` so `TextParameter` narrows to
  `Parameter[str]`, `FloatParameter` to `Parameter[float]`, etc.
  Pydantic supports generic models via `BaseModel, Generic[T]`.
- Kinds like `"rule_i"` / `"example_i"` are for sub-indexed views
  (a single rule or example as its own `Parameter`). The path
  should include the index, e.g., `"reasoner.rules[2]"`. Keep the
  implementation minimal here — just the type shape; a later task
  will wire up the enumeration.

## Success criteria

- `uv run pytest tests/optim/test_parameter.py` passes offline.
- `uv run ruff check operad/optim/` is clean.
- `from operad.optim import Parameter, TextualGradient,
  ParameterConstraint` works.
- `operad/optim/__init__.py` exports every public symbol cleanly.
- No changes to files outside `operad/optim/` and `tests/optim/`.
