# 2-2 Interactive graph: React Flow with inverted semantics

## Scope

Build the centerpiece of the agent view: a fully interactive graph
where input/output **types are nodes** and **agents are edges**.
Pan, zoom, minimap, click-to-expand. This is the most ambitious
component in the rewrite — get it right.

### You own

- `apps/frontend/src/components/agent-view/graph/`
  - `interactive-graph.tsx` — top-level wrapper + React Flow setup
  - `io-type-node.tsx` — custom React Flow node
  - `agent-edge.tsx` — custom React Flow edge
  - `io-node-popup.tsx` — popup for I/O type nodes
  - `agent-edge-popup.tsx` — popup for agent edges
  - `field-row.tsx` — one-row renderer for an attribute
  - `config-section.tsx` — collapsible config-attributes view
  - `composite-grouping.ts` — utility that derives visual grouping
    from `composite_path`
  - `layout.ts` — static or auto-layout (e.g. dagre / elkjs)
  - `registry.tsx` + `index.ts`
- `package.json` — add `@xyflow/react` (and a layout engine, e.g.
  `dagre` or `@dagrejs/dagre`).

### Depends on (iter-1 contracts)

- `GET /runs/{id}/io_graph` (1-3) returning the inverted-graph
  shape (1-2).
- `useUIStore.openDrawer({kind, payload})` (1-1) — every
  link-style action in the popups calls this.
- The component-folder convention (1-1).

### Out of scope

- Drawer shell + content (2-3, 3-x).
- The `forward_in/out` indicator badges and trainable-params panel
  details — those are iter-4 enrichments to your popups; leave
  hooks (props or context) so they can land cleanly later.

---

## Vision

The current Mermaid render is read-only and wrong-shaped: agents
as nodes, types as edge labels. We're flipping it.

A user lands on the agent view and sees a flowchart where:

- **Rounded boxes** are I/O types (`Question`, `Reflection`,
  `Answer`). Each box has the class name in big text and a small
  pill showing how many fields it carries.
- **Arrows** are agents. The arrow label shows the agent's class
  name (or path tail). Color/thickness optional but tasteful.
- **Pan, zoom, minimap, fit-to-view** controls in a corner.
  Cmd-scroll to zoom, drag to pan.

Click an I/O node:

- Opens an **inline popover** anchored to the node (NOT the side
  drawer). The popover lists every field as
  `<name> (<type>): <description>` with an `S` or `U` chip on the
  right (system vs user-turn field — see operad's
  `is_system_field`).
- Each field row has a small "values" link → calls
  `openDrawer({kind: "values", payload: {agentPath, attr,
  side}})`. The drawer (2-3 + 3-3) handles rendering.

Click an agent edge:

- Opens an inline popover anchored along the edge.
- Three sections, each collapsible:
  1. **Configuration** — when toggled open, render every
     `Configuration` field at every nesting depth (sampling.*,
     resilience.*, io.*, runtime.extra.*) as a key/value grid.
     Surface `model`, `backend`, `temperature` at the top level
     even when collapsed.
  2. **Links** — three icon-buttons:
     - "Langfuse" → `openDrawer({kind: "langfuse", payload:
       {agentPath}})`.
     - "Events"   → `openDrawer({kind: "events", payload:
       {agentPath}})`.
     - "Prompt"   → `openDrawer({kind: "prompts", payload:
       {agentPath}})`.
  3. **At-a-glance metrics** — invocation count, average latency,
     hash_content (chip).

Composites get **grouping**, not nodes:

- Derive groups from `edges[i].composite_path`. Edges sharing a
  composite get a subtle bounding box (React Flow `parentNode` or
  a manual `<rect>` overlay) with the composite class name in the
  corner.
- Groups can be collapsed (replaced by a single super-edge
  labelled with the composite class name).

---

## Implementation pointers

- React Flow: use the `@xyflow/react` (v12+) package. Examples
  (`createNodeTypes`, `createEdgeTypes`) are in their docs. The
  custom-node and custom-edge demos are the right starting point.
- Auto-layout: an inverted-graph needs left-to-right layered
  layout. `dagre` is the simplest fit; `elkjs` is nicer for
  composite groups but heavier. Pick whichever you can ship by
  end of iteration. If you hit performance issues, memoise the
  layout call by the `io_graph` hash.
- Popovers: use Radix's `Popover` primitive (already a transitive
  dep via shadcn) — anchored, keyboard-accessible, click-outside
  closes.
- The popovers are *separate* from the side drawer. The side
  drawer holds long-form content; popovers are quick hovers /
  clicks attached to the graph element. Don't conflate.
- Field type labels come from `to_io_graph`'s walker (1-2). Trust
  them; don't try to re-derive types client-side.
- For the configuration view, fetch
  `/runs/{id}/agent/{path}/meta` lazily on first edge click and
  cache it.
- Edge labels overlap easily with auto-layout. Use React Flow's
  `BezierEdge` with a `MarkerEnd`, label centered, and let
  collisions happen — users can pan.

---

## Polish targets

- **Selected edge highlight**: dim non-selected edges, fade
  non-incident type nodes.
- **Click-while-other-popover-open**: close the previous popover
  cleanly.
- **Keyboard nav**: tab through nodes, enter to expand.
- **Screen reader**: each node and edge has an aria-label
  describing its role + identity.
- **Hover preview**: hovering an edge for >300ms shows a tooltip
  with `class_name`, `path`, and a one-line config summary.
- **Empty state**: graph not ready yet → centered message
  "waiting for first invocation".

---

## Be creative

- The visual language for "S" (system field) vs "U" (user field)
  is your call. A small letter chip is the floor. A subtle border
  treatment on the parent type node ("this type has 2 system
  fields") would be richer.
- Composite collapse/expand is the place where this view earns
  its keep on big graphs. A single ReAct or AutoResearcher agent
  spawns a complex sub-tree; users will want to fold the inner
  loop into one super-edge labelled "ReAct".
- When the same input type fans out to N agents (Parallel) and
  later fans back in to a combine step, the rendering should
  *feel* like a fork-join. React Flow's edge routing won't do this
  for free — consider whether you need a custom path for it.
- For `Switch`, the router edge feels different from the branch
  edges. Maybe a dotted style? Or a small label on the input node
  showing the live-router output?
- This is a chance to show off. If you have time, add a "highlight
  flow for invocation N" overlay that animates a token traveling
  along the chosen edges as the user steps through invocations.
  That kind of feature is what makes the dashboard feel alive.

---

## Verification

```bash
pnpm -C apps/frontend add @xyflow/react dagre
pnpm -C apps/frontend test
pnpm -C apps/frontend typecheck
make dashboard && make dev-frontend
# Open a non-algorithm run with a multi-agent graph. Confirm:
# - the graph renders inverted (types are nodes, agents are arrows)
# - pan/zoom work; minimap visible
# - click a type node → inline field popover; "values" calls openDrawer
# - click an agent edge → inline popover; toggling Configuration expands; "Langfuse" calls openDrawer
# - composite grouping is visible and collapsible
```
