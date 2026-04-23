# Feature · Standardise schema files as `schemas.py` per domain

**Addresses.** E-2 (ISSUES.md) + `TODO_SCHEMAS_STANDARDIZATION` in
`missing.py`.

Today the schema-file naming is inconsistent across domains:

| Domain | Where schemas live today |
| --- | --- |
| `coding/` | `types.py` |
| `memory/` | `shapes.py` |
| `conversational/` | inline in `talker.py` |
| `reasoning/` | inline in `react.py` and each component file |

Pick one name — `schemas.py` — and apply it everywhere.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-2.
- Every `operad/agents/*/` package.

---

## Proposal

### Target layout

```
operad/agents/reasoning/
  schemas.py                # Task, Thought, Action, Observation, Answer,
                            # ReflectionInput, Reflection, Query, Hits, Hit,
                            # RouteInput, Choice, ToolCall, ToolResult, ...
  components/
    reasoner.py             # imports from ..schemas
    ...
  react.py                  # imports from .schemas
  switch.py

operad/agents/coding/
  schemas.py                # DiffChunk, PRDiff, PRSummary, ReviewComment, ReviewReport
  components/
    code_reviewer.py        # imports from ..schemas
    ...
  pr_reviewer.py

operad/agents/conversational/
  schemas.py                # Utterance, SafeguardVerdict, TurnChoice, StyledUtterance
  components/
    ...
  talker.py

operad/agents/memory/
  schemas.py                # Belief, Beliefs, Turn, Conversation, UserModel, Summary
  components/
    ...
  store.py
```

### Backwards compatibility

- Rename `coding/types.py` → `coding/schemas.py`.
- Rename `memory/shapes.py` → `memory/schemas.py`.
- Extract inline schemas from `conversational/talker.py` and
  `reasoning/react.py` (and `reasoning/components/*.py` where shapes
  are defined inline) into their domain's `schemas.py`.
- Keep re-exports from the old module paths for one release with a
  `DeprecationWarning`:

  ```python
  # operad/agents/coding/types.py
  import warnings
  warnings.warn(
      "operad.agents.coding.types is renamed to operad.agents.coding.schemas; "
      "the old name will be removed in a future release",
      DeprecationWarning, stacklevel=2,
  )
  from .schemas import *  # noqa: F401,F403
  ```

- Update `operad/__init__.py` re-exports to pull from `schemas.py`.

### Update tests / examples

`tests/test_*.py` and `examples/*.py` that import from `coding.types`,
`memory.shapes`, or inline paths — update them to the new location.
The deprecation shims keep the test suite green during migration.

---

## Scope

- Rename: `coding/types.py` → `coding/schemas.py`, `memory/shapes.py` → `memory/schemas.py`.
- New: `conversational/schemas.py`, `reasoning/schemas.py`.
- Edit: every component / composition that imported inline types.
- Edit: `operad/__init__.py` re-exports.
- New: deprecation shims at the old paths.
- Edit: tests and examples touching those imports.

Do NOT:
- Change any public type names — just their location.
- Remove the deprecation shims in this PR. They expire a release later.

---

## Acceptance

- `uv run pytest tests/` green.
- `python -c "from operad.agents.coding.schemas import DiffChunk"` works.
- `python -c "from operad.agents.coding.types import DiffChunk"` works
  and emits a DeprecationWarning (assert in a test).
- `CLAUDE.md` updated: "Each `agents/<domain>/` uses `schemas.py` for
  shared types."

---

## Watch-outs

- Circular imports: `schemas.py` must not import from its own domain's
  component files. Types are leaves in the import graph.
- `reasoning/schemas.py` will need to house `Choice[T]`, which is a
  generic Pydantic model — check that `Literal[...]` parameterisation
  still works post-move.
- Examples and tests may use `from operad.agents.coding.types import *` —
  grep for all such references before deleting the old files.
