# Langfuse deep-link wiring: integration test against an OTLP collector

## Goal
The README claims "the dashboard's run-detail page renders a 'View in Langfuse' link that resolves directly to the matching trace without any external mapping," and INVENTORY §13 promises `int(run_id, 16)` is the OTel `trace_id`. There is no integration test verifying any of this. Spin up an in-test OTLP collector (or in-memory exporter), run an agent, assert: (1) a span is exported with the expected `trace_id`, (2) the dashboard renders a deep-link with that exact `trace_id` in the URL, (3) `gen_ai.tool.*` attributes (from iter 2-5) are present.

## Context
- `operad/runtime/observers/otel.py` — span construction; `trace_id = int(run_id, 16)`.
- `apps/dashboard/operad_dashboard/app.py` — accepts `langfuse_url`; renders the deep-link in templates.
- `docker-compose.yml` — Langfuse stack; not needed for the test.
- This task depends on iteration 2-5 (tool-use OTel attributes) being merged.

## Scope

**In scope:**
- `tests/runtime/test_otel_langfuse.py` (new) — use `opentelemetry.sdk.trace.export.in_memory_span_exporter.InMemorySpanExporter` to capture spans. Run an agent; assert root span's `trace_id` matches `int(run_id, 16)`. Assert deep-link URL format (configurable via `langfuse_url` kwarg).
- `apps/dashboard/tests/test_langfuse_link.py` (new) — render the run-detail page via TestClient, assert the rendered HTML contains the correct deep-link URL.
- INVENTORY §13 (self-hosted Langfuse stack) — reference the test as the source of truth for the URL format.

**Out of scope:**
- Spinning up the actual Langfuse stack in-test. The deep-link format is a string contract; we don't need a real Langfuse to verify it.
- The OTLP exporter dispatch logic (lives in OTel SDK).
- Per-attribute tool-use coverage (already tested in iter 2-5).
- Anything outside `tests/runtime/` and `apps/dashboard/tests/`.

**Owned by sibling iter-4 tasks — do not modify:**
- `apps/studio/`, `apps/demos/agent_evolution/`, `Makefile`, `scripts/`, `examples/benchmark/`, `operad/algorithms/sweep.py`, `apps/dashboard/operad_dashboard/routes/sweep.py` (4-6 owns), `apps/dashboard/operad_dashboard/contracts.py` (4-2 owns).

## Implementation hints
- The InMemorySpanExporter is the standard way to test OTel emitters; no need to invent an HTTP fake.
- The deep-link URL format from INVENTORY: `{langfuse_url}/trace/{run_id}`. If your test reveals the actual rendered link uses a different format, treat that as a contract bug to fix in the dashboard, not a test problem.
- For the dashboard test, render the template via Jinja directly if `TestClient` adds too much overhead; either is fine.

## Acceptance
- OTel-side test passes: trace_id match, attribute presence.
- Dashboard-side test passes: deep-link URL exact-match.
- Failure modes documented: if `langfuse_url` is missing, the link should be omitted (not broken).
