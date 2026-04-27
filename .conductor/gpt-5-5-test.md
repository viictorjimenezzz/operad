# Agent View Test Report

Date: 2026-04-27
Workspace: `/Users/viictorjimenezzz/conductor/workspaces/operad/sydney-v2`
Run tested: `94a1c8cb15114cb78bdde9c737d6087d`

## Scope

I tested the dashboard Agent view against `examples/01_agent.py` using the Gemini backend, focusing on the view shown for a live agent invocation. I did not change application code.

Assumptions:

- The relevant target is the built dashboard served at `http://127.0.0.1:7860`.
- `examples/01_agent.py` is representative because it exercises a root composite, parallel branches, nested `ReAct` composites, many leaf agents, typed IO schemas, prompts, invocation envelopes, trainable parameters, and Langfuse links.

## Commands Run

```bash
git branch -m test-agent-view-windows
make clean
make build-frontend
make rebuild
make dashboard
set -a; [ -f .env ] && . ./.env; set +a; \
  OPERAD_BACKEND=gemini uv run --extra otel --extra gemini \
  python examples/01_agent.py --dashboard --no-open
```

Notes:

- `make rebuild` failed because host port `7000` was already allocated for Langfuse. I continued with `make dashboard` in host mode, which is sufficient for the Agent view and HTTP attach ingestion.
- The first Gemini run failed because the virtualenv did not include the `gemini` extra. Rerunning with `--extra gemini` fixed it.

## Run Result

The example completed successfully.

- Dashboard attached: yes
- Backend/model: `gemini` / `gemini-2.5-flash`
- Run state: `ended`
- Events: `52 start`, `52 end`, `104 total`
- Graph JSON: present
- Root invocation: present
- Root latency: about `35.9s`
- Root output rendered in Overview and Invocations

Playwright artifacts saved under `.context/`:

- `.context/agent-overview-94a1c8cb15114cb78bdde9c737d6087d.png`
- `.context/agent-graph-94a1c8cb15114cb78bdde9c737d6087d.png`
- `.context/agent-invocations-94a1c8cb15114cb78bdde9c737d6087d.png`
- `.context/direct-cost-94a1c8cb15114cb78bdde9c737d6087d.png`
- `.context/direct-train-94a1c8cb15114cb78bdde9c737d6087d.png`
- `.context/agent-view-check-94a1c8cb15114cb78bdde9c737d6087d.json`

## What Works

- Run list shows the agent run and links to `/runs/{run_id}`.
- Overview renders status, script, latency, input, output, identity, backend/model/renderer, examples, reproducibility, and latest invocation.
- Invocations tab renders the root invocation with input/output and hashes.
- Cost tab loads and shows the current single-invocation state: `Cost & latency needs 2+ invocations`.
- Train tab appears because trainable parameters are available and renders the parameter list.
- Graph tab initially renders a collapsed graph with `Planner`, collapsed `Parallel`, and final `Reasoner`.
- Representative leaf backend routes work:
  - `/runs/{run_id}/agent/research_analyst.stage_0/meta`
  - `/runs/{run_id}/agent/research_analyst.stage_0/invocations`
  - `/runs/{run_id}/agent/research_analyst.stage_0/events`
- Langfuse links are present and point at `http://localhost:7000/trace/{run_id}` in this environment.

## Issues Found

### 1. Overview triggers a backend 500 for sister runs

The Overview page calls:

```text
GET /runs/by-hash?hash_content=f895c4b8161fa5fb
```

It returns:

```text
500 Internal Server Error
AttributeError: 'RunRegistry' object has no attribute 'values'
```

Relevant code: `apps/dashboard/operad_dashboard/agent_routes.py:899`

The route assumes `obs.registry.values()`, but the current `RunRegistry` object is not dict-like. The UI survives and shows `Sister runs endpoint unavailable`, but this is a real backend bug.

Suggested fix:

- Use the `RunRegistry` public iterator/listing API instead of `.values()`.
- Add a dashboard test for `/runs/by-hash` with the live in-memory registry.

### 2. Graph “expand all composites” crashes the React route

Initial graph rendering works. Clicking the expand-all button crashes the route.

Console error:

```text
TypeError: Cannot set properties of undefined (setting 'rank')
```

This comes from Dagre layout after expanding all nested composites. After the crash, React Router renders its default error boundary and the graph disappears.

Relevant code:

- `apps/frontend/src/components/agent-view/graph/agent-flow-graph.tsx:55`
- `apps/frontend/src/components/agent-view/graph/agent-flow-layout.ts:104-154`

Likely cause:

- The expanded compound Dagre graph is getting an invalid parent/edge arrangement for this nested `Sequential -> Parallel -> ReAct -> Loop` graph. The observed agent graph has deep compounds and edges that cross composite boundaries; Dagre is fragile when compound parent relationships and inter-cluster edges are inconsistent.

Suggested fix:

- Add a fixture from this run’s `agent_graph` payload.
- Unit-test `layoutAgentFlow(... expanded=all composites ...)`.
- In layout, normalize cross-boundary edges so Dagre never receives invalid compound edges. At minimum, wrap `dagre.layout(g)` and fall back to collapsed graph rather than crashing the route.

### 3. Leaf inspector selection is wired to the wrong selection kind

Direct leaf APIs work, but the graph selection wiring prevents leaf nodes from opening the rich agent inspector.

Relevant code:

- `apps/frontend/src/components/agent-view/graph/agent-flow-graph.tsx:174-175`
- `apps/frontend/src/components/agent-view/graph/graph-page.tsx:62-77`

Problem:

- Leaf nodes call `setSelection({ kind: "node", nodeKey: n.path })`.
- `GraphPage` adapts `agent_graph` into an `IoGraphResponse` with `nodes: []`; all agent records are put into `edges`.
- `InspectorShell` only shows the agent tabs for `selection.kind === "edge"`.

Result:

- A leaf should open `Overview / Invocations / Prompts / Events / Edit & run / Langfuse`, but the selection shape points at an empty node list.

Suggested fix:

- For agent-flow cards, select agents with `setSelection({ kind: "edge", agentPath: n.path })`, or rename/refactor the store shape so agent selections are not represented as legacy IO edges.
- Add a component test that clicks `Planner` and asserts the inspector shows the six agent tabs.

### 4. Graph inspector work is blocked by issue 2

Because expand-all crashes, I could not reliably test nested branch leaves through the UI. The backend has the required metadata/invocation/event payloads for representative leaves, so this is primarily a frontend graph stability/selection problem.

## Prioritized Fix Plan

1. Fix `/runs/by-hash` to use the current registry API and add a route test.
2. Add the `01_agent.py` agent-graph payload as a frontend layout fixture.
3. Make `layoutAgentFlow` handle all-expanded nested composites without throwing.
4. Fix graph leaf selection so leaf cards open the agent inspector tabs.
5. Rerun the same Gemini example and repeat browser checks for Overview, Graph, Invocations, Cost, Train, and all inspector tabs.

