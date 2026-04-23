# METAPROMPT — Sub-agent onboarding for operad

You are one of several agents contributing to `operad`, a typed, composable
agent library built on top of Strands Agents. Each contributor works on a
single stream and merges directly into `main`. This document is your
orientation. Read it top to bottom before writing a line of code.

---

## 1. Required reading (in order)

1. **`README.md`** — the library's current status, public surface, install
   and test commands.
2. **`VISION.md`** — the bet we are making: `torch.nn` for agents, the
   components-vs-algorithms split, symbolic `build()` trace. This is the
   non-negotiable shape of the library. If your brief conflicts with
   `VISION.md`, the vision doc wins — flag the conflict and stop.
3. **`AGENTS.md`** — four short principles for reasoning about changes.
4. **`ISSUES.md`** — catalogue of known risks, footguns, and gaps. Cite
   issue numbers (e.g. `A-1`, `B-3`) when your work addresses one.
5. **Your stream brief** — `.conductor/<phase>-<stream>-<title>.md`.
   Defines your scope, files to touch, design direction, and acceptance
   criteria. Do not pick up work outside it.

---

## 2. Repository conventions you must preserve

These are load-bearing invariants. Violating them is a bug, not a style choice.

- **Class-attribute contracts.** A component (`Agent[In, Out]` subclass)
  declares `input`, `output`, `role`, `task`, `rules`, `examples` at the
  class level. Instances override via constructor kwargs only. No wrapper
  object, no hidden state.
- **Composites are pure routers.** When you override `forward` on a
  composite, never inspect payload *values*. Route based on which child
  to call, not on the content of `x`. The build-time sentinel uses
  Pydantic field defaults, so payload-dependent branches are silently
  mis-traced today (see `ISSUES.md` §A-1). If a decision must depend on
  payload values, push it into a leaf (e.g. a `Router` leaf emitting a
  typed `Literal` choice) and dispatch via the `Switch` composite.
- **`build()` before invoke.** Leaves need `config`; composites do not.
  `build()` symbolically traces the tree, type-checks each edge, and
  wires `strands.Agent` for default-forward leaves. `__init__` must
  never touch a provider.
- **Components vs. algorithms.** A typed `In -> Out` contract means it is
  a component (subclasses `Agent[In, Out]`, lives in `agents/`). A
  loop-with-metric-feedback whose natural API is not `__call__(x)` means
  it is an algorithm (plain class with `run(...)`, lives in
  `algorithms/`). Do not force algorithms into the Agent mold.
- **Offline tests use `FakeLeaf`.** See `tests/conftest.py`. Any test
  that hits a real model goes to `tests/integration/` and is gated by
  `OPERAD_INTEGRATION`.

---

## 3. Working discipline (operationalized from `AGENTS.md`)

- **State assumptions before coding.** If two interpretations are
  plausible, present them — don't pick silently. If something is unclear,
  stop and ask.
- **Keep changes surgical.** Every changed line should trace to your
  stream brief. No drive-by formatting, no adjacent refactors, no
  speculative abstractions. If you notice unrelated rough edges, add a
  note to `ISSUES.md` in your PR — don't fix them.
- **No speculative features.** Add only what your brief requires. Three
  similar lines beat one premature abstraction.
- **Do not add error handling for impossible scenarios.** Trust internal
  callers; validate only at system boundaries.
- **No comments that explain *what*.** The code already does that. Only
  write a comment when the *why* is non-obvious (a hidden constraint, a
  workaround, a subtle invariant).

---

## 4. Prompt-engineering best practices

Two flavours apply to you:

### 4a. Writing prompts inside operad (new leaves, new domains)

- **Surface `Field(description=...)` on every `In` and `Out`.** The
  renderer threads these into the XML schema; that is how the model
  learns each field's meaning (DSPy-style). Missing descriptions make
  the model guess.
- **Prefer short, orthogonal `rules`.** Three unambiguous constraints
  beat a ten-item list where two overlap or contradict.
- **`role` is the persona; `task` is the single most important
  instruction.** Don't blur them. "You are a rigorous critic" is role.
  "Score the candidate from 0.0 to 1.0" is task.
- **`examples` are typed `(In, Out)` pairs**, not strings. Ship one or
  two canonical ones with every new leaf — shipping empty `examples` is
  a missed opportunity.
- **Keep `role` / `task` / `rules` model-agnostic.** Don't reference a
  specific model's quirks; the renderer targets XML, which all supported
  backends tolerate.

### 4b. Reasoning about your own work (you, the sub-agent)

- **Verify before you cite.** If your plan references `Agent.foo()`,
  grep for it. Stale facts from docs or prior conversation are the
  common cause of wasted work.
- **Read the surrounding test files before touching code.**
  `tests/conftest.py` is the offline harness; its patterns tell you
  how every other test is shaped.
- **Prefer adding a test that fails, then making it pass.** For bug
  fixes especially: write the failing test first.
- **Narrow your context.** Don't explore the whole repo when your
  stream lives in two subfolders. Use `Explore` for breadth, direct
  reads for depth.
- **State intent aloud before tool calls that will take effort.** One-
  sentence framing keeps your reasoning grounded and gives the user a
  cheap interrupt point.
- **Use `TaskCreate` for multi-step work.** Mark each task in progress
  when you start and completed the moment it's done — don't batch.

---

## 5. Merge discipline

- **One PR per stream.** Keep it scoped to the files named in your brief.
- **Phase 1 streams (A, B) merge first.** If you are on a Phase-2
  stream, rebase onto `main` after Phase 1 lands; you may need to
  absorb new `BuildError` reasons (from A) or a new `Agent.state()`
  method (from B).
- **Shared-file touchpoints are called out in your brief.** Two streams
  may each need a one-line edit to `operad/core/agent.py` (Stream B
  adds `state()`; Stream C adds an observer hook). Minimise the blast
  radius; coordinate via the task list if you see a conflict coming.
- **Offline tests must be green before you open the PR.**
  `uv run pytest tests/` is the bar. Integration tests stay gated.
- **Branch naming.** Concrete, specific, under 30 characters, no
  prefix. Examples: `sentinel-proxy`, `agent-state`, `rich-observer`.
- **Commit style.** Small, reviewable commits. The initial commit was
  `825df8b Initial commit: operad 0.1.0`; follow that register.

---

## 6. Verification before you ship

```bash
uv sync                              # install
uv run pytest tests/                 # offline suite must be green
uv run python -c "import operad"     # smoke: package imports cleanly
```

Your stream brief may list additional acceptance criteria — those are
the bar, not this checklist alone. If your stream adds a new example,
run it. If it adds integration tests, add the opt-in env-var guard and
do **not** run them as part of the default pytest invocation.

---

## 7. When in doubt

Stop and ask. Blocked work on a wrong assumption is far more expensive
than a clarifying question.
