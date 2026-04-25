# operad.utils — cross-cutting helpers

Tiny module, load-bearing. Errors with structured reasons, the
content-addressable hashing family, the typed in-place mutation
primitives that `EvoGradient` and `RewriteAgent` consume, the
record/replay cassette, and path resolution.

Every other submodule depends on this one; this one depends on
nothing inside `operad/`.

---

## Files

| File          | Role                                                                                  |
| ------------- | ------------------------------------------------------------------------------------- |
| `errors.py`   | `BuildError(reason, ...)` + `BuildReason` enum. Every type-check / contract failure.  |
| `hashing.py`  | `hash_str`, `hash_json`, `hash_prompt`, `hash_schema`, `hash_config`, `hash_model`, `hash_input`, `hash_content`. 16-hex SHA, stable across processes. |
| `ops.py`      | `Op` / `CompoundOp` mutation primitives: `SetRole`, `EditTask`, `AppendRule`, `SetModel`, `AppendExample`, ... Each has an undo function. |
| `paths.py`    | Dotted-path resolution helpers (`stage_0.role`, `rules[2]`).                          |
| `cassette.py` | LLM call recorder/replayer for offline-deterministic tests.                           |

## Public API

```python
from operad.utils.errors import BuildError, BuildReason
from operad.utils.hashing import (
    hash_str, hash_json, hash_prompt, hash_schema,
    hash_config, hash_model, hash_input, hash_content,
)
from operad.utils.ops import Op, CompoundOp, SetRole, EditTask, AppendRule
from operad.utils.cassette import Cassette
```

## Why each piece exists

- **Hashes are how reproducibility works.** Every `OperadOutput` ships
  with the seven `hash_*` fields above; identical fingerprints ⇒
  cassette hit, `Trace.replay` match, deterministic CI. Add to this
  family only when adding a new dimension of identity (rare).

- **`Op` is how `EvoGradient` and `RewriteAgent` mutate prompts in
  place.** Each `Op` is content-addressable, has an undo function, and
  composes via `CompoundOp`. Adding a new trainable parameter type
  typically lands as a new `Op` here.

- **`BuildError` is the single error type users see** for type
  mismatches, missing contracts, wrong return types. The reason enum
  is exhaustive — extend the enum if you add a new failure mode in
  `core/build.py`.

- **`cassette` makes the test suite offline.** Set
  `OPERAD_CASSETTE=record` once to capture real LLM calls; subsequent
  CI runs replay deterministically. A `CassetteMiss` names the
  drifting hash segment so you know *why* the replay failed.

## Smallest meaningful example

```python
from operad.utils.ops import AppendRule, SetRole
from operad.utils.hashing import hash_content

before = hash_content(agent)
SetRole(path="reasoner", role="Be skeptical.").apply(agent)
AppendRule(path="reasoner", rule="Cite at least one source.").apply(agent)
after = hash_content(agent)
assert before != after          # hash_content tracks declared state
```

```python
# Offline test mode
import os; os.environ["OPERAD_CASSETTE"] = "record"
# … run tests once, capture LLM calls into JSONL cassettes …
del os.environ["OPERAD_CASSETTE"]
# … subsequent runs replay from cassettes, no network …
```

## How to extend

| What                            | Where                                                                              |
| ------------------------------- | ---------------------------------------------------------------------------------- |
| A new mutation primitive        | `ops.py` — subclass `Op`; implement `apply(agent)` and an undo callable.           |
| A new identity dimension        | `hashing.py` — new `hash_<dim>(...)`; thread through `OperadOutput` if user-visible. |
| A new failure reason            | Add to `BuildReason` enum in `errors.py`; raise from the relevant `core/` site.    |

## Related

- [`../core/`](../core/README.md) — uses every helper here.
- [`../optim/`](../optim/README.md) — `EvoGradient` and `RewriteAgent`
  consume `Op` / `CompoundOp`.
- Top-level [`../../INVENTORY.md`](../../INVENTORY.md) §20 lists every
  `hash_*` field on `OperadOutput`.
