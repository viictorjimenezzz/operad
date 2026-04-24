# 2 · 10 — New model backends: Gemini, Batch, HuggingFace

**Addresses.** M1 (Gemini), M2 (Batch API), M4 (local HuggingFace).

**Depends on.** 1-1-restructure (models package collapses to
`operad/core/models.py` in Wave 1; this PR extends that single file).

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §4 (provider-agnostic runtime).
- `operad/core/models.py` *(post-1-1; collapses the old
  `operad/models/*.py` into a single file with `resolve_model(cfg)` at
  the bottom)*.
- `operad/core/config.py` — `Backend` literal + `Configuration` field
  table. The `batch: bool` toggle is a new Configuration field this
  PR adds.
- `operad/utils/errors.py` — `BuildError` for unknown-backend paths.
- `pyproject.toml` — `[project.optional-dependencies]` section.

---

## Proposal

Extend `operad/core/models.py` with three new adapters and wire them
through `resolve_model(cfg)`. All three are optional extras; core
operad must stay importable without them.

### M1 — Gemini (Google) adapter

Native Gemini adapter, separate from the OpenAI-compatible fallback
that already works through `lmstudio`/`openai` aliasing. Uses
`google-generativeai` or `google-genai` (whichever strands-models
supports as of merge time — prefer the strands adapter if one exists).

- Fields consumed from `Configuration`:
  `backend="gemini"`, `model`, `api_key`, `temperature`, `max_tokens`,
  `top_p`, `top_k`, `seed`, `stop`, `reasoning_tokens`
  (→ `thinking_config.thinking_budget`), `timeout`, `max_retries`.
- `host` must be **absent** (hosted backend).
- `extra` splats into the SDK's generation config.

Optional extra: `[gemini]`.

### M2 — Batch API adapter

A new adapter that routes submission through whichever backend the
user's `model` resolves to, but via that provider's batch endpoint.
Returns a **handle** rather than a live response. Applies to providers
with batch support (OpenAI, Anthropic, Bedrock); errors cleanly for
local backends.

- Orthogonal to `backend`: triggered by `Configuration.batch: bool =
  False`. `backend` still selects the provider; `batch=True` selects
  the batch endpoint for that provider.
- Return type from `forward`: a thin `BatchHandle` pydantic model
  carrying `provider_batch_id`, `submitted_at`, `endpoint`. The
  caller polls via a provider-specific helper that lives **in this
  PR** as `poll_batch(handle) -> BatchResult | None`.
- For Wave 2, the invoke-semantics change is **documented but not
  wired into the `Agent.invoke` envelope**. Invoking a batch-configured
  agent raises `BuildError("prompt_incomplete", "batch mode is opt-in;
  use Agent.forward directly and poll via models.poll_batch")` unless
  the caller is explicitly using the low-level forward.
  Full invoke-side integration is a future brief.

```python
class BatchHandle(BaseModel):
    provider: Backend
    provider_batch_id: str
    endpoint: str
    submitted_at: float
    raw: dict[str, Any] = Field(default_factory=dict)


async def poll_batch(handle: BatchHandle) -> "BatchResult | None":
    """Return BatchResult when ready, None while in-flight."""
```

No optional-extra addition beyond each provider's existing dep;
providers that don't support batch (llamacpp, lmstudio, ollama)
raise `BuildError("prompt_incomplete", ...)` at resolve time.

### M4 — Local HuggingFace adapter

Runs a `transformers.pipeline`-backed model on local hardware (CPU,
CUDA, MPS). Async-safe by offloading `pipeline()` calls to a thread
via `asyncio.to_thread`.

- Fields consumed: `backend="huggingface"`, `model` (HF model ID or
  local path), `temperature`, `max_tokens` (→ `max_new_tokens`),
  `top_p`, `top_k`, `seed` (→ `transformers.set_seed`), `stop` (→
  `stopping_criteria`), `extra` splats into `pipeline(**extra)`.
- `host` must be **absent**.
- `api_key` ignored.

Optional extra: `[huggingface]`.

### `Backend` literal

Extend in `operad/core/config.py`:

```python
Backend = Literal[
    "llamacpp", "lmstudio", "ollama", "openai", "bedrock", "anthropic",
    "gemini", "huggingface",
]
```

Update `_LOCAL_BACKENDS` and `_REMOTE_BACKENDS`:

```python
_LOCAL_BACKENDS = frozenset({"llamacpp", "lmstudio", "ollama", "huggingface"})
_REMOTE_BACKENDS = frozenset({"openai", "bedrock", "anthropic", "gemini"})
```

Note: `huggingface` is *local* (no host validation; runs in-process),
but `host` remains optional — `None` is the common case; any value is
rejected via the existing `_check_host_matches_backend` validator
path.

### `Configuration.batch` flag

```python
class Configuration(BaseModel):
    ...
    batch: bool = False
```

Validator: when `batch=True`, backend must be one of
`{"openai", "anthropic", "bedrock"}`. Otherwise raise `ValueError`.

### `resolve_model` dispatch

Extend the `match` in `resolve_model`:

```python
match cfg.backend:
    case "llamacpp": ...
    ...
    case "gemini":
        return _build_gemini(cfg)
    case "huggingface":
        return _build_huggingface(cfg)
    case other:
        raise BuildError("prompt_incomplete", f"unknown backend {other!r}")
```

When `cfg.batch=True`, dispatch instead goes through a new
`_build_batch(cfg)` branch at the top of `resolve_model` that wraps
the underlying provider's batch endpoint. Example:

```python
def resolve_model(cfg: Configuration) -> "Model":
    if cfg.batch:
        return _build_batch(cfg)
    match cfg.backend:
        ...
```

### `pyproject.toml`

```toml
[project.optional-dependencies]
gemini = ["google-genai>=0.3"]   # or google-generativeai; pick whichever strands supports
huggingface = ["transformers>=4.40", "torch>=2.2"]
```

All three new deps are strictly optional.

---

## Required tests

`tests/test_model_backends.py` (new; offline with mocks):

1. **Gemini resolve.** Patch `google.genai` with a MagicMock; construct
   `Configuration(backend="gemini", model="gemini-1.5-pro", api_key="x")`;
   `resolve_model(cfg)` returns a mocked model object without raising.
2. **Gemini without extra.** Omit `google.genai` from `sys.modules`;
   confirm `resolve_model` raises `ImportError`-derived error with a
   clear `[gemini]` hint.
3. **HuggingFace resolve.** Patch `transformers.pipeline` with a
   MagicMock; resolve returns the model.
4. **HF without extra.** Patch `transformers` absent; `ImportError`
   with `[huggingface]` hint.
5. **Batch flag validation.** `Configuration(backend="llamacpp",
   model="x", host="...", batch=True)` raises `ValueError` at
   construction.
6. **Batch handle shape.** With a mocked OpenAI batch endpoint,
   `resolve_model` for `Configuration(backend="openai",
   model="gpt-4o-mini", api_key="x", batch=True)` returns a model that
   submits and surfaces a `BatchHandle` on `forward`. Field check:
   `handle.provider_batch_id` is non-empty.
7. **`Backend` literal widened.** `operad.Configuration(backend=
   "gemini", model="x", api_key="y")` validates without error.

Integration tests (behind `OPERAD_INTEGRATION`, one per backend):

- `tests/integration/test_gemini.py` — real Gemini call (requires
  `GEMINI_API_KEY`), runs only when `OPERAD_INTEGRATION=gemini`.
- `tests/integration/test_huggingface.py` — loads a tiny HF model
  (e.g. `HuggingFaceTB/SmolLM2-135M`) and runs a single forward.
  Runs only when `OPERAD_INTEGRATION=huggingface`.
- `tests/integration/test_batch.py` — submits one batch to OpenAI,
  polls until done. Runs only when `OPERAD_INTEGRATION=batch`.

All integration tests skip by default.

---

## Scope

**New files.**
- `tests/test_model_backends.py`.
- `tests/integration/test_gemini.py` (skip by default).
- `tests/integration/test_huggingface.py` (skip by default).
- `tests/integration/test_batch.py` (skip by default).

**Edited files.**
- `operad/core/models.py` — add three adapter functions + dispatcher
  cases.
- `operad/core/config.py` — extend `Backend` literal, add `batch:
  bool` field, extend `_LOCAL_BACKENDS`/`_REMOTE_BACKENDS`, add
  `batch`-backend cross-check validator.
- `pyproject.toml` — add `[gemini]` and `[huggingface]` extras.

**Must NOT touch.**
- Anything outside `operad/core/models.py`, `operad/core/config.py`,
  `pyproject.toml`.
- `operad/runtime/`, `operad/agents/`, `operad/algorithms/`.
- `operad/__init__.py` (the top-level re-exports don't change).

---

## Acceptance

- `uv run pytest tests/test_model_backends.py` green.
- `uv run pytest tests/` green (full suite; integration skipped).
- `uv run pip install -e '.[gemini]'` succeeds.
- `uv run pip install -e '.[huggingface]'` succeeds.
- `uv run python -c "import operad"` works without any new extras.
- `operad.Configuration.model_fields` includes `batch`; the `Backend`
  literal includes `"gemini"` and `"huggingface"`.

---

## Watch-outs

- **Strands model class vs native SDK.** The existing adapters
  (`llamacpp`, `ollama`, etc.) wrap strands' model classes. If
  `strands-models` ships a native Gemini wrapper, prefer it — it
  inherits strands' retry/structured-output plumbing for free.
  Otherwise, write a thin `strands.models.Model` subclass in this PR
  that wraps the google-genai SDK. Same question for HuggingFace;
  strands may or may not have a local-HF class.
- **Batch semantics are explicitly partial in Wave 2.** Users must
  understand: `batch=True` changes the *return type* of forward.
  Invoke-path integration is a future brief. Raise a clear
  `BuildError` if someone tries `await agent.invoke(x)` with
  `cfg.batch=True`; do not silently succeed.
- **`Configuration.batch` hash domain.** `hash_config` must include
  the new `batch` field so a batch-mode run and a non-batch run
  hash differently (no cassette cross-contamination). Confirm via
  a test: `hash_config(cfg, batch=True) != hash_config(cfg,
  batch=False)`.
- **HF thread safety.** `transformers.pipeline` is not async. Call
  it via `await asyncio.to_thread(pipeline, ...)`. Multiple
  concurrent invokes against the same HF pipeline instance may block
  each other — document that the HF adapter is serial per pipeline.
- **HF model loading cost.** Pipelines are expensive to construct.
  Cache by `(model, device)` tuple at module scope so repeated
  `resolve_model` calls for the same config reuse the pipeline. This
  breaks the "resolve returns a fresh object" invariant — document
  that clearly in a comment at the cache site.
- **Single-file growth.** `operad/core/models.py` is already the
  landing target for the six existing backends (post-1-1). With
  three more, the file grows toward 600+ LOC. The user explicitly
  asked for a single file; don't split in this PR. If future
  iterations outgrow one file, that's a separate refactor brief.
- **Optional-dependency style.** Use module-local `try/except
  ImportError` at function entry, not top-of-module — that way the
  single `operad.core.models` module stays importable on any
  install.
- **`api_key` in frozen agents.** Gemini's adapter takes the key from
  `cfg.api_key`. Confirm 2-2's freeze path strips it (freeze
  serialiser must drop `api_key` before JSON dump). No change here;
  just don't regress the invariant.
