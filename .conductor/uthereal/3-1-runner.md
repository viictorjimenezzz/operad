# 3-1 — ArtemisRunner (the integration cliff)

**Batch:** 3 · **Parallelizable with:** — (single task) · **Depends on:** 1-4, 1-5, 2-1, 2-2

You are the integrator. Every leaf, the retrieval client, the run state,
and the trace observer come together in one operad-native composition
that mirrors a stripped subset of `selfserve/workflow.py`. This is the
largest single deliverable in the plan; budget accordingly.

## Goal

Implement `ArtemisRunner` as an operad `Agent[ArtemisInput,
ArtemisFinalAnswer]` whose `forward` runs nine leaves in the right
order, threads `ArtemisRunState` between them, calls the
`RetrievalClient` between `RetrievalOrchestrator` and `EvidencePlanner`,
and emits a `WorkflowTrace` for the whole run.

## Files to create

| Path | Purpose |
|---|---|
| `apps_uthereal/workflow/runner.py` | `ArtemisRunner` |
| `apps_uthereal/workflow/render.py` | small helpers that turn `ArtemisRunState` slices into per-leaf inputs |
| `apps_uthereal/tests/test_runner.py` | end-to-end runner tests with cassettes |
| `apps_uthereal/tests/fixtures/runner/` | dataset entries + cassettes covering all 4 paths |

## API surface

```python
# apps_uthereal/workflow/runner.py
"""Owner: 3-1-runner."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from operad import Agent, Configuration
from operad.runtime.observers.base import registry

from apps_uthereal.schemas.workflow import (
    ArtemisInput, ArtemisFinalAnswer, DatasetEntry, WorkspaceMetadata,
)
from apps_uthereal.workflow.state import ArtemisRunState
from apps_uthereal.workflow.trace import WorkflowTrace, WorkflowTraceObserver
from apps_uthereal.retrieval.client import RetrievalClient
from apps_uthereal.leaves.registry import load_all_leaves, LEAF_REGISTRY


class ArtemisRunner(Agent[ArtemisInput, ArtemisFinalAnswer]):
    """Operad-native composition equivalent to a stripped ArtemisWorkflow.

    Construction wires up nine leaves loaded from YAML and a
    RetrievalClient. `forward(x)` runs the right path:

        ContextSafeguard
            ↓ continue_field
        ┌── "no" / "exit" → SafeguardTalker → return
        └── "yes" → Reasoner
                ↓ route
            ┌── DIRECT_ANSWER → ConvTalker → return
            └── RAG_NEEDED  → RuleClassifier → RetrievalOrchestrator
                              → for spec in specs: retrieval.retrieve(spec)
                              → EvidencePlanner → FactFilter → RAGTalker → return

    The character_limit precheck happens before ContextSafeguard. If the
    input message exceeds the limit, the runner short-circuits with a
    deterministic CHAR_LIMIT_REJECTED answer (no LLM calls).

    config = None — composite. Each child leaf has its own Configuration.
    """

    config = None

    def __init__(
        self,
        *,
        selfserve_root: Path,
        retrieval: RetrievalClient,
        config_overrides: dict | None = None,
    ) -> None:
        super().__init__(
            config=None,
            input=ArtemisInput,
            output=ArtemisFinalAnswer,
        )
        self.retrieval = retrieval

        leaves = load_all_leaves(selfserve_root, config_overrides=config_overrides)
        self.context_safeguard          = leaves["context_safeguard"]
        self.safeguard_talker           = leaves["safeguard_talker"]
        self.reasoner                   = leaves["reasoner"]
        self.conv_talker                = leaves["conv_talker"]
        self.rule_classifier            = leaves["rule_classifier"]
        self.retrieval_orchestrator     = leaves["retrieval_orchestrator"]
        self.evidence_planner           = leaves["evidence_planner"]
        self.fact_filter                = leaves["fact_filter"]
        self.rag_talker                 = leaves["rag_talker"]

    async def forward(self, x: ArtemisInput) -> ArtemisFinalAnswer:
        """Single-call path. Does NOT install the trace observer.
        Use `run_with_trace` for the public, traced path."""

    async def run_with_trace(
        self,
        x: ArtemisInput,
    ) -> tuple[ArtemisFinalAnswer, WorkflowTrace]:
        """Public entry point used by every CLI command.

        Installs WorkflowTraceObserver for the duration; returns the
        sealed trace alongside the typed answer.
        """
```

## Implementation notes

- **Path branches in `forward`.** Use plain `if/await`. No
  `pydantic_graph`, no `asyncio.gather` (phase 1 — sequential is fine).
  Each branch reads from / writes to `ArtemisRunState`.
- **Per-leaf input rendering.** A leaf's input is a typed Pydantic model
  built from the run state. This rendering lives in
  `workflow/render.py` so the runner stays linear:
  ```python
  def render_context_safeguard_input(s: ArtemisRunState) -> ContextSafeguardInput: ...
  def render_reasoner_input(s: ArtemisRunState) -> ReasonerInput: ...
  # ... one per leaf
  ```
  These are pure functions; test them directly.
- **State mutation.** After each leaf, copy the leaf's typed output
  fields onto `state`. Do this explicitly (no reflection); makes the
  data flow grep-able.
- **Char-limit precheck.** Implemented before `ContextSafeguard`. If
  `len(input_message) > character_limit`, set
  `intent_decision="CHAR_LIMIT_REJECTED"`, `utterance` to the templated
  message ("Your message is too long ({n}/{limit} characters)..."), and
  return immediately. No LLM calls. No frame in the trace for the leaves
  that didn't fire.
- **Retrieval fan-out.** `state.retrieval_specs` may have multiple
  specs. Call `await asyncio.gather(*(self.retrieval.retrieve(spec,
  workspace_id=...) for spec in specs))`. Order the results by spec_id
  for determinism.
- **Empty retrieval result.** If retrieval returns no hits, still call
  `EvidencePlanner` with the empty result; let the planner decide.
  (This is what selfserve does.)
- **Final step name.** Set `state.final_step` to the step_name of
  whichever leaf produced the final utterance. Used by
  `to_final_answer` to populate `ArtemisFinalAnswer.final_step`.
- **References on direct paths.** When the path is DIRECT_ANSWER /
  SAFEGUARD_REJECTED / CHAR_LIMIT_REJECTED, `references` stays None.
  RAG path sets it from the RAG talker's structured output.
- **Building.** `await runner.abuild()` traces every leaf and verifies
  type compatibility at build time. Operad's tracer constructs sentinel
  inputs via `model_construct()` — make sure every leaf's input schema
  has defaults that survive (you covered this in 1-2, but the
  integration test catches it).
- **Trace observer wiring.** In `run_with_trace`:
  ```python
  obs = WorkflowTraceObserver(entry_id=x.entry.compute_entry_id())
  registry.register(obs)
  try:
      out = await self(x)
  finally:
      registry.unregister(obs)
  trace = obs.trace.seal()
  return out.response, trace
  ```
- **`forward` vs `run_with_trace`.** `forward` is the operad-required
  method; `run_with_trace` is the public surface that installs the
  observer. Tests should use `run_with_trace`. Internal operad
  introspection (e.g. `tape()`) calls `__call__`, which goes through
  `forward`. Both work; pick one for the public API.

## Acceptance criteria

- [ ] `ArtemisRunner(selfserve_root=..., retrieval=...).abuild()` succeeds.
- [ ] All four paths execute correctly under cassette replay against
      checked-in fixtures:
      - DIRECT_ANSWER (e.g. greeting): `intent_decision="DIRECT_ANSWER"`,
        `final_step="conv_talker"`, no retrieval call.
      - RAG_NEEDED: `intent_decision="RAG_NEEDED"`,
        `final_step="rag_talker"`, retrieval called at least once.
      - SAFEGUARD_REJECTED:
        `intent_decision="SAFEGUARD_REJECTED"`,
        `final_step="safeguard_talker"`, no Reasoner call.
      - CHAR_LIMIT_REJECTED: `intent_decision="CHAR_LIMIT_REJECTED"`,
        no LLM calls at all, deterministic message.
- [ ] `run_with_trace` returns `(answer, trace)` with `trace.frames`
      containing exactly the leaves that fired (no more, no less).
- [ ] Each `TraceFrame.step_name` matches the registry's step_name.
- [ ] Cassette replay is byte-stable: two runs of the same dataset
      entry produce equal `trace.trace_id` and equal answer text.
- [ ] Calling `runner` with `tape()` active produces a populated tape
      (smoke test for batch 4).
- [ ] No imports from `uthereal_*`.
- [ ] No `asyncio.gather` is used outside the retrieval fan-out (keep
      the runner readable).

## Tests

- `test_runner_builds`.
- `test_direct_answer_path` — fixture: greeting; assert state and trace.
- `test_rag_path` — fixture: factual question; assert retrieval called
  with each spec; assert references populated.
- `test_safeguard_rejected_path` — fixture: blatant out-of-scope.
- `test_safeguard_exit_path` — fixture: user explicitly leaves.
- `test_char_limit_rejected_path` — message > 10000 chars; assert no
  LLM calls (use a mock retrieval client that records calls).
- `test_replay_byte_stable` — two runs, equal `trace.trace_id`.
- `test_trace_step_names_match_registry`.
- `test_runner_under_tape_records_entries` — open `tape()`, run; assert
  `len(tape.entries) == len(trace.frames)`.
- `test_render_each_leaf_input_is_pure_function` — for each render
  function, same state → equal output.

## Fixtures

`tests/fixtures/runner/` contains four dataset entries + cassettes:

```
tests/fixtures/runner/
├── direct_answer/
│   ├── entry.json
│   └── cassettes/{llm,rag}/...
├── rag_needed/
├── safeguard_rejected/
└── char_limit_rejected/
```

To author the cassettes: run the runner once with `OPERAD_CASSETTE=record`
and `mode="record-missing"` for the retrieval client, against a real
deployment. Check the cassette files in. Tests run against them.

## References

- `selfserve/workflow.py` — the upstream workflow we mirror. Read
  closely; ignore the streaming/attachments/title bits.
- `apps/demos/triage_reply/run.py` — closest operad-native pattern for
  a small driver that builds an agent, runs it, prints results.
- `operad/agents/safeguard/pipeline.py::SafetyGuard` — operad's existing
  example of a `Router`-driven branching composition, for reference.
- `operad/runtime/trace.py` — operad's trace; we mirror but don't reuse.

## Notes

(Append discoveries here as you implement. In particular: any deviation
from `selfserve/workflow.py` you had to make and why.)
