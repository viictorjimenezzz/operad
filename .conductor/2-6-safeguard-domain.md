# 2 · 6 — `agents/safeguard/` — task-agnostic guardrail leaves

**Addresses.** S2 (input sanitisation), S3 (output moderation).

**Depends on.** 1-1-restructure.

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §7 (safety as a first-class concern),
  `ISSUES.md` §B (composite payload branching — the safeguard domain
  must not route on payload values).
- `operad/agents/conversational/components/safeguard.py` —
  `Safeguard(Agent[Utterance, SafeguardVerdict])` stays put; this PR
  adds a *new, generic* domain.
- `operad/agents/conversational/__init__.py` — structure to mirror.
- `operad/agents/reasoning/` — the canonical shape for a domain
  (`schemas.py`, `components/`, `__init__.py`).
- `operad/core/agent.py` — `Agent[In, Out]` contract + class-attribute
  pattern.

---

## Proposal

Today's `Safeguard` lives in `conversational/` and is tied to
`Utterance`/`Turn`. That's right for conversational flows, but leaves a
gap for non-conversational pipelines that want generic input
sanitisation (strip PII, truncate overly long text, reject binary
payloads) or output moderation (classify a leaf's response against a
policy).

Add a new **task-agnostic** domain `operad/agents/safeguard/` with two
independent leaves:

- **`InputSanitizer[T]`** — a pass-through `Agent[T, T]` whose
  `forward_out` (from 2-1) or `forward` (if used standalone) normalises
  or redacts the payload. Subclass-friendly: override the policy, not
  the type.
- **`OutputModerator[T]`** — `Agent[T, ModerationVerdict]`. Runs a
  deterministic or LLM-backed policy check against any payload and
  emits a verdict. Composed downstream by callers via `Pipeline(
  upstream, OutputModerator)` or as a `forward_out` hook.

Both leaves are generic on `T`. They're intended to be dropped into an
existing pipeline without introducing conversational types.

### Layout

```
operad/agents/safeguard/
    __init__.py           # re-exports
    schemas.py            # GuardInput, ModerationVerdict, SanitizerPolicy
    components/
        __init__.py
        input_sanitizer.py
        output_moderator.py
```

### `schemas.py`

```python
from typing import Literal
from pydantic import BaseModel, Field


class ModerationVerdict(BaseModel):
    """A binary allow/block verdict with a short rationale."""
    label: Literal["allow", "block"]
    reason: str = Field(default="", description="Short rationale (≤ 2 sentences).")
    categories: list[str] = Field(
        default_factory=list,
        description="Optional policy categories triggered (e.g. 'pii', 'toxicity').",
    )


class SanitizerPolicy(BaseModel):
    """Declarative sanitisation rules consumed by InputSanitizer."""
    strip_pii: bool = True
    max_chars: int | None = None
    redact_pattern: str | None = None   # regex; matched substrings → "[REDACTED]"
    lowercase: bool = False
```

### `components/input_sanitizer.py`

```python
from typing import Generic, TypeVar
from pydantic import BaseModel
from ....core.agent import Agent
from ..schemas import SanitizerPolicy

T = TypeVar("T", bound=BaseModel)


class InputSanitizer(Agent[T, T], Generic[T]):
    """Pass-through leaf that redacts/truncates string fields in `T`.

    Walks the payload's Pydantic fields, applies the policy to any
    `str` field, and returns a new instance of `T` with sanitised
    values. Non-string fields pass through untouched. Override
    `sanitize_str` for custom redaction.
    """

    input = BaseModel   # overridden per-instance in __init__
    output = BaseModel

    role = "Sanitise string fields in the incoming payload before downstream use."
    task = (
        "Apply the configured SanitizerPolicy to every string field: "
        "redact matches of the policy pattern, truncate to max_chars, "
        "strip PII-like substrings when enabled."
    )
    rules = (
        "Do not alter non-string fields.",
        "Preserve the original field names exactly.",
        "Return a new instance; do not mutate the input in place.",
    )

    def __init__(
        self,
        *,
        schema: type[T],
        policy: SanitizerPolicy | None = None,
    ) -> None:
        super().__init__(config=None, input=schema, output=schema)
        self._policy = policy or SanitizerPolicy()

    def sanitize_str(self, s: str) -> str: ...

    async def forward(self, x: T) -> T: ...
```

Runs as an **override-forward leaf** (no LLM needed). `forward` walks
`x.model_fields`, applies `sanitize_str` to every string-valued field,
and constructs `type(x)(**...)` with sanitised values.

### `components/output_moderator.py`

```python
from typing import Generic, TypeVar
from pydantic import BaseModel
from ....core.agent import Agent, Example
from ..schemas import ModerationVerdict

T = TypeVar("T", bound=BaseModel)


class OutputModerator(Agent[T, ModerationVerdict], Generic[T]):
    """Classify an arbitrary payload against a policy.

    Default-forward leaf: the model judges the payload. Subclass to
    tighten the role/task or narrow `output` to a Literal-constrained
    verdict subtype.
    """

    input = BaseModel    # overridden per-instance in __init__
    output = ModerationVerdict

    role = "You enforce an output policy for downstream consumers."
    task = (
        "Review the payload below and decide whether it is appropriate "
        "for release. Emit 'allow' when safe; 'block' when it would "
        "produce disallowed, unsafe, or policy-violating content."
    )
    rules = (
        "Default to 'allow' for ordinary outputs; reserve 'block' for "
        "clear violations (PII exposure, hostile content, hallucinated "
        "sensitive advice).",
        "Always include a short reason (≤ 2 sentences).",
        "List triggered categories when relevant (e.g. 'pii', 'toxicity').",
    )
    examples = (
        # generic example: a bare str wrapper shown as safe
    )

    def __init__(
        self,
        *,
        schema: type[T],
        config=None,
    ) -> None:
        super().__init__(config=config, input=schema, output=ModerationVerdict)
```

No custom `forward` — this is a default-forward leaf that relies on the
strands-backed structured-output path.

### `agents/__init__.py` wiring

Re-export the new domain at `operad.agents.safeguard`:

```python
from . import safeguard  # noqa: F401
```

The top-level `operad.__init__` does **not** promote these names (per
1-1 stratification cap). Users import from
`operad.agents.safeguard` directly.

### Compositional patterns (documentation only, not code)

Document in a brief paragraph at the top of
`operad/agents/safeguard/__init__.py`:

```
Compose via Pipeline or forward hooks:

    pipe = Pipeline(
        InputSanitizer(schema=Question),
        Reasoner(...),
        OutputModerator(schema=Answer),
    )

Or as forward hooks on an existing leaf (2-1):

    class SafeReasoner(Reasoner):
        def forward_in(self, x): return _san.forward_sync(x)
        def forward_out(self, x, y): ... # custom gate on verdict

Both leaves are generic — construct with the concrete payload type
you're guarding.
```

No registry, no DI container — composition is explicit.

---

## Required tests

`tests/test_safeguard.py` (new):

1. **InputSanitizer redaction.** Pydantic model with `text: str,
   count: int`; policy `redact_pattern=r"\bSSN-\d+\b"`; input
   contains `"user SSN-12345"`; forward returns a new instance with
   `"user [REDACTED]"` and `count` unchanged.
2. **InputSanitizer truncation.** Policy `max_chars=10`; input
   `text="hello world"`; output `text="hello worl"`.
3. **InputSanitizer type preservation.** `type(out) is type(in)` for
   any input model; no Pydantic revalidation errors.
4. **OutputModerator build.** `OutputModerator(schema=Question,
   config=_fake_cfg).build()` succeeds; graph JSON includes the
   moderator as a leaf.
5. **OutputModerator forward (offline).** Use a FakeLeaf wrapping a
   cassette-free stub that returns `ModerationVerdict(label="allow",
   reason="benign")`. Assert `await mod(x)` returns the envelope,
   `.response.label == "allow"`.
6. **Pipeline composition.** `Pipeline(InputSanitizer(schema=Foo),
   Reasoner, OutputModerator(schema=Answer))` builds without type
   errors; Mermaid rendering names all three stages.

All tests offline; FakeLeaf / cassette-free. No network.

---

## Scope

**New files.**
- `operad/agents/safeguard/__init__.py`
- `operad/agents/safeguard/schemas.py`
- `operad/agents/safeguard/components/__init__.py`
- `operad/agents/safeguard/components/input_sanitizer.py`
- `operad/agents/safeguard/components/output_moderator.py`
- `tests/test_safeguard.py`

**Edited files.**
- `operad/agents/__init__.py` — add `from . import safeguard`.

**Must NOT touch.**
- `operad/agents/conversational/` — leave `Safeguard` / `SafeguardVerdict`
  in place; this PR does not move, rename, or deprecate them.
- `operad/agents/reasoning/` or any other existing domain.
- `operad/core/`.
- Any runtime, algorithms, or metrics file.

---

## Acceptance

- `uv run pytest tests/test_safeguard.py` green.
- `uv run pytest tests/` green.
- `from operad.agents.safeguard import InputSanitizer, OutputModerator,
  ModerationVerdict, SanitizerPolicy` works.
- `from operad.agents.conversational import Safeguard` still works
  (untouched).
- `operad.agents.safeguard` shows up in `dir(operad.agents)`.

---

## Watch-outs

- **Two `Safeguard`-like symbols.** The existing `Safeguard` in
  `conversational/` and the new `OutputModerator` in `safeguard/`
  coexist. Do NOT rename the old one; do NOT alias. A user who wants
  conversational-flavoured guardrails imports from
  `operad.agents.conversational`; a user who wants generic guardrails
  imports from `operad.agents.safeguard`. The top-level `operad`
  namespace does not re-export either.
- **`ModerationVerdict` vs `SafeguardVerdict`.** Do not share schemas
  across domains. The conversational domain's `SafeguardVerdict` is
  purpose-built (it may embed `Utterance` context in later iterations);
  this PR's `ModerationVerdict` is the generic analogue. Distinct
  types with distinct hashes.
- **Generic `Agent[T, T]` + class attributes.** `Agent`'s contract
  wants `input`/`output` as class attributes. For generic leaves we
  override them in `__init__` via `super().__init__(input=schema,
  output=schema)`. Confirm that `build()` honours per-instance
  `input`/`output` (it does — see `_init_strands` in 1-1's
  consolidated envelope), and that `hash_schema` reflects the concrete
  type at build time.
- **`InputSanitizer` has no LLM.** It's an override-forward leaf; don't
  give it a `Configuration`. `config=None` must be accepted by
  `Agent.__init__`.
- **PII heuristics stay simple.** `strip_pii=True` applies a minimal
  regex set (SSN-style, email, phone). Don't ship a heavyweight
  recogniser. Callers who want Presidio/hardened PII plug their own
  via `SanitizerPolicy.redact_pattern` or a `sanitize_str` override.
- **No payload-value routing.** Per `ISSUES.md` §B, composites must not
  branch on payload values. `OutputModerator` returns a verdict; it's
  the caller's pipeline or a `Switch` that routes on `verdict.label`,
  not anything in this PR.
