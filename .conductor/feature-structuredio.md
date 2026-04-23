# Feature · `Configuration.structuredio: bool` — toggle structured vs. serialized I/O

**Addresses.** E-3 (ISSUES.md) + `TODO_STRUCTURED_IO` in `missing.py`.

Today every leaf renders input as XML strings (`render_input`) and
always requests structured output via `strands.invoke_async(..., structured_output_model=Out)`.
That is the right default, but some backends and users want the
alternative: pass the Pydantic instance directly through without
string rendering, or fall back to textual JSON output when native
structured output is missing.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-3, `VISION.md` §5–§6.
- `operad/core/config.py`, `operad/core/agent.py::Agent.forward` /
  `format_user_message`, `operad/core/render.py`.

---

## Proposal

Add `structuredio: bool = True` to `Configuration`.

**`structuredio=True` (default — current behaviour).** Pass the
Pydantic instance to strands with `structured_output_model=self.output`.
Response is parsed natively by strands. `format_user_message` still
runs, but the rendered string is treated as context — the request
shape is enforced by strands.

**`structuredio=False` (new).** Pass the rendered XML string (current
`render_input`) as the user message; do NOT pass `structured_output_model`
to strands. Parse the model's textual response against `self.output`
by hand (`self.output.model_validate_json(text)` with graceful error).

In BOTH modes, the model must see:
1. Input field names, types, and `Field(description=...)`.
2. Output schema with types and descriptions (`render_output_schema`).

Current `render.py` surfaces all three. The test below asserts it.

---

## Required test

Write a new `tests/test_structuredio.py`:

1. Build a `Reasoner` with `structuredio=True`; capture the exact
   arguments passed to `strands.invoke_async` via a mock/spy.
   Assert `structured_output_model=Out` was passed and the user
   message contains every `Field(description=...)` string from the
   input class.
2. Same setup with `structuredio=False`: assert `structured_output_model`
   was NOT passed and the user message still contains all
   descriptions plus the output-schema block.
3. Parse path: with `structuredio=False`, feed a canned textual JSON
   response and assert the output validates to the typed `Out`.

Use `FakeLeaf`-style spying to avoid real network. Name the spy helper
`tests/_spy_strands.py` if it's more than a one-liner.

---

## Scope

- Edit: `operad/core/config.py` (new field, default True).
- Edit: `operad/core/agent.py::Agent.forward` (dispatch on
  `self.config.structuredio`).
- Edit: `operad/core/render.py` only if you need a JSON-mode renderer
  sibling — prefer to reuse what's there.
- New: `tests/test_structuredio.py`, optional `tests/_spy_strands.py`.
- Edit: `operad/__init__.py` if re-exports change.

Do NOT:
- Change existing examples' behaviour (default stays `True`).
- Touch `OperadOutput` hashing — `hash_prompt` should include the
  final wire string in both modes.

---

## Acceptance

- `uv run pytest tests/` green; new test passes.
- Field descriptions reach the model in both modes (test assertion).
- Backwards compatible: no existing test needs to change.
- README mentions the flag under a short "Structured vs textual I/O"
  section.

---

## Watch-outs

- `strands.invoke_async` semantics differ across adapters when
  `structured_output_model` is omitted. Verify behaviour with
  openai + llamacpp adapters; document any divergence in
  `operad/models/__init__.py`.
- `structuredio=False` parse path can fail on malformed model output;
  raise `BuildError("output_mismatch", ...)` rather than a raw
  `ValidationError`.
- This is a leaf-only concern. Composites are unaffected.
