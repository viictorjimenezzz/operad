# Phase 2 · Stream K — Docs, examples, CLAUDE.md, seeded few-shots

**Goal.** Turn the library into a learnable product. Populate the
unused `examples=` class attribute on every reasoning leaf, ship one
example per major abstraction, and write `CLAUDE.md` for
agent-assisted contribution.

**Owner.** One agent.
**Depends on.** Stream D for the eval-loop example; Stream F for the
evolutionary demo (optional — skip if F hasn't landed).
**Addresses:** B-5, D-1, D-2, D-4.

---

## Scope

### Files you will create
- `CLAUDE.md` — top-level Claude Code orientation.
- `examples/pipeline.py` — Pipeline of 3+ stages.
- `examples/react.py` — standalone ReAct demo.
- `examples/best_of_n.py` — `BestOfN` against a local model.
- `examples/custom_agent.py` — a user-defined `Agent[In, Out]`
  subclass.
- `examples/mermaid_export.py` — build, `to_mermaid`, print.
- `examples/eval_loop.py` — depends on Stream D.
- `tests/test_examples.py` — smoke-imports every example.

### Files you will edit
- `operad/agents/reasoning/components/reasoner.py`
- `operad/agents/reasoning/components/actor.py`
- `operad/agents/reasoning/components/extractor.py`
- `operad/agents/reasoning/components/evaluator.py`
- `operad/agents/reasoning/components/classifier.py`
- `operad/agents/reasoning/components/planner.py`
- `operad/agents/reasoning/components/critic.py`
  — add 1–2 canonical `examples=` per leaf.
- `README.md` — add pointers to the new examples.
- `operad/agents/reasoning/react.py:89` — if not already fixed in
  Stream A, type `config: Configuration`.

### Files to leave alone
- Any source file not listed above.

---

## Design direction

### `CLAUDE.md`

```markdown
# operad — Claude Code orientation

See METAPROMPT.md for sub-agent onboarding. This file is a quick map
for humans and one-off Claude sessions.

## Layout
operad/
  core/              Agent, build, render, Configuration
  agents/            typed components (torch.nn-style library)
  algorithms/        plain orchestrators with metric feedback
  metrics/           deterministic scorers + Metric protocol
  models/            per-backend adapters
  runtime/           slot registry + observers

## Conventions
- Components declare contracts as class attributes.
- Composites are pure routers; leaves do the model calls.
- `build()` type-checks before any tokens are generated.
- Offline tests use FakeLeaf from tests/conftest.py.

## Common tasks
- Add a leaf: follow agents/reasoning/components/reasoner.py
- Add a domain: copy agents/reasoning/ shape
- Run tests: uv run pytest tests/
- Integration: OPERAD_INTEGRATION=llamacpp OPERAD_LLAMACPP_HOST=...

## Where to find
- Core abstractions: operad/core/
- Component library: operad/agents/<domain>/
- Orchestrators: operad/algorithms/
- Known issues: ISSUES.md
- Stream briefs: .conductor/
```

### Seeded examples

Every leaf that ships without an `examples=` entry should gain one or
two. Keep them tiny and canonical — these are the docstring of the
leaf, rendered into the prompt, forever.

```python
# reasoner.py (after existing class body)
from ....core.agent import Example
from ....agents.reasoning.react import Task, Thought

examples = (
    Example(
        input=Task(goal="What is 2 + 2?"),
        output=Thought(
            reasoning="Addition: 2 + 2 sums to 4.",
            next_action="return the answer 4",
        ),
    ),
)
```

Each leaf's `examples` field must be a `Sequence[Example[In, Out]]` — if
the leaf is generic in `In` / `Out` and the class attribute is abstract,
consider leaving the *class-level* `examples` empty and providing the
seed examples in documentation instead. Don't force a bad match.

### Narrative examples

Each example file is ~30–50 lines. Clear comments explaining the
concept:

- `pipeline.py` — Pipeline of three stages; show typed edges.
- `react.py` — Standalone ReAct; single goal; print the mermaid graph
  before running.
- `best_of_n.py` — Generator + Critic + BestOfN over a trivia question.
- `custom_agent.py` — Minimal user-defined `Agent[Q, A]` subclass with
  its own typed contract.
- `mermaid_export.py` — Build, `print(to_mermaid(agent._graph))`.
- `eval_loop.py` — Run `evaluate()` over a 5-row dataset, print the
  report.

Every network-requiring example starts with a short "Requires a local
llama-server at $OPERAD_LLAMACPP_HOST" banner at the top.

### `tests/test_examples.py`

Smoke test: `import examples.pipeline` for each file. Confirms no
import error and no top-level network call. Offline-only.

---

## Tests

- `uv run pytest tests/test_examples.py` smoke-imports every example.
- If you seed examples on leaves, add a `tests/test_reasoning_examples.py`
  that asserts each leaf's `examples` list parses cleanly (no Pydantic
  errors).

---

## Acceptance

- `uv run pytest tests/` green.
- Running any example in `examples/` against a local model works (for
  network-gated ones: the banner matches documented env setup).
- `README.md` has a "Examples" subsection pointing at the new files.

---

## Watch-outs

- Don't pick complicated domains for examples. Trivia Q&A is enough to
  show shape.
- Don't couple examples to each other. Each stands alone.
- Don't change the canonical seed examples once shipped — they end up
  referenced in external docs.
- Do NOT create a `docs/` folder unless the brief explicitly asks;
  README + examples + CLAUDE.md is the first docs layer.
