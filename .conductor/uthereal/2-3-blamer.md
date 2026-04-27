# 2-3 — Blamer agent

**Batch:** 2 · **Parallelizable with:** 2-1, 2-2, 2-4 · **Depends on:** 1-2, 1-5

You are building the only learned component the bridge owns. The Blamer
reads a `WorkflowTrace` plus a human critique and decides which leaf is
responsible.

## Goal

Define `Blamer` as a custom operad `Agent[BlamerInput, BlamerOutput]`,
plus a small renderer that turns a trace + feedback into the Blamer's
input. The Blamer has its own prompt (authored here, not loaded from
YAML — it's bridge-internal).

## Files to create

| Path | Purpose |
|---|---|
| `apps_uthereal/feedback/blamer.py` | `BlamerInput`, `BlamerOutput`, `Blamer`, `render_blamer_input` |
| `apps_uthereal/tests/test_blamer.py` | structural + offline behavioral tests |
| `apps_uthereal/tests/fixtures/blamer/` | hand-labeled (trace, feedback, expected_target) cases |

## API surface

```python
# apps_uthereal/feedback/blamer.py
"""Owner: 2-3-blamer."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from operad import Agent, Configuration, Example
from apps_uthereal.workflow.trace import WorkflowTrace
from apps_uthereal.feedback.schema import HumanFeedback


KNOWN_LEAF_PATHS: tuple[str, ...] = (
    "context_safeguard",
    "safeguard_talker",
    "reasoner",
    "conv_talker",
    "rule_classifier",
    "retrieval_orchestrator",
    "evidence_planner",
    "fact_filter",
    "rag_talker",
)
SPECIAL_TARGETS: tuple[str, ...] = ("control_flow", "data", "no_fault")


class LeafSummary(BaseModel):
    """Compact description of a leaf for the Blamer's prompt."""
    step_name: str
    role: str
    task: str
    fired_in_trace: bool
    input_preview: str = ""
    output_preview: str = ""

    model_config = ConfigDict(frozen=True)


class BlamerInput(BaseModel):
    """The full context the Blamer needs to make a decision."""
    final_answer: str
    user_critique: str
    desired_behavior: str = ""
    trace_summary: str          # rendered by `WorkflowTrace.to_blamer_summary`
    leaves: list[LeafSummary]

    model_config = ConfigDict(frozen=True)


class BlamerOutput(BaseModel):
    target_path: Literal[
        "context_safeguard", "safeguard_talker", "reasoner", "conv_talker",
        "rule_classifier", "retrieval_orchestrator", "evidence_planner",
        "fact_filter", "rag_talker",
        # Special:
        "control_flow",  # workflow logic is wrong, no leaf rewrite would fix
        "data",          # the dataset entry / retrieval is wrong, not a leaf
        "no_fault",      # the human critique doesn't identify a problem we can act on
    ]
    rationale: str
    leaf_targeted_critique: str
    severity: float = Field(ge=0.0, le=1.0, default=1.0)

    model_config = ConfigDict(frozen=True)


class Blamer(Agent[BlamerInput, BlamerOutput]):
    """Reasons over a WorkflowTrace and a human critique to localize blame.

    Heuristic: prefer the earliest leaf whose output already contains the
    defect. Distinguish "wrong route" (Reasoner / ContextSafeguard) from
    "wrong style" (Talker). Refuse when the critique doesn't map to a
    leaf — that's "control_flow" or "no_fault".
    """

    input = BlamerInput
    output = BlamerOutput
    role = """..."""
    task = """..."""
    rules = (
        ...,
    )
    examples = (
        Example[BlamerInput, BlamerOutput](
            input=BlamerInput(...),
            output=BlamerOutput(...),
        ),
        ...
    )

    def __init__(self, *, config: Configuration | None = None) -> None:
        super().__init__(config=config or default_blamer_config(), input=BlamerInput, output=BlamerOutput)


def default_blamer_config() -> Configuration:
    """The Blamer uses `tier_to_config('thinking_high')` by default.

    Why: blame is a meta-reasoning task; we want the strongest model.
    Override via `Blamer(config=...)` in tests.
    """


def render_blamer_input(
    *,
    trace: WorkflowTrace,
    feedback: HumanFeedback,
    leaf_directory: dict[str, "operad.Agent"],
) -> BlamerInput:
    """Build the BlamerInput from a sealed trace and feedback.

    `leaf_directory` maps step_name → loaded leaf, used to fill
    `LeafSummary.role` and `LeafSummary.task` for leaves that didn't
    fire in this run.
    """
```

## Implementation notes

- **Authoring the prompt is your job.** The Blamer's `role/task/rules/
  examples` live on the class body (not in a YAML — this is a bridge-
  owned agent). Use `cleandoc` for multiline strings. The role should
  state that the agent is a "debugging agent for a multi-leaf prompt
  pipeline"; the task should explain the contract (single target, one
  of `KNOWN_LEAF_PATHS` or `SPECIAL_TARGETS`).
- **Examples are critical.** Author at least 5 examples covering:
  - Wrong route (route should have been DIRECT_ANSWER but was RAG_NEEDED) → `target_path="reasoner"`.
  - Wrong refusal (safeguard incorrectly blocked) → `target_path="context_safeguard"`.
  - Off-style answer (talker tone wrong) → `target_path="conv_talker"` or `"rag_talker"`.
  - Citation didn't resolve → `target_path="rag_talker"` (most likely the talker hallucinated, not the planner).
  - User complains about something the workflow can't fix (e.g.
    "your retrieval is too slow") → `target_path="control_flow"` or `"no_fault"`.
- **Heuristic in `rules`.** Encode "prefer the earliest leaf whose output
  already contains the defect"; "if the route is wrong, blame the
  Reasoner; if the route is right but the style is wrong, blame the
  Talker"; "if the rejection category was correct but the refusal text
  was bad, blame `safeguard_talker` not `context_safeguard`".
- **Severity guidance.** `severity` is the optimizer's `lr` knob: low
  values nudge the prompt, high values rewrite it. Default 1.0 is fine;
  the Blamer can lower it for partial fixes.
- **Renderer.** `render_blamer_input` produces a deterministic string
  layout — same inputs → same string. Truncate long fields (matches
  `WorkflowTrace.to_blamer_summary`).
- **Leaves directory.** Even leaves that didn't fire in this trace
  appear in `leaves` with `fired_in_trace=False`, so the Blamer can
  reason about whether the problem is "leaf X should have fired but
  didn't".

## Acceptance criteria

- [ ] `Blamer().abuild()` succeeds.
- [ ] `Blamer.input is BlamerInput`, `Blamer.output is BlamerOutput`.
- [ ] `BlamerOutput.target_path` is a Literal containing all 9 leaf
      step_names plus the 3 special targets.
- [ ] `render_blamer_input(trace, feedback, leaves)` returns a
      `BlamerInput` whose `trace_summary` is non-empty.
- [ ] Two calls of `render_blamer_input` on identical inputs return
      equal `BlamerInput`s.
- [ ] At least 5 examples on the Blamer class.
- [ ] On the labeled fixtures in `tests/fixtures/blamer/`, the Blamer's
      offline structural tests pass (the LIVE behavioral tests can be
      gated by an env var; offline runs that require the real LLM are
      skipped automatically).

## Tests

- `test_blamer_class_pins_input_output`.
- `test_blamer_target_path_literal_includes_all_leaves_and_specials`.
- `test_render_blamer_input_deterministic` — same inputs → same output.
- `test_render_blamer_input_includes_all_leaves` — even non-firing
  leaves show up with `fired_in_trace=False`.
- `test_render_blamer_input_truncates_long_fields`.
- `test_blamer_examples_validate` — every example's input and output
  validates against the schemas.
- `test_blamer_severity_in_unit_interval` — `severity` is always 0..1.
- (Behavioral, gated) `test_blamer_picks_reasoner_on_wrong_route` — runs
  against a cassette of the Blamer's own LLM call. Skip when cassette
  is absent.

## Fixtures

`tests/fixtures/blamer/` contains 5 hand-labeled cases:

```
case_wrong_route/
├── trace.jsonl
├── feedback.json
└── expected.json    # {"target_path": "reasoner", "rationale_substring": "..."}
case_wrong_refusal/
case_off_style/
case_unresolvable/
case_no_fault/
```

You author the fixture content. The reviewer will sanity-check.

## References

- `operad/agents/reasoning/components/critic.py` — closest existing
  pattern: a structured-output reasoning agent with rule-driven
  judgments.
- `operad/agents/reasoning/components/router.py` — pattern for an agent
  whose output is a Literal-typed routing decision.
- `apps_uthereal/workflow/trace.py` (1-5) — the trace API you consume.

## Notes

(Append discoveries here as you implement. Especially: which heuristics
in `rules` you tested via offline replay and how robust they were on the
fixtures.)

- Implemented exact target paths from `KNOWN_LEAF_PATHS`; no dotted aliases
  were added because the batch-2 API surface names direct runner paths.
- Offline fixture coverage is structural: wrong route, wrong refusal,
  off-style direct answer, unresolved citation, and no-fault critique all
  load and validate deterministically. The live Blamer behavioral test skips
  until a Blamer LLM cassette is recorded.
- `Blamer().abuild()` succeeds when run with the locked `gemini` extra
  installed. The base workspace without that extra cannot build default
  Gemini-backed agents, which is dependency/environment setup rather than
  Blamer API behavior.
