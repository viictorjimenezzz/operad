# Decouple `Agent` from `strands.Agent` (inheritance → composition)

## Goal
`Agent` extends `strands.Agent` today. Tool calls/MCP/structured-output come for free, but every Strands API change forces an operad release, the state-shadowing dance in `_init_strands` (`operad/core/agent.py:422-429`) is a downstream symptom, and there's no path to swap the runtime substrate (e.g. LiteLLM, raw httpx, a future first-party Strands replacement). Refactor to composition: `self._strands_runner: StrandsRunner` instead of `class Agent(strands.Agent)`.

This is the single highest-impact architectural change in the plan. Treat it accordingly.

## Context
- `operad/core/agent.py` — inheritance and the state-shadowing hack live here.
- `operad/core/build.py` — uses some `strands.Agent` machinery via `super().__init__` calls.
- `operad/core/models.py` — backend dispatch; some adapters reach into Strands shapes.
- VISION §4 names Strands as the substrate; the framing remains true under composition — operad still uses Strands for the inherited behaviors. The change is structural, not philosophical.

## Scope

**In scope:**
- `operad/core/agent.py` — replace `class Agent(strands.Agent)` with composition. Define a thin `StrandsRunner` adapter (in a new `operad/core/_strands_runner.py` or similar) that exposes only what operad needs from Strands: `invoke(messages, tools, structured_output_schema, sampling) -> response`. Construct one inside `Agent` lazily in `build()` (NOT `__init__`, per the no-side-effects rule from iteration 2-3).
- `operad/core/build.py` — replace `super().__init__()` Strands calls with calls into the runner.
- `operad/core/models.py` — anything that reaches into Strands shapes (config translation, tool-call massaging) goes through the runner adapter.
- `operad/core/_strands_runner.py` (new) — the adapter. Keep it small; this is the seam.
- Tests under `tests/core/` covering: existing agent behavior unchanged (full pre-existing test suite still passes), runner can be substituted via a `runner_factory` kwarg for testing.
- Update `INVENTORY.md` §4 (build), §10 (configuration) to mention the seam.
- Update `VISION.md` §4 — keep the narrative; just clarify that the relationship is "uses" not "extends."

**Out of scope:**
- Implementing a non-Strands runner. The seam is what matters; alternative runners are future work.
- Changing the `Agent` public API (constructor kwargs, methods on the class). Existing user code must continue to work.
- Anything in `operad/optim/`, `operad/train/`, `operad/runtime/`, `operad/agents/` *unless* they directly reach into Strands attributes (they shouldn't, but verify).

**Owned by sibling iter-5 tasks — do not modify:**
- `operad/utils/cassettes.py`, `operad/train/trainer.py`.

## Implementation hints
- Inheritance leaks more than people think: `agent.state`, `agent.conversation`, `agent.tools`, etc. all come from Strands. Audit every `self.<attr>` reference in `Agent` to identify which need explicit forwarding.
- Don't create a sprawling adapter — `StrandsRunner` should be ~150 lines. If it grows past 300, you're either re-implementing Strands or papering over a leaky abstraction; stop and reconsider.
- `freeze`/`thaw` must still work. The frozen artifact contains a hash for the Strands runner's effective state; bump it (or version the format) so old frozen files explicitly fail rather than silently misbehave.
- Backward compatibility: subclasses that previously called `super().__init__(...)` and passed Strands kwargs will break. Document this in the changelog and provide a migration helper.
- Tool calls: the trickiest path. Make sure `ToolUser` continues to work end-to-end with the same OTel span attributes from iteration 2-5.

## Acceptance
- Existing `tests/` suite passes unchanged (the public API didn't change).
- `tests/core/test_strands_runner.py` (new) covers the seam: inject a fake runner, assert the agent uses it.
- `_init_strands` and the state-shadowing hack are gone.
- VISION/INVENTORY updated to reflect composition framing.
- A migration note in `INVENTORY.md` §1 for any subclass authors.
