# Feature · Markdown renderer + chat-template-aware rendering

**Addresses.** E-9 (ISSUES.md) + `TODO_MARKDOWN_RENDERER` +
`TODO_CHAT_TEMPLATE_AWARE` in `missing.py`. VISION §7 calls out both.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-9.
- `operad/core/render.py`, `operad/core/agent.py::format_system_message`.
- `VISION.md` §7 "render.py: additional renderers".

---

## Proposal

Two related renderers, picked per-agent via a renderer selector.

### 1. Module split

Current `operad/core/render.py` is XML-only. Split:

```
operad/core/render/
  __init__.py        # re-exports xml.render_system as the default
  xml.py             # today's render.py content
  markdown.py        # new
  chat.py            # new — chat-template-aware
```

Backwards compat: `operad.core.render.render_system` remains importable.

### 2. Markdown renderer

Emits the same sections as XML but in Markdown — headings for role /
task / rules / examples / output schema. Good for models that handle
Markdown better than XML.

```markdown
# Role
You are a careful reasoner.

# Task
Work through the problem step-by-step.

# Rules
- Show reasoning before the final answer.

# Output schema
| Field | Type | Description |
| --- | --- | --- |
| reasoning | string | Step-by-step thought |
| answer | string | Final answer |
```

Field descriptions still surface (brief's acceptance test).

### 3. Chat-template-aware renderer

Some backends (llama.cpp with `--chat-template`, Ollama, LM Studio)
do better when the system / user split respects the model's native
template — ChatML, Mistral, Gemma. Instead of concatenating
everything into a single `system_prompt`, emit a structured
`list[{"role": ..., "content": ...}]` that the adapter passes to
strands' multi-message API.

Minimal v1:

```python
# operad/core/render/chat.py
def render_chat(agent) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": render_xml.render_system(agent)},
        # user turn added by format_user_message at invoke time
    ]
```

Later the renderer can interrogate the model name or backend's
`/props` endpoint to pick ChatML vs. Gemma vs. Mistral, but v1 is
just "system + user messages" instead of a single string.

### 4. Selection

Three hooks, simplest first:

- **Per-Configuration flag:**
  `renderer: Literal["xml", "markdown", "chat"] = "xml"`
- **Per-agent override:** subclass sets
  `renderer: ClassVar[str] = "markdown"`.
- **Runtime mutation:** `agent.renderer = "markdown"` works because
  Pydantic's `model_fields_set` logic applies only to Configuration.

Dispatch in `Agent.format_system_message`:

```python
def format_system_message(self) -> str | list[dict[str, str]]:
    mode = getattr(self, "renderer", None) or (
        self.config.renderer if self.config is not None else "xml"
    )
    if mode == "markdown":
        return render_markdown.render_system(self)
    if mode == "chat":
        return render_chat.render_system(self)
    return render_xml.render_system(self)
```

Note the return type widens to `str | list[dict[str, str]]`. Leaf
`forward` must handle both (string → `invoke_async(system_prompt=...)`,
list → pass as messages).

---

## Required tests

`tests/test_renderers.py`:

1. `render_markdown.render_system` for a sample agent contains every
   `Field(description=...)` and every rule.
2. `render_chat.render_system` returns a list with at least one system
   message carrying the schema.
3. Agent with `Configuration(renderer="markdown")` uses the Markdown
   path in `format_system_message`.
4. Per-agent `renderer` override wins over Configuration's.

---

## Scope

- New: `operad/core/render/` package replacing the single `render.py`.
- Edit: `operad/core/config.py` (new `renderer` field).
- Edit: `operad/core/agent.py::format_system_message` (dispatch).
- Edit: leaf `forward` to handle list-of-messages system prompt.
- New: `tests/test_renderers.py`.
- Edit: `CLAUDE.md` (mention the three renderers).

Do NOT:
- Try to detect the model's chat template from its name in v1. Just
  ship the "system + user" split; template detection is a follow-up.
- Drop XML — it remains the default and the most portable option.

---

## Acceptance

- `uv run pytest tests/` green.
- Existing tests (rendering, observers, build, etc.) unchanged in
  behaviour with `renderer="xml"`.
- A sample agent with `renderer="markdown"` produces a legible
  Markdown system prompt.
- `README.md` gains a "Renderers" subsection.

---

## Watch-outs

- Circular import potential in the split. `render/__init__.py` must
  not import Agent.
- `format_system_message`'s widened return type will ripple through
  anyone who expected `str`. Update cassette hashing to handle
  lists (hash the joined text or the sorted JSON dump of messages).
- Coordinate with `.conductor/feature-structuredio.md` if both land
  together — both touch `format_system_message`.
