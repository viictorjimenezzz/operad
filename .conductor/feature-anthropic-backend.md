# Feature · Native Anthropic backend

**Addresses.** E-14 (ISSUES.md) + `TODO_NATIVE_ANTHROPIC_BACKEND` in
`missing.py`.

Every hosted provider today is OpenAI-compatible. Add a native
Anthropic adapter so users can target Claude directly, with proper
handling of Anthropic-specific features (system prompts, tool use,
extended thinking).

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-14.
- `operad/models/` — every existing adapter.
- `operad/models/__init__.py` (dispatcher and `extra` semantics table).
- strands' Anthropic model class.

---

## Proposal

### Configuration

Extend the `Backend` Literal:

```python
# operad/core/config.py
Backend = Literal[
    "llamacpp", "lmstudio", "ollama",
    "openai", "bedrock", "anthropic",
]

_REMOTE_BACKENDS: frozenset[Backend] = frozenset({"openai", "bedrock", "anthropic"})
```

`anthropic` is a remote backend — no `host`, requires `api_key`.

### Adapter

```python
# operad/models/anthropic.py (new)
"""Native Anthropic backend via strands.models.AnthropicModel.

Configuration:
    backend="anthropic"
    model="claude-opus-4-7" or "claude-sonnet-4-6" etc.
    api_key=$ANTHROPIC_API_KEY

Extra dict is forwarded via `additional_request_fields`; use it for
extended-thinking and other Anthropic-specific knobs.
"""
from __future__ import annotations

from ..core.config import Configuration


def build(cfg: Configuration):
    from strands.models.anthropic import AnthropicModel

    params = _anthropic_params(cfg)
    return AnthropicModel(
        model_id=cfg.model,
        api_key=cfg.api_key,
        **params,
    )


def _anthropic_params(cfg: Configuration) -> dict:
    out: dict = {}
    if cfg.temperature is not None:
        out["temperature"] = cfg.temperature
    if cfg.max_tokens is not None:
        out["max_tokens"] = cfg.max_tokens
    if cfg.top_p is not None:
        out["top_p"] = cfg.top_p
    if cfg.top_k is not None:
        out["top_k"] = cfg.top_k
    if cfg.stop is not None:
        out["stop_sequences"] = cfg.stop
    if cfg.timeout is not None:
        out["timeout"] = cfg.timeout
    if cfg.max_retries:
        out["max_retries"] = cfg.max_retries
    if cfg.extra:
        out.update(cfg.extra)
    return out
```

### Dispatch

```python
# operad/models/__init__.py
from .anthropic import build as _build_anthropic
...
case "anthropic":
    return _build_anthropic(cfg)
```

Update the docstring table of `extra` semantics to include anthropic.

### Integration test

Add `tests/integration/test_anthropic.py` mirroring the llamacpp/openai
pattern:

```python
@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("OPERAD_INTEGRATION") != "anthropic",
    reason="set OPERAD_INTEGRATION=anthropic to enable",
)
async def test_anthropic_structured_output():
    cfg = Configuration(
        backend="anthropic",
        model=os.environ.get("OPERAD_ANTHROPIC_MODEL", "claude-haiku-4-5"),
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )
    agent = Reasoner(config=cfg, input=Question, output=Answer)
    await agent.abuild()
    out = await agent(Question(text="What is 2 + 2?"))
    assert isinstance(out.response, Answer)
    assert out.response.answer.strip()
```

---

## Scope

- New: `operad/models/anthropic.py`.
- Edit: `operad/core/config.py` (Backend literal + _REMOTE_BACKENDS).
- Edit: `operad/models/__init__.py` (dispatch case + docstring).
- New: `tests/integration/test_anthropic.py`.
- Edit: `README.md` (mention anthropic under backends).
- Edit: `.conductor/2-L-integration-tests.md` won't exist anymore
  (removed in prior round); instead touch `README.md`.

Do NOT:
- Put `anthropic` SDK in base deps. It's an optional install behind
  strands' Anthropic adapter.
- Add model-specific logic for Claude 4.x. The adapter is a thin
  pass-through.

---

## Acceptance

- `uv run pytest tests/` green (offline).
- `OPERAD_INTEGRATION=anthropic ANTHROPIC_API_KEY=... uv run pytest tests/integration/test_anthropic.py`
  passes against a live Claude Haiku.
- `Configuration(backend="anthropic", ...)` round-trips through
  `hash_config` (verify in a test).

---

## Watch-outs

- strands' `AnthropicModel` constructor signature may differ from
  `BedrockModel` — verify by reading strands source before writing
  the adapter.
- Anthropic's `max_tokens` is required, not optional, for some
  endpoints. Default to `cfg.max_tokens` or a sensible floor (2048).
- Extended thinking (`thinking: {"type": "enabled", "budget_tokens": ...}`)
  goes through `extra` in v1. A first-class
  `Configuration.reasoning_tokens` field already exists — map it to
  Anthropic's budget when non-None.
