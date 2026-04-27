# Dashboard Agent View — Audit Report

**Run tested**: `examples/01_agent.py` with Gemini 2.5 Flash backend  
**Dashboard**: `http://127.0.0.1:7860` (sydney-v2 workspace, same commit as da-nang-v2)  
**Run ID sampled**: `a252bcaf3b214754b71dd6f5f9e5eadf` (research_analyst, Sequential composite, 52 nodes)  

---

## CRITICAL — App-crashing bugs

### 1. Expanding a composite node in the Graph crashes the entire app

**Repro**: Graph tab → click "PARALLEL … 3 children · click to expand"  
**Error**: `TypeError: Cannot set properties of undefined (setting 'rank')`  
**Stack**: Inside `dagre.layout(g)` in `agent-flow-layout.ts:154`

**Root cause**: `layoutAgentFlow` uses a dagre *compound* graph. When `research_analyst.stage_1` (PARALLEL) is expanded, its children (`biology`, `policy`, `economic`) are added as compound children via `g.setParent(child, parent)`. The original edge set contains edges **from the parent to its compound children** (e.g. `research_analyst.stage_1 → research_analyst.stage_1.biology`). Dagre's compound layout algorithm cannot handle edges between a compound parent and its own children — it crashes trying to set `rank` on an undefined internal node structure.

**Files**: `apps/frontend/src/components/agent-view/graph/agent-flow-layout.ts`

**Fix**: In the `remappedEdges` loop (around line 139–152), skip any edge where one endpoint is a dagre-parent of the other:

```ts
// After remapping, skip parent→child compound edges
if (g.hasNode(a) && g.parent(b) === a) continue;
if (g.hasNode(b) && g.parent(a) === b) continue;
```

Or equivalently, before calling `g.setEdge`, check if either node is the compound parent of the other.

### 2. No error boundary around the Graph tab

After the crash, React Router's default error page is shown with raw stack traces (no custom styling, no "back" button that works). The error message mentions "Hey developer 👋 You can provide a way better UX than this when your app throws errors by providing your own `ErrorBoundary` or `errorElement`".

**Fix**: Add `errorElement` prop to the `/runs/:runId/graph` route in `apps/frontend/src/dashboard/routes.tsx`. Also wrap `AgentFlowGraph` in a per-component `<ErrorBoundary>` fallback so a layout crash doesn't blow up the entire route.

---

## HIGH — Major functionality broken

### 3. Clicking a leaf node opens the inspector but shows the empty placeholder

**Repro**: Graph tab → click on "Planner" or "Reasoner" node card → split pane opens → shows "Select a node or edge to inspect."

**Root cause** (two-part):

**Part A** (selection kind mismatch): In `agent-flow-graph.tsx` (line ~175), leaf nodes call:

```ts
onSelect: () => sel ? clearSelection() : setSelection({ kind: "node", nodeKey: n.path })
```

But in `InspectorShell.tsx` (line ~50), the `"node"` branch looks up `ioGraph.nodes.find(n => n.key === selection.nodeKey)`. The `ioGraph` is built by `adaptAgentGraphForInspector()` in `graph-page.tsx` which **always sets `nodes: []`** — all agents (leaf and composite) are in `ioGraph.edges`. So `meta` is always `null` for leaf nodes, showing the placeholder.

**Part B** (UX): On first click, the split pane *opens* (because `selection !== null`), but the inspector shows nothing. On second click, `sel = true` so `clearSelection()` fires and the pane *closes*. The user can never see inspector content for leaf nodes.

**Fix**: Change `onSelect` for leaf nodes in `agent-flow-graph.tsx` to use the same kind as composites:

```ts
onSelect: () => sel ? clearSelection() : setSelection({ kind: "edge", agentPath: n.path })
```

This routes leaf nodes through `ioGraph.edges.find(e => e.agent_path === selection.agentPath)` where they actually live.

### 4. Token counts are always 0/0 for Gemini backend

**All invocations** (leaf and composite, run and agent level) report `prompt_tokens: 0, completion_tokens: 0`. Confirmed via direct API calls to `/runs/{id}/invocations` and `/runs/{id}/agent/{path}/invocations`.

Downstream effects:

- Invocation banner shows **TOKENS 0 / 0 in / out**
- Run list header shows **TOKENS 0**
- Cost tab shows **$0.00** total cost (cost is also `null`)
- Reproducibility block shows `model` hash as `—` for the composite (the model hash IS computed for leaf agents: `df62facf54939172`, but the composite's invocation has `hash_model: ""`)

**Root cause**: The Strands/Gemini runner does not emit token usage in the `OperadOutput` envelope. This is a backend (operad core) issue, not a dashboard-UI issue.

**Dashboard mitigation** (independent of fixing the backend): When `prompt_tokens + completion_tokens === 0` AND `cost === null`, show a small indicator like "(token tracking unavailable for this backend)" instead of raw zeros, to avoid user confusion.

### 5. `/runs/by-hash` returns HTTP 500 (intermittent)

**Repro**: On the first tested run (`94a1c8cb...`), the Sister runs block showed "endpoint unavailable" because `/runs/by-hash?hash_content=f895c4b8161fa5fb` returned 500. On a subsequent run it worked (200 with matches).

**Root cause** (likely): `_latest_root_hash_content()` in `agent_routes.py:928` walks `info.events` in reverse. If `info.events` contains an event where `metadata` is not a dict or is missing `hash_content`, the function returns `None` and the run is skipped — that's fine. But if `info.summary()` itself raises (e.g., the `RunInfo` object is in a partially-constructed state when the request hits), the 500 propagates.

**Fix**: Wrap `info.summary()` call at line 902 in a try/except, and add exception handling around `_latest_root_hash_content()` call.

---

## MEDIUM — UX and data issues

### 6. Configuration block shows "no configuration captured" for composite agents

Composite agents (`Sequential`, `Parallel`) have `config: None` in their meta response (they don't own a `Configuration` object — they delegate to leaf children). The UI shows "no configuration captured" with no explanation, which reads as a data loss bug.

**Fix**: Show "configuration is set per-leaf agent" (or hide the block entirely) when `kind === "composite"` and config is null.

### 7. Identity block shows empty ROLE and TASK labels for composite agents

Composites have no `role` or `task`. The Identity block still renders the `ROLE:` and `TASK:` labels with empty values. This looks like missing data.

**File**: `apps/frontend/src/components/agent-view/overview/identity-block.tsx` (inferred)  
**Fix**: Conditionally render these rows only when the values are non-empty.

### 8. Output values truncated with no way to see full text

The invocation banner shows truncated output values (`"Urgent policy reforms are critical to add…"`). Clicking the output card collapses it (toggles the section). There is no "expand" / "show full" affordance for long field values.

**Fix**: Add a "show more" toggle on each field value when the string is truncated. Alternatively, make the field value clickable to open a modal/drawer with the full content.

### 9. Cost tab requires 2+ invocations but latency is available from 1

The `CostLatencyBlock` component (`cost-latency-block.tsx:51`) shows "needs 2+ invocations" and disables the entire block with only 1 invocation. But avg latency and the single data point are perfectly meaningful with 1 run.

**Fix**: Show avg latency and total tokens with 1 invocation. Reserve the sparklines and p95 for 2+ invocations.

### 10. Reproducibility block counts `—` hashes as "stable"

The block header shows "6/6 stable across 1 invocation" but two of the six hashes (`model` and `config`) display `—` (null). A composite doesn't have a model hash or config hash at the root level — those are leaf-level. The "stable" count includes these empty values, inflating the score.

**Fix**: Exclude `null`/`—` hashes from both the numerator and denominator of the stability count. Optionally hide rows with `—` for composite agents, or label them "N/A (composite)".

### 11. Duplicate API requests on run detail load

On navigating to a run detail page, the network log shows:

- `/runs/{runId}/summary` fetched **2×** within 6ms
- `/runs/{runId}/invocations` fetched **2×** within 6ms

**Root cause**: Two components on the overview page use the same data but with slightly different React Query keys, or the same component mounts twice (StrictMode double-invoke would not cause duplicate network requests). Likely the overview JSON-render layout and the React component both fetch independently.

**Fix**: Audit `useRunSummary` and `useRunInvocations` hooks for key consistency. Ensure all overview blocks share the same cached query result.

### 12. Langfuse links point to `localhost:7000` with no reachability check

All Langfuse deep-links (`langfuse` header badge, "Open in Langfuse" button, per-invocation Langfuse links, inspector Langfuse tab) point to `http://localhost:7000/...`.

The inspector Langfuse tab renders an `<iframe src="http://localhost:7000/traces?search=…">` unconditionally. If Langfuse is not running (e.g. docker stack not started, or port conflict as in this test), the iframe just shows a blank page or browser error — no feedback.

**Fix**: 

- The Langfuse tab should check `langfuse_search_url` is reachable before showing the iframe (or at least show a fallback "Langfuse is not accessible at …" message with an "open in new tab" button).
- Consider checking during dashboard startup whether Langfuse is reachable and surfacing it in the header.

### 13. Graph tab: node/control layout breaks when split pane opens

When the inspector split pane opens (by clicking any node), the graph canvas is resized to ~50% width. Two issues:

1. The rightmost node (Reasoner) gets clipped outside the visible canvas area.
2. The expand/collapse all + mermaid controls shift from top-right to a different position.

**Fix**: Call ReactFlow's `fitView()` when the split pane opens/closes (listen to viewport resize). Pin the graph controls to the canvas container, not the page.

### 14. Graph tab: `output_schema` hash shows orange dot with only 1 invocation

In the Reproducibility block, the `output schema` row shows an orange/warning dot with 1 invocation. With only 1 invocation, stability cannot be established — the UI should show a neutral state (gray dot) rather than implying instability.

**File**: reproducibility block component  
**Fix**: Only show orange (drifted) indicator when there are 2+ invocations AND the value has changed. With 0–1 invocations, show gray.

### 15. "Edit & run" inspector tab: invoke endpoint disabled, no UI indication

The "Edit & run" tab (`TabExperiment`) renders a form with role/task/rules fields and an input JSON editor. When submitted, the backend returns `{"error": "experiment_disabled"}`. There is no label in the UI indicating that this feature requires a specific server flag to enable.

**Fix**: Check `experiment_disabled` on page load (perhaps via a `/api/manifest` or `/api/capabilities` endpoint), and render the tab in a disabled/grayed-out state with a "Requires `--enable-experiments` flag" tooltip, rather than letting users fill out the form only to get an error.

### 16. `/agent/{path}/values` endpoint is missing (404)

`GET /runs/{runId}/agent/{agentPath}/values?attr=input&side=in` returns 404. This endpoint is listed in the frontend API client (`dashboard.ts`) but not implemented in the backend.

**Impact**: Unknown — search the frontend for where `dashboardApi.agentValues(...)` is called and verify the feature is entirely unused or broken.

### 17. `/agent/{path}/diff` endpoint is missing (404)

`GET /runs/{runId}/agent/{agentPath}/diff?from={invId}&to={invId}` returns 404. Used by the invocation comparison feature in `InvocationsList`.

**Fix**: Implement the diff endpoint in `agent_routes.py`, or remove the comparison UI if it's not intended to ship.

---

## LOW — Minor polish

### 18. Run list sidebar: "events=104" metadata is cryptic

The sidebar entry for each run shows `events=104` as metadata. This is an internal counter that means little to a user. Consider replacing with a human-friendly label: "104 events" → "ran 35s ago · 14 leaf invocations" or similar.

### 19. AgentChrome header: script path truncated with no tooltip

The header shows `examples/01_agent.py` truncated in some viewports with no tooltip showing the full path. Add a `title` attribute or `<Tooltip>` component.

### 20. Breadcrumb "runs /" is clickable but just navigates home — expected, but aria label missing

The `runs /` breadcrumb link has no accessible label. Add `aria-label="all runs"`.

---

## Summary table


| #   | Area                                            | Severity | Status         |
| --- | ----------------------------------------------- | -------- | -------------- |
| 1   | Graph: expand composite crashes app             | CRITICAL | Open           |
| 2   | Graph: no error boundary                        | CRITICAL | Open           |
| 3   | Graph: leaf node click → empty inspector        | HIGH     | Open           |
| 4   | Tokens always 0/0 for Gemini                    | HIGH     | Open (backend) |
| 5   | `/runs/by-hash` 500 (intermittent)              | HIGH     | Open           |
| 6   | Config block misleading for composites          | MEDIUM   | Open           |
| 7   | Empty ROLE/TASK labels for composites           | MEDIUM   | Open           |
| 8   | Output values not expandable                    | MEDIUM   | Open           |
| 9   | Cost tab requires 2+ invocations                | MEDIUM   | Open           |
| 10  | Reproducibility counts `—` as stable            | MEDIUM   | Open           |
| 11  | Duplicate API requests on load                  | MEDIUM   | Open           |
| 12  | Langfuse iframe with no reachability check      | MEDIUM   | Open           |
| 13  | Graph canvas not re-fit on split pane           | MEDIUM   | Open           |
| 14  | Orange dot on output_schema with 1 invocation   | MEDIUM   | Open           |
| 15  | Edit & run tab: no indication endpoint disabled | MEDIUM   | Open           |
| 16  | `/agent/{path}/values` → 404                    | MEDIUM   | Open           |
| 17  | `/agent/{path}/diff` → 404                      | MEDIUM   | Open           |
| 18  | Sidebar "events=N" cryptic                      | LOW      | Open           |
| 19  | Script path no tooltip                          | LOW      | Open           |
| 20  | Breadcrumb missing aria-label                   | LOW      | Open           |


