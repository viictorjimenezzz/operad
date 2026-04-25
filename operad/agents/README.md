# operad.agents — the component library

The `torch.nn`-style tier of operad. Two kinds of things live here:

1. **Structural operators** at the package root: `Pipeline`,
   `Parallel`. Domain-agnostic; they just compose other agents.
2. **Domain components and pre-wired patterns** under one folder per
   domain. Each domain folder has a `components/` subdir for its
   leaves and a domain-root file for any pre-wired multi-agent pattern.

Adding a new domain is a sibling folder mirroring this layout. Adding
a new component to an existing domain is a new file under that
domain's `components/`.

---

## Structural operators

| Class    | What it does                                                                  |
| -------- | ----------------------------------------------------------------------------- |
| `Pipeline(a, b, c, …)` | Sequential composition; each stage's `Out` must equal the next's `In`. |
| `Parallel({"a": x, "b": y}, input=…, output=…, combine=…)` | Fan-out to a dict of children, run concurrently, fold via `combine`. |

`Switch` (under `reasoning/switch.py`) routes at runtime based on a
router leaf's typed choice. `a >> b` is sugar for `Pipeline(a, b)` and
chains flatten.

## Domains shipped today

| Domain             | Components in `components/`                                                  | Pre-wired composites at the domain root |
| ------------------ | ---------------------------------------------------------------------------- | --------------------------------------- |
| `reasoning/`       | `Reasoner`, `ChatReasoner`, `Actor`, `Classifier`, `Critic`, `Evaluator`, `Extractor`, `Planner`, `Reflector`, `Retriever` (+ `BM25Retriever`, `FakeRetriever`), `Router`, `ToolUser` | `react.py` (`ReAct`), `switch.py` (`Switch`) |
| `coding/`          | `CodeReviewer`, `ContextOptimizer`, `DiffSummarizer`                          | `pr_reviewer.py` (`PRReviewer`)          |
| `conversational/`  | `Talker`, `ConversationTitler`, `InteractionTitler`                           | —                                        |
| `memory/`          | `Beliefs`, `User` + `MemoryStore`                                             | —                                        |
| `retrieval/`       | `CitationGist`, `EvidencePlanner`, `FactFilter`                               | —                                        |
| `safeguard/`       | `Context`, `Talker` (chat-scope guardrail leaves)                             | —                                        |
| `debate/`          | `Proposer`, `DebateCritic`, `Synthesizer` (used by `algorithms/debate.py`)    | —                                        |

The `agents.conversational.Talker` and `agents.safeguard.Talker` are
exported under disambiguated names at the top level
(`ConversationalTalker`, `SafeguardTalker`).

## The component pattern

Every leaf declares its contract on the class body:

```python
from pydantic import BaseModel
from operad import Agent, Configuration

class Q(BaseModel): text: str
class A(BaseModel): answer: str

class Concise(Agent[Q, A]):
    input  = Q
    output = A
    role   = "You are terse."
    task   = "Answer in one sentence."
    rules  = ("Never exceed 20 words.",)

leaf = Concise(config=Configuration(backend="llamacpp",
                                    host="127.0.0.1:8080",
                                    model="qwen2.5-7b"))
```

Construction kwargs override class attributes; instance mutation
afterward also works (`leaf.task = "..."`). Components also declare
opinionated `default_sampling` dicts that merge with the caller's
`Configuration.sampling` (e.g. `Classifier` pins `temperature=0.0`).

### Prompt attributes at a glance

Every Agent renders its system prompt from these class-level (and
instance-overridable) attributes:

| Attribute         | Type            | Purpose                                                                 |
| ----------------- | --------------- | ----------------------------------------------------------------------- |
| `role`            | `str`           | Persona the agent adopts.                                               |
| `task`            | `str`           | Single most important instruction; *what* the agent does.               |
| `style`           | `str`           | *How* the agent expresses itself (tone, register, verbosity).           |
| `context`         | `str`           | Static task-at-hand guidelines for *this deployment*.                   |
| `rules`           | `tuple[str, …]` | Hard constraints.                                                       |
| `examples`        | `tuple[Example, …]` | Typed few-shot demonstrations.                                      |
| `reasoning_field` | `str \| None`   | Opt-in: emit chain-of-thought on the wire under this field name.        |
| `stateless`       | `bool` (True)   | Each `invoke()` is independent; reuse one instance for fan-out.         |

`role` / `task` / `style` / `rules` / `examples` are all `Parameter`s
optimizers can move (see [`../optim/`](../optim/README.md)).
`reasoning_field` and `stateless` are structural — class-level switches,
not part of the trainable surface.

#### `context` semantics

`context` is a **static system-prompt section provisioned per-instance
at construction time** by the script or algorithm wiring this agent into
a deployment. Use it to hand the agent task-at-hand guidelines that are
constant for its lifetime in this deployment — *not* for per-call
iteration awareness inside a loop.

If an algorithm needs to send slow-changing per-call awareness (e.g.
"you are arguing the affirmative; the prior speaker said …"), add a
field to your **input class** marked with the system flag — it routes
into the per-call system prompt without busting the cached static base:

```python
from pydantic import BaseModel, Field

class DebateTurn(BaseModel):
    side: str = Field(
        json_schema_extra={"operad": {"system": True}},
        description="Which side this agent is arguing on this turn.",
    )
    transcript_so_far: str = Field(default="", description="Prior turns.")
```

#### `stateless` semantics

The default (`stateless = True`) means every `invoke()` runs against a
fresh, transient strands.Agent built from the leaf's resolved model and
the freshly-composed system + user message. No conversation history
carries across calls, and the operad Agent's own `system_prompt` /
`messages` are never mutated — so concurrent fan-out on a single shared
instance (e.g. `await asyncio.gather(*(agent(x) for x in batch))`)
is safe.

Subclasses that genuinely depend on multi-turn dialogue history opt out
with `stateless = False`. That re-enables strands' sliding-window
conversation manager and is single-threaded by contract.

## Smallest meaningful composite

```python
from operad import Pipeline, Parallel
from operad.agents.reasoning import Reasoner, Critic

# Sequential
graded = Pipeline(reasoner, critic)

# Fan-out + combine
both = Parallel(
    {"poet": poet_reasoner, "coder": coder_reasoner},
    input=Q, output=Report,
    combine=lambda r: Report(answers={k: v.answer for k, v in r.items()}),
)
```

`Switch` and `Router` route at runtime; see
`operad.agents.reasoning.switch`.

## How to extend

| What                            | Where                                                                                 |
| ------------------------------- | ------------------------------------------------------------------------------------- |
| A new component (leaf)          | `operad/agents/<domain>/components/<name>.py` — subclass `Agent[In, Out]`.            |
| A new pre-wired pattern         | `operad/agents/<domain>/<pattern>.py` — composite `forward` as a router.              |
| A new domain                    | `operad/agents/<new_domain>/` mirroring `reasoning/` (with `components/`, `schemas.py`, optional pre-wirings). |
| A schema shared across domains  | Promote it; otherwise keep it in the domain's `schemas.py`.                           |

### Two rules every component must satisfy

1. **`__init__` is side-effect-free.** No network, no provider
   handshakes, no model loading. All of that belongs in `build()`.
2. **Composite `forward` is a router, not a calculator.** The build
   sentinel proxy (`core/build.py`) raises `BuildError` if a composite
   reads payload values to decide which child to call.

## Roadmap

- `agents/reasoning/debate.py` and `agents/reasoning/verifier.py` —
  pre-wired composition wrappers parallel to `react.py`. The
  corresponding algorithms exist; the agent-level pre-wirings do not.
- `agents/conversational/TurnTaker`.

## Related

- [`../core/`](../core/README.md) — `Agent`, `Pipeline`, `Parallel`,
  `build`, `AgentGraph`.
- [`../algorithms/`](../algorithms/README.md) — outer loops that use
  these components as parameters.
- [`../optim/`](../optim/README.md) — what reads `Parameter` handles
  off these agents.
- Top-level [`../../INVENTORY.md`](../../INVENTORY.md) §6 — exhaustive
  per-domain leaf list.
