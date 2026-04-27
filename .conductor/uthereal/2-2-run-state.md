# 2-2 — ArtemisRunState

**Batch:** 2 · **Parallelizable with:** 2-1, 2-3, 2-4 · **Depends on:** 1-2

You are providing the mutable state object the runner threads through
its leaves. Phase-1 only: no streaming, no attachments, no memory
persistence.

## Goal

Define a Pydantic model that mirrors the subset of `ArtemisState` (from
selfserve/state.py) that the runner actually uses. This is the
data-flow contract: every field is a typed handoff between leaves.

## Files to create

| Path | Purpose |
|---|---|
| `apps_uthereal/workflow/state.py` | `ArtemisRunState` |
| `apps_uthereal/tests/test_run_state.py` | construction + invariant tests |

## API surface

```python
# apps_uthereal/workflow/state.py
"""Owner: 2-2-run-state."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from apps_uthereal.schemas.workflow import ArtemisInput, ArtemisFinalAnswer
from apps_uthereal.schemas.retrieval import (
    RetrievalSpecification,
    RetrievalResult,
    SummarizationResult,
    ClaimItem,
)


class ArtemisRunState(BaseModel):
    """Mutable state threaded through the runner.

    Construction: created from `ArtemisInput` at the start of a run.
    Mutation: each leaf may set its declared output fields. Each field
    has a sensible default so partial runs are safe.

    This is NOT a value object — `frozen=False`. The runner mutates it.
    Treat it like an `asyncio` task-local: one instance per run.
    """

    # --- inputs (set at construction; never mutated post-init) -----------

    input_message: str
    workspace_id: str
    context: str = ""
    workspace_guide: str = ""
    exit_strategy: str = ""
    target_language: str = ""
    chat_history: str = ""
    session_memory_context: str = ""
    prior_beliefs_context: str = ""
    character_limit: int | None = 10000

    # --- safeguard outputs ----------------------------------------------

    safeguard_decision: Literal["yes", "no", "exit"] | None = None
    safeguard_reason: str = ""
    safeguard_category: str = ""

    # --- reasoner outputs -----------------------------------------------

    rewritten_message: str = ""
    downstream_message: str = ""
    route: Literal["DIRECT_ANSWER", "RAG_NEEDED"] | None = None
    route_reasoning: str = ""
    reasoner_scratchpad: str = ""

    # --- retrieval pipeline outputs --------------------------------------

    matched_rules: list[dict] = Field(default_factory=list)
    retrieval_specs: list[RetrievalSpecification] = Field(default_factory=list)
    rag_results: list[RetrievalResult] = Field(default_factory=list)
    summarization_results: list[SummarizationResult] = Field(default_factory=list)
    collected_claims: dict[str, list[dict]] = Field(default_factory=dict)
    references: dict | None = None

    # --- final ----------------------------------------------------------

    utterance: str = ""
    final_step: str = ""
    intent_decision: Literal[
        "DIRECT_ANSWER", "RAG_NEEDED", "SAFEGUARD_REJECTED", "CHAR_LIMIT_REJECTED"
    ] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def from_input(cls, x: ArtemisInput) -> "ArtemisRunState":
        """Build a state from an ArtemisInput. Workspace metadata is
        read but not stored on the state — the runner consumes it
        directly when constructing retrieval specs."""

    def to_final_answer(self) -> ArtemisFinalAnswer:
        """Project the final answer envelope from terminal state."""
```

## Implementation notes

- **Mutability is intentional.** This is the only mutable object in the
  bridge. Everything else (schemas, traces, feedback) is frozen. Note
  the comment in the docstring; do not silently make it frozen.
- **Defaults that survive `model_construct()`.** Operad's tracer uses
  `model_construct()` for sentinels; every field needs a default. Lists
  use `Field(default_factory=list)`; dicts use
  `Field(default_factory=dict)`.
- **No `attachments` field.** Phase 1 explicitly excludes the VLM/image
  path (per AGENTS.md §9). If you find yourself wanting to add one, stop.
- **No `event_listener` field.** Streaming is excluded.
- **No `memory_manager` field.** Memory persistence is excluded. The
  three "context" string fields (`session_memory_context`,
  `prior_beliefs_context`, `chat_history`) are pre-rendered strings the
  caller provides on the dataset entry.
- **`rules` field name.** The state holds `matched_rules` (output of
  `RuleClassifier`); do NOT name it `rules` because that collides with
  operad's `Agent.rules` attribute on any subclass that holds a state
  reference.

## Acceptance criteria

- [ ] `ArtemisRunState.model_construct()` returns a state with all fields
      at default — no `ValidationError`.
- [ ] `ArtemisRunState.from_input(some_artemis_input)` returns a state
      with the input fields populated and the output fields at default.
- [ ] State mutation works: `state.utterance = "hello"` succeeds.
- [ ] `state.to_final_answer()` returns a typed `ArtemisFinalAnswer`
      consistent with terminal state.
- [ ] No imports from `uthereal_*`.

## Tests

- `test_run_state_construct_default` — `model_construct()` succeeds.
- `test_run_state_from_input_copies_fields` — every input field on
  `ArtemisInput` lands on the state.
- `test_run_state_is_mutable` — assignment to output field succeeds.
- `test_to_final_answer_for_direct_path` — set `intent_decision`,
  `utterance`, `final_step="conv_talker"`; assert `ArtemisFinalAnswer`.
- `test_to_final_answer_for_rag_path` — same with `references` set.
- `test_to_final_answer_for_safeguard_path` — `intent_decision="SAFEGUARD_REJECTED"`,
  `safeguard_category` populated.
- `test_to_final_answer_for_char_limit_path` — `intent_decision="CHAR_LIMIT_REJECTED"`.

## References

- `selfserve/state.py` (in uthereal-src) — the ground-truth state shape
  we mirror. Read for context only; do not import.
- `operad/core/agent.py` — defaults convention.
- `apps_uthereal/schemas/workflow.py` (1-2) — `ArtemisInput`,
  `ArtemisFinalAnswer`.

## Notes

- Implemented under `apps/uthereal/apps_uthereal/workflow/state.py`,
  matching the editable app package layout already present in this
  workspace.
- Excluded `ArtemisState` production handles and phase-1 out-of-scope
  fields: backend/config, live agent/workflow instances, input safeguards,
  event listener/streaming, memory manager and persisted memory state,
  image attachments/visual inspection, datasource/index caches, citation
  gist internals, titles, assistant examples, and tool-call stats.
- Contract gap: the assigned state includes `CHAR_LIMIT_REJECTED`, but
  the existing immutable
  `ArtemisFinalAnswer.intent_decision` schema only admits
  `DIRECT_ANSWER`, `RAG_NEEDED`, and `SAFEGUARD_REJECTED`. The state keeps
  `CHAR_LIMIT_REJECTED` for the terminal path and uses
  `ArtemisFinalAnswer.model_construct()` only for that projection, leaving
  the 1-2 vendored schema untouched.
