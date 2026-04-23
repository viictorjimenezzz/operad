# Feature · Default sampling config per Agent class

**Addresses.** E-12 (ISSUES.md) + `TODO_DEFAULT_CONFIG_PER_AGENT` in
`missing.py`.

Each Agent subclass should carry an opinionated default sampling
profile (temperature, top_p, max_tokens, seed) that merges with the
user-supplied `Configuration` at construction time. Backend selection
(provider, host, api_key) stays the caller's choice — only sampling
knobs have sensible per-component defaults.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-12, `VISION.md` §5.2.
- `operad/core/agent.py::Agent.__init__`.
- All leaf class bodies under `operad/agents/reasoning/components/`.

---

## Proposal

### Class attribute

```python
class Agent(strands.Agent, Generic[In, Out]):
    default_sampling: ClassVar[dict[str, Any]] = {}
```

Subclasses override with a small, opinionated dict:

```python
class Classifier(Agent[In, Out]):
    default_sampling = {"temperature": 0.1, "max_tokens": 256}

class Reasoner(Agent[In, Out]):
    default_sampling = {"temperature": 0.7}

class Critic(Agent[Candidate, Score]):
    default_sampling = {"temperature": 0.0, "max_tokens": 512}
```

### Merge at `__init__`

When the caller passes a `Configuration`, merge class defaults in
**only for fields the caller did not set explicitly.** User wins.

Implementation sketch:

```python
def __init__(self, *, config=None, ...):
    ...
    if config is not None:
        merged = dict(type(self).default_sampling)
        # user-supplied fields override class defaults
        user_set = config.model_fields_set   # Pydantic v2 tracks explicit sets
        for k, v in merged.items():
            if k not in user_set and hasattr(config, k):
                config = config.model_copy(update={k: v})
    self.config = config
```

`Configuration.model_fields_set` gives exactly the fields the user
explicitly provided at construction. Defaults are NOT in that set —
so class defaults fill them in, while user-explicit values are left
alone.

### Curated defaults

Add opinionated `default_sampling` to these leaves at minimum:

| Leaf | Recommended `default_sampling` |
| --- | --- |
| `Reasoner` | `{"temperature": 0.7}` |
| `Actor` | `{"temperature": 0.3}` |
| `Classifier` | `{"temperature": 0.0, "max_tokens": 128}` |
| `Extractor` | `{"temperature": 0.0}` |
| `Evaluator` | `{"temperature": 0.2}` |
| `Planner` | `{"temperature": 0.4}` |
| `Critic` | `{"temperature": 0.0, "max_tokens": 512}` |
| `Router` | `{"temperature": 0.0, "max_tokens": 64}` |
| `Reflector` | `{"temperature": 0.3}` |
| `ToolUser` | `{"temperature": 0.0}` |

Domain leaves (coding, conversational, memory) follow their own
logic — add defaults only where you're confident.

---

## Scope

- Edit: `operad/core/agent.py` (class attr + __init__ merge).
- Edit: each leaf under `operad/agents/reasoning/components/*.py`.
- Edit: domain leaves where defaults are obvious.
- New tests: `tests/test_default_sampling.py`.

Do NOT:
- Put backend / host / model defaults in `default_sampling`. Those
  are deployment concerns, not component concerns.
- Mutate the user-passed Configuration in place. Always `model_copy`.

---

## Acceptance

- `uv run pytest tests/` green.
- New test confirms: `Classifier(config=Configuration(backend="openai", model="gpt-4o-mini")).config.temperature == 0.0`.
- New test confirms: `Classifier(config=Configuration(backend="openai", model="gpt-4o-mini", temperature=0.9)).config.temperature == 0.9`
  (user's explicit value wins).
- Existing tests that pass an explicit temperature still pass.
- `README.md` adds one line under "Core ideas" about class-level
  sampling defaults.

---

## Watch-outs

- `Configuration(extra="forbid")` — ensure `default_sampling` keys are
  actual Configuration field names, not typos.
- Don't merge `max_tokens` into backends that use a different name.
  Let the adapter layer translate.
- `model_fields_set` is Pydantic v2 only — the project already pins v2.
