# 2-4 — Backprop (GradLLM) agents

**Wave.** 2 (depends on 1-1 for `TextualGradient`).
**Parallel with.** 2-1, 2-2, 2-3, 2-5.
**Unblocks.** 3-1 (`backward()`).

## Context

When `backward()` walks the tape in reverse, at each node it needs
two things:

1. **Output gradient propagation** — given a downstream `TextualGradient`
   (what the next layer wanted differently) plus this node's
   `(prompt, input, output)`, compute the gradient *on this node's
   output* (what this node should have emitted differently).
2. **Parameter gradient** — given the output gradient, compute the
   per-parameter gradient (how specifically the role / task /
   rules / examples should change to produce a better output).

Both of these are LLM calls. We package them as `Agent` subclasses so
they benefit from cassettes, hashing, observers, and schema
validation.

Read `.context/NEXT_ITERATION.md` §6 and
`operad/agents/reasoning/components/reflector.py` (closest existing
analog).

## Scope — in

### `operad/optim/grad_agent.py`

- Input/output schemas (Pydantic):
  - `PropagateInput`:
    - `prompt: str` — the rendered system prompt of the node
    - `input_str: str` — the node's input, dumped to JSON
    - `output_str: str` — the node's output, dumped to JSON
    - `downstream_gradient: str` — the critique flowing back from
      the downstream layer
    - `downstream_by_field: dict[str, str] = {}`
  - `PropagateOutput`:
    - `message: str` — the new critique, targeted at this node's output
    - `by_field: dict[str, str] = {}`
    - `severity: float` = 1.0
  - `ParameterGradInput`:
    - `parameter_kind: str`
    - `parameter_path: str`
    - `current_value: str`
    - `prompt: str`
    - `input_str: str`
    - `output_str: str`
    - `output_gradient: str` — what the output should have been
    - `output_by_field: dict[str, str] = {}`
  - `ParameterGradOutput`:
    - `message: str`
    - `severity: float`
    - `target_paths: list[str] = []`
- Base classes:
  - `class BackpropAgent(Agent[PropagateInput, PropagateOutput])`:
    - Opinionated defaults for "given this node's forward record and
      the downstream critique, emit a critique of what *this node's
      output* should have been." Task-specific subclasses can
      refine the prompt.
  - `class ParameterGradAgent(Agent[ParameterGradInput, ParameterGradOutput])`:
    - "Given this parameter's kind, current value, and the critique
      on this node's output, produce a specific critique of *this
      parameter*."
- Kind-specialized `ParameterGradAgent` subclasses:
  - `TextParameterGrad` (role / task)
  - `RuleListParameterGrad`
  - `ExampleListParameterGrad`
  - `FloatParameterGrad`
  - `CategoricalParameterGrad`
  These carry kind-appropriate prompts (a parameter-grad for
  `temperature` is a very different conversation than for `role`).
- Registry:
  - `PARAMETER_GRAD_AGENTS: dict[ParameterKind, type[ParameterGradAgent]]`.
  - `def parameter_grad_for(kind: ParameterKind) -> type[ParameterGradAgent]`.
- Helpers for converting agent I/O to strings (reuse Pydantic's
  `model_dump_json`; for non-BaseModel inputs, `repr()` or `str()`).
- Factory helpers:
  - `async def propagate(node: Agent, rendered_prompt, input, output,
    downstream_grad: TextualGradient, propagator: BackpropAgent) ->
    TextualGradient` — builds the `PropagateInput`, invokes, wraps
    the response as a `TextualGradient`.
  - `async def parameter_grad(param: Parameter, node: Agent,
    rendered_prompt, input, output, output_grad: TextualGradient,
    grad_agent: ParameterGradAgent) -> TextualGradient`.

### `operad/optim/__init__.py`

Export `BackpropAgent`, `ParameterGradAgent` and kind subclasses,
`PropagateInput/Output`, `ParameterGradInput/Output`, the registry,
`propagate`, `parameter_grad`.

### `tests/optim/test_grad_agent.py`

- Every concrete subclass constructs cleanly with `config=None`.
- Stubbed `BackpropAgent` (override `forward`) produces a
  deterministic `PropagateOutput`; `propagate(...)` wraps it into a
  `TextualGradient` with fields preserved.
- Stubbed `ParameterGradAgent` ditto for `parameter_grad(...)`.
- Registry has entries for every `ParameterKind` that should have a
  gradient agent (at minimum: role, task, rules, examples,
  temperature; model/backend/renderer are marked with clear
  `NotImplementedError` rewrites — these rarely need textual
  gradients, optimizers for them are in wave 4).
- Defense: `propagate` handles `downstream_gradient == ""` (null
  gradient) gracefully by returning null gradient — short-circuit, no
  LLM call.

## Scope — out

- Do **not** implement the walk-the-tape algorithm — that is 3-1.
- Do not implement `apply_rewrite` — that is 2-3.
- Do not modify existing `operad/agents/`.

## Dependencies

- `operad.core.agent.Agent`.
- Wave 1-1: `TextualGradient`, `ParameterKind`.
- `operad.core.render` (via default renderer).

## Design notes

- **Prompts are the product.** Same advice as 2-3: these prompts
  determine whether `backward()` converges or flails. Model them
  after TextGrad and DSPy optimizer prompts. Include explicit
  instructions:
  - "Do not fabricate facts about the node's input or output."
  - "If the output is already correct with respect to the downstream
    gradient, return severity=0."
  - "Be specific. Vague critiques produce bad rewrites."
- **Serialization of input/output.** For Pydantic inputs/outputs,
  `model_dump_json(indent=2)`. For non-Pydantic (shouldn't happen
  much), `str()` as fallback.
- **Truncation.** Rendered prompts can be long; provide a
  `max_prompt_chars: int = 8000` parameter to `propagate` /
  `parameter_grad` that truncates the `prompt` field (with a
  clear ellipsis marker) before invoking the BackpropAgent.
- **Default sampling.** `default_sampling = {"temperature": 0.3}` for
  backprop/grad agents — a little creativity, not too much.
- **Null gradient short-circuit.** Both `propagate` and
  `parameter_grad` must special-case the "no downstream gradient"
  case to avoid wasted LLM calls.

## Success criteria

- `uv run pytest tests/optim/test_grad_agent.py` passes offline with
  stubbed agents.
- `uv run ruff check operad/optim/grad_agent.py` is clean.
- `from operad.optim import BackpropAgent, ParameterGradAgent,
  propagate, parameter_grad` works.
- No edits outside `operad/optim/` and `tests/optim/`.
