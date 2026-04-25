# Tool-use observability: `gen_ai.tool.*` span attributes

## Goal
`OtelObserver` already emits `gen_ai.system`, `gen_ai.request.model`, and `gen_ai.usage.*` per the OpenTelemetry GenAI semantic conventions. Tool calls — the most operationally interesting events in an agent run — get no dedicated attributes. Langfuse and other LLM-aware backends render them poorly because of this. Add `gen_ai.tool.name`, `gen_ai.tool.call.id`, and structured-but-bounded `gen_ai.tool.arguments` / `gen_ai.tool.result` attributes for each tool invocation under `ToolUser`.

## Context
- `operad/runtime/observers/otel.py` — span construction.
- `operad/agents/reasoning/components/tool_user.py` — tool dispatch; emits `AgentEvent`s on tool entry/exit.
- OTel GenAI conventions: <https://opentelemetry.io/docs/specs/semconv/gen-ai/> (read the latest "tool" attribute set; the spec evolves — pick the current set).

## Scope

**In scope:**
- `operad/runtime/observers/otel.py` — recognize tool-call events and attach the `gen_ai.tool.*` attributes. Truncate arguments/result strings to a bounded length (configurable, default 4 KB).
- `operad/agents/reasoning/components/tool_user.py` — make sure the events emitted carry enough payload (tool name, call id, args dict, result dict) for the observer to populate the attributes. If the events already carry it, just confirm and add tests.
- `operad/runtime/events.py` (or wherever `AgentEvent` is defined) — only add fields if strictly required for the tool payload; do not refactor existing events.
- Tests under `tests/runtime/` that intercept the OTLP exporter (use `opentelemetry.sdk.trace.export.in_memory_span_exporter.InMemorySpanExporter`) and assert the attribute set on a tool-call span.

**Out of scope:**
- Adding new tool kinds.
- Wiring Langfuse-specific attributes (the `gen_ai.*` set is enough).
- Touching the dashboard's tool rendering (separate UI work, not in this iteration).

**Owned by sibling iter-2 tasks — do not modify:**
- `operad/core/*`, `operad/train/trainer.py`, `operad/train/callbacks.py`, `operad/train/losses_hf.py`, `operad/optim/*`.

## Implementation hints
- Confirm the latest GenAI semconv attribute names and stability levels before naming things. Anything not yet stable goes behind a `gen_ai.tool.experimental_*` or similar.
- For args/result truncation: prefer JSON canonicalization (lean on the canonicalizer landed in iteration 1's hash-stability task) so the attribute is comparable across runs.
- The OTel SDK accepts attribute values up to certain limits; respect the SDK's `max_attribute_length` config.

## Acceptance
- New OTLP attribute test passes.
- Existing OTel tests pass.
- Attribute names match current GenAI semconv (cite the spec version in the docstring).
