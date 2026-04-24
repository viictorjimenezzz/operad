# operad.optim — orchestration overview

**Read first.** Every task brief in `.construct/optim/` assumes you
have read `.context/NEXT_ITERATION.md` (design rationale) and
`operad/optim/README.md` (design surface). Those two docs plus this
overview plus your task-specific brief should be sufficient context
to implement.

## How to use this folder

Files in `.construct/optim/` follow the name convention
**`<sequential>-<parallel>-<short-title>.md`**:

- `<sequential>` is the wave number (1, 2, 3, ...). Tasks in the
  same wave run **in parallel**; the next wave starts only after
  **every** task in the prior wave is merged to `main`.
- `<parallel>` is the slot within the wave. Slots are coordinated
  to touch **disjoint files** so parallel agents never collide on
  `main`.
- `<short-title>` is a kebab-case descriptor for humans.

When picking up a task:

1. Read the file. It tells you goal, scope, dependencies, files to
   create/modify, what to avoid, and success criteria.
2. Confirm every `<sequential>-*` task from prior waves is merged.
3. Do the work, ship a PR naming the task (`operad.optim §<wave>-<slot>:
   <title>`), and close the task.

## The waves

### Wave 1 — foundations (2 tasks)

Nothing in `operad.optim/` exists yet (except the package skeleton).
Each task creates a disjoint new file tree.

| Slot | Title                              | Touches                                         |
| ---- | ---------------------------------- | ----------------------------------------------- |
| 1-1  | Parameter foundation               | `operad/optim/parameter.py` + tests             |
| 1-2  | Data layer (DataLoader, split)     | `operad/data/**` + tests                        |

### Wave 2 — building blocks (5 tasks)

With `Parameter` and `TextualGradient` in hand, five independent
building blocks go in.

| Slot | Title                     | Touches                                        |
| ---- | ------------------------- | ---------------------------------------------- |
| 2-1  | Agent surface additions   | `operad/core/agent.py` + hooks tests           |
| 2-2  | Loss abstractions         | `operad/optim/loss.py` + tests                 |
| 2-3  | Rewrite agents library    | `operad/optim/rewrite.py` + tests              |
| 2-4  | Backprop (GradLLM) agents | `operad/optim/grad_agent.py` + tests           |
| 2-5  | Tape + TapeObserver       | `operad/optim/tape.py` + tests                 |

**Coordination note.** Slot 2-1 is the only wave-2 task that edits
files outside `operad/optim/`. All other slots create fresh modules
under `operad/optim/`.

### Wave 3 — algorithmic core (2 tasks)

| Slot | Title                          | Touches                                     |
| ---- | ------------------------------ | ------------------------------------------- |
| 3-1  | `backward()` propagation       | `operad/optim/backward.py` + tests          |
| 3-2  | Optimizer base + SGD           | `operad/optim/optimizer.py`, `.../sgd.py` + tests |

### Wave 4 — fleet + trainer (3 tasks)

| Slot | Title                                          | Touches                                                   |
| ---- | ---------------------------------------------- | --------------------------------------------------------- |
| 4-1  | Optimizer fleet (Momentum, Evo, OPRO, APE)     | `operad/optim/momentum.py`, `.../evo.py`, `.../opro.py`, `.../ape.py` + tests |
| 4-2  | LR schedulers                                  | `operad/optim/lr_scheduler.py` + tests                    |
| 4-3  | Trainer + callbacks                            | `operad/train/**` + tests                                 |

### Wave 5 — integration and polish (5 tasks)

| Slot | Title                                        | Touches                                                 |
| ---- | -------------------------------------------- | ------------------------------------------------------- |
| 5-1  | End-to-end offline training demo             | `examples/train_demo.py`, `scripts/verify.sh`           |
| 5-2  | Documentation updates                        | `README.md`, `VISION.md`, `FEATURES.md`, `TRAINING.md`  |
| 5-3  | `state_dict` / freeze-thaw integration       | `operad/core/agent.py`, `operad/core/freeze.py` + tests |
| 5-4  | PromptTraceback                              | `operad/optim/traceback.py` + tests                     |
| 5-5  | Cassette replay validation for training runs | `tests/optim/test_cassette_training.py`                 |

## Global conventions (apply to every task)

- **Offline-testable.** Every new component ships with a
  `FakeLeaf`-style test that runs with zero network. If a component
  needs an LLM (BackpropAgent, RewriteAgent), the test stubs the
  `forward` via subclassing or monkeypatching.
- **Imports only downward.** `operad/optim/*` may import from
  `operad/core/`, `operad/runtime/`, `operad/agents/`,
  `operad/metrics/`, `operad/algorithms/`. The reverse is forbidden —
  `operad/core/` must not import from `operad/optim/` (breaks the
  dependency DAG for users who only need inference).
- **Pydantic-first.** Every public data type is a `pydantic.BaseModel`
  (not a `dataclass`) unless there's a specific reason.
- **Async-first.** Every runtime method that can be async, is.
  `step()`, `backward()`, `compute()` — all `async def`.
- **No behavioural regressions.** Existing `operad` tests keep
  passing. `operad/algorithms/` and `operad/agents/` do not change
  in waves 1-4 (wave 5 may *deprecate* `Evolutionary` but may not
  remove it).
- **Style.** Match the repo: PEP-8 via `ruff`, 120-col soft, narrow
  docstrings, no comment clutter. Read `AGENTS.md` before you open
  a PR.
- **PR naming.** `operad.optim §<wave>-<slot>: <title>` — e.g.
  `operad.optim §2-3: Rewrite agents library`.

## Escaping the plan

These briefs are guidance, not contracts. If during implementation
you discover a better partitioning, a missing dependency, or a spec
error:

1. **Flag it in the PR description**, citing which brief to update.
2. **Prefer a small amendment PR** to `.construct/optim/*.md` over
   silently drifting from the plan. Future-you and parallel agents
   rely on these briefs being accurate.
3. **If a task is blocked** on another in-flight task, say so in the
   PR and pick up a different slot. Do not invent a new wave on the fly.
