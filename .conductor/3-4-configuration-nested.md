# 3 · 4 — Nested `Configuration` (`sampling`, `resilience`, `io`, `runtime`)

**Addresses.** R5 (restructure the flat `Configuration` into nested
sub-models).

**Depends on.** All Wave-2 tasks that touch `Configuration`
(2-1 through 2-11). Wave-3 ordering ensures this sweep happens after
every other consumer has settled — minimises merge pain.

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §4 (provider-agnostic runtime).
- `operad/core/config.py` — current 19-field flat `Configuration`.
- Every consumer of `Configuration` field access — grep for `.backend`,
  `.temperature`, `.max_tokens`, `.top_p`, `.top_k`, `.seed`,
  `.stop`, `.reasoning_tokens`, `.timeout`, `.max_retries`,
  `.backoff_base`, `.stream`, `.structuredio`, `.renderer`, `.extra`:
  - `operad/core/models.py` (all backend adapters).
  - `operad/core/agent.py` (render, invoke, stream).
  - `operad/core/render/*.py` (all renderers).
  - `operad/runtime/slots.py`.
  - `operad/core/build.py`.
  - Every example in `examples/`.
  - Every test under `tests/` that constructs a `Configuration`.

---

## Proposal

Nest `Configuration` into four sub-models. This trades a flat
19-field namespace for a small hierarchy that's easier to grow without
cluttering the top-level.

### New shape

```python
# operad/core/config.py

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


Backend = Literal[
    "llamacpp", "lmstudio", "ollama", "openai", "bedrock", "anthropic",
    "gemini", "huggingface",   # post-2-10
]


class Sampling(BaseModel):
    """LLM sampling knobs."""
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float | None = None
    top_k: int | None = None
    seed: int | None = None
    stop: list[str] | None = None
    reasoning_tokens: int | None = None

    model_config = ConfigDict(extra="forbid")


class Resilience(BaseModel):
    """Retry / timeout policy."""
    timeout: float | None = None
    max_retries: int = 0
    backoff_base: float = 0.5

    model_config = ConfigDict(extra="forbid")


class IOConfig(BaseModel):
    """Input/output rendering + streaming toggles."""
    stream: bool = False
    structuredio: bool = True
    renderer: Literal["xml", "markdown", "chat"] = "xml"

    model_config = ConfigDict(extra="forbid")


class Runtime(BaseModel):
    """Backend-specific pass-through fields."""
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class Configuration(BaseModel):
    """Provider-agnostic runtime knobs for a model call."""

    backend: Backend
    model: str
    host: str | None = None
    api_key: str | None = None
    batch: bool = False   # post-2-10

    sampling: Sampling = Field(default_factory=Sampling)
    resilience: Resilience = Field(default_factory=Resilience)
    io: IOConfig = Field(default_factory=IOConfig)
    runtime: Runtime = Field(default_factory=Runtime)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_host_matches_backend(self) -> "Configuration": ...
```

### Field-access rewrite table

| Old                     | New                                    |
|-------------------------|----------------------------------------|
| `cfg.temperature`       | `cfg.sampling.temperature`             |
| `cfg.max_tokens`        | `cfg.sampling.max_tokens`              |
| `cfg.top_p`             | `cfg.sampling.top_p`                   |
| `cfg.top_k`             | `cfg.sampling.top_k`                   |
| `cfg.seed`              | `cfg.sampling.seed`                    |
| `cfg.stop`              | `cfg.sampling.stop`                    |
| `cfg.reasoning_tokens`  | `cfg.sampling.reasoning_tokens`        |
| `cfg.timeout`           | `cfg.resilience.timeout`               |
| `cfg.max_retries`       | `cfg.resilience.max_retries`           |
| `cfg.backoff_base`      | `cfg.resilience.backoff_base`          |
| `cfg.stream`            | `cfg.io.stream`                        |
| `cfg.structuredio`      | `cfg.io.structuredio`                  |
| `cfg.renderer`          | `cfg.io.renderer`                      |
| `cfg.extra`             | `cfg.runtime.extra`                    |

`backend`, `model`, `host`, `api_key`, `batch` stay at the top level
(these are endpoint identifiers / credentials, not knobs).

### No backwards-compat

Delete the flat fields outright. **Do not** add `__getattr__` shims or
proxy properties. Every call site updates in this PR. Tests and
examples update in this PR. `CHANGELOG.md` or release notes mention
the rename — but no runtime fallback.

### Validator behaviour

`_check_host_matches_backend` stays untouched — it only reads `backend`
and `host`, both still at the top level.

A new validator for `batch` (from 2-10) stays: `batch=True` requires
a batch-capable backend.

### YAML/JSON round-trip

`Configuration.model_dump(mode="json")` emits the nested shape:

```json
{
  "backend": "openai",
  "model": "gpt-4o-mini",
  "api_key": "...",
  "batch": false,
  "sampling": {"temperature": 0.7, "max_tokens": 2048, ...},
  "resilience": {"timeout": null, "max_retries": 0, "backoff_base": 0.5},
  "io": {"stream": false, "structuredio": true, "renderer": "xml"},
  "runtime": {"extra": {}}
}
```

`Configuration.model_validate(...)` accepts either the nested JSON or,
for convenience, a flat dict whose keys match the nested leaves —
Pydantic v2 handles this natively via `model_validate` if we leave
`extra="forbid"` on sub-models *and* off the top-level; that's
asymmetric, so: **don't accept flat input**. Flat dicts raise a clear
validation error.

### Hash contract

`hash_config(cfg)` currently hashes `cfg.model_dump(mode="json", exclude={
"api_key"})`. After the refactor, the dump shape changes — **old
cassettes will mass-miss on `hash_model`**.

This is a deliberate break for cassette determinism. Document in the
release notes:

> Cassettes recorded before 3-4 land do not replay. Record against
> the new shape.

Provide a one-liner in the changelog for rebulk:
`OPERAD_CASSETTE=record uv run pytest tests/ -v`.

### Call-site sweep

Every file listed under "Required reading" must migrate in this PR.
The bulk of the change is mechanical `s/cfg\.([a-z_]+)/cfg.sub.\1/`.
A sed script for reference (do not commit it):

```bash
rg -l 'cfg\.(temperature|max_tokens|top_p|top_k|seed|stop|reasoning_tokens)' |
  xargs sed -i 's/cfg\.\(temperature\|max_tokens\|top_p\|top_k\|seed\|stop\|reasoning_tokens\)/cfg.sampling.\1/g'
# ... similar for resilience, io, runtime.
```

Inspect every edit; mechanical rewrites always miss at least one
tricky case (dict-style key access, YAML field names in tests).

---

## Required tests

`tests/test_config_nested.py` (new):

1. **Construct from nested JSON.** `Configuration(**json_nested)`
   validates; `cfg.sampling.temperature == 0.7`.
2. **Flat construction rejected.** `Configuration(backend="openai",
   model="x", api_key="y", temperature=0.5)` raises
   `ValidationError` (extra field at top level).
3. **Default factories.** `Configuration(backend="openai",
   model="x", api_key="y")` populates `sampling`, `resilience`,
   `io`, `runtime` with each sub-model's defaults.
4. **Host validator still works.** `Configuration(backend="llamacpp",
   model="x")` (no host) raises; `Configuration(backend="openai",
   model="x", api_key="y", host="localhost")` raises.
5. **Extra field rejection everywhere.** A typo in any sub-model
   (`sampling={"temparature": 0.7}`) raises.
6. **`hash_config` stable under round-trip.** `dump → model_validate`
   → `hash_config` is invariant.
7. **Round-trip through `examples/_config.py`.** After migrating
   the helper, `local_config()` produces a valid `Configuration` with
   the nested shape.

Plus: the **existing** test suite must pass end-to-end after every
call-site migration. Every test using `Configuration(...)` updates in
this PR.

---

## Scope

**New files.**
- `tests/test_config_nested.py`.

**Edited files.**
- `operad/core/config.py` — the restructure itself.
- `operad/core/models.py` — all adapters now read from
  `cfg.sampling.*`, `cfg.resilience.*`, `cfg.runtime.extra`.
- `operad/core/agent.py` — anywhere that reads `cfg.io.stream`,
  `cfg.io.structuredio`, `cfg.io.renderer`, `cfg.resilience.
  max_retries`, etc.
- `operad/core/render/*.py` — `renderer` field access moves.
- `operad/core/build.py` — any config field reads.
- `operad/runtime/slots.py` — only reads `cfg.backend` and
  `cfg.host`; unaffected, but verify.
- `operad/utils/hashing.py` — `hash_config` and `hash_model` helpers;
  dump shape changes.
- Every test fixture under `tests/` that constructs a
  `Configuration`.
- Every example under `examples/`, including `examples/_config.py`
  (the `local_config()` helper).
- `demo.py`.

**Must NOT touch.**
- Re-exports in `operad/__init__.py` — `Configuration` is already
  exported; just keep the name stable.
- `operad/agents/`, `operad/algorithms/` — these never read
  `Configuration` fields directly; they pass it through to leaves.
  (Verify with a grep; the assumption holds today.)

---

## Acceptance

- `uv run pytest tests/` green.
- `uv run python -c "import operad; print(operad.Configuration)"` works.
- `uv run --extra observers python demo.py` runs through the offline
  stages.
- `uv run python examples/<any>.py` works for every example.
- No `cfg.temperature` / `cfg.stream` / `cfg.renderer` (etc.) left
  in the repo under `operad/`, `tests/`, `examples/`. Grep audit.
- Cassettes are **not** migrated as part of this PR — they'll be
  re-recorded on first use (producing a `CassetteMiss` with the 2-9
  diff pointing at `hash_model` as the drift).

---

## Watch-outs

- **Every call site in one PR.** No partial migration. A half-done
  rename produces `AttributeError` at runtime on the untouched sites.
  Use `rg` aggressively to find every reader.
- **Pydantic v2 `ConfigDict(extra="forbid")` on sub-models.** With
  forbid set on each sub-model, unknown keys inside a nested block
  raise. Confirm the error message points at the sub-model (it does
  by default).
- **Cassette re-record expected.** Any repo landing this PR loses
  cassette replay determinism for the affected tests. Coordinate the
  re-record run as part of the PR merge. Publish the record command
  in the PR description.
- **`Experiment.save` stored configs.** 3-3's `state.json` dumps
  `cfg.model_dump(mode="json")`. After 3-4, stored experiments have
  the nested shape. Pre-3-4 experiments won't load (deliberate — no
  backwards-compat).
- **Default values preserved.** The restructure does NOT change
  any default values. `Configuration()` produces identical runtime
  behaviour modulo attribute paths. Tests that assert on defaults
  should still pass after the sweep.
- **`api_key` stays top-level.** Do NOT nest `api_key` under
  `runtime` or `resilience`. Top-level placement is load-bearing for
  the freeze/experiment scrubbers that redact by field name.
- **`batch: bool` from 2-10 stays top-level.** It's semantically
  closer to `backend` (endpoint selector) than to sampling. Keep it
  beside `api_key`.
- **Examples + CLAUDE.md.** `CLAUDE.md` contains snippets referencing
  `Configuration(..., renderer=...)`; update those to the nested
  form in this PR so the documentation matches the code.
- **Last in the wave.** This is Wave 3's final brief because every
  earlier brief may add fields to `Configuration` (e.g., 2-10's
  `batch`, 2-11's rate-limiting knobs if they chose a different
  approach). Land 3-4 after 2-1 through 2-11 and 3-1 through 3-3
  merge — then the call-site sweep is done once.
