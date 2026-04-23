# Phase 2 · Stream H — Conversational domain

**Goal.** Ship `operad/agents/conversational/` with leaves (`Safeguard`,
`TurnTaker`, `Persona`) and one composed pattern (`Talker`). Mirror
the shape of `operad/agents/reasoning/`.

**Owner.** One agent.
**Depends on.** Stream E (`Switch` is essential for safeguard
short-circuiting).
**Addresses:** C-4 (conversational sub-domain).

---

## Scope

### Files you will create
- `operad/agents/conversational/__init__.py`
- `operad/agents/conversational/components/__init__.py`
- `operad/agents/conversational/components/safeguard.py`
- `operad/agents/conversational/components/turn_taker.py`
- `operad/agents/conversational/components/persona.py`
- `operad/agents/conversational/talker.py`
- `tests/test_conversational_components.py`, `test_talker.py`.
- `examples/talker.py`.

### Files you will edit
- `operad/agents/__init__.py` — re-exports.
- `operad/__init__.py` — re-exports.

### Files to leave alone
- Reasoning, coding, memory domains.

---

## Design direction

### Typed shapes

```python
class Utterance(BaseModel):
    user_message: str
    history: str = Field(default="", description="Prior conversation as a flat string.")

class SafeguardVerdict(BaseModel):
    label: Literal["allow", "block"]
    reason: str = ""

class TurnChoice(BaseModel):
    action: Literal["respond", "clarify", "defer"]
    prompt: str = Field(default="", description="Clarifying question if action=clarify.")

class StyledUtterance(BaseModel):
    response: str
```

### Leaves

- **`Safeguard(Agent[Utterance, SafeguardVerdict])`** — emits
  `label: Literal["allow", "block"]`, making it ideal as a `Router`
  input to `Switch`.
- **`TurnTaker(Agent[Utterance, TurnChoice])`** — chooses between
  responding, asking for clarification, or deferring.
- **`Persona(Agent[Utterance, StyledUtterance])`** — produces the final
  styled response.

All three follow the standard default-forward leaf pattern with
`role` / `task` / `rules` at class level and one `Example(...)` in
`examples=`.

### `Talker` composition

A Safeguard rejection must short-circuit the rest. Use `Switch` from
Stream E:

```
Safeguard → Switch(label)
              ├── allow: Pipeline(TurnTaker, Persona)
              └── block: RefusalLeaf  (emits a polite refusal)
```

Both branches must return `StyledUtterance`. A minimal `RefusalLeaf`
can hard-code a polite template without even calling the model (just
override `forward` to return a fixed `StyledUtterance`).

If Stream E's `Switch` isn't merged yet when you start, scaffold the
pipeline against a mock composite and swap in `Switch` when it lands.

---

## Tests

- `Safeguard` with a canned FakeLeaf returns the expected verdict.
- `Talker` routes an allowed utterance through TurnTaker → Persona.
- `Talker` routes a blocked utterance to the refusal branch without
  invoking TurnTaker or Persona.
- Mermaid export shows both branches.

---

## Acceptance

- `uv run pytest tests/` green.
- `examples/talker.py` runs a short conversation (2–3 turns) against a
  local model.

---

## Watch-outs

- `Safeguard` is easy to over-engineer. Stay `Literal["allow", "block"]`
  for v1; multi-class taxonomies are a later addition.
- Conversation history is a `str` in v1 — structured memory is Stream
  I's problem. Don't try to introduce a shared session object.
- Keep `Persona.role` generic ("helpful, concise assistant"); users
  will subclass for specific personae.
