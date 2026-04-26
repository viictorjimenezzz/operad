# 2-3 Side drawer shell

## Scope

Build the right-side resizable drawer that hosts every "open in
drawer" action from the popups in 2-2 and the metadata table in
2-1. This stream ships the **shell + state machine + registry**;
content streams (3-1, 3-2, 3-3) fill it.

### You own

- `apps/frontend/src/components/agent-view/drawer/`
  - `side-drawer.tsx` — the right-hand resizable sliding panel.
  - `drawer-host.tsx` — chooses which view to render based on
    `useUIStore.drawer.kind`, with stub renderers per kind.
  - `drawer-registry.ts` — `kind -> Component` map. Designed so
    iter-3 streams add entries without touching this file (use
    a per-view registration pattern: each view's `index.ts`
    self-registers, or expose a `registerDrawerView(kind, fn)`
    function).
  - `views/_stub.tsx` — placeholder rendered until iter-3 lands a
    real view. Shows kind + payload as a JSON dump so devs can
    sanity-check.
  - `registry.tsx` + `index.ts`.
- `apps/frontend/src/components/agent-view/registry.tsx` — wire
  the drawer's component into the agent-view spread.

### Depends on (iter-1 contracts)

- `useUIStore.drawer`, `openDrawer`, `closeDrawer`, `drawerWidth`,
  `setDrawerWidth` (1-1 delivers).

### Out of scope

- Drawer view content — Langfuse iframe (3-1), event timeline
  filter (3-1), prompt diff (3-2), value timeline (3-3). Stub
  them.
- The graph + popups (2-2) and metadata (2-1) — they call
  `openDrawer` and trust the drawer shows up.

---

## Vision

The drawer is the dashboard's "context panel" — the place that
flips between deep views without taking the user to a new page.
Think VS Code's right panel or the Stripe dashboard's drawer
when you click an event.

Behavior:

- **Open**: slides in from the right, animates 200ms ease-out.
  Default width 480px (configurable), persisted to localStorage.
- **Resize**: drag the left edge of the drawer to resize, with
  min 320px and max ~60% of viewport. Width persists.
- **Close**: ESC, click on backdrop (no — drawer is *not* modal;
  it's docked. Use an explicit X button), or call
  `closeDrawer()`.
- **Header**: title that reflects the kind ("Langfuse trace",
  "Filtered events for `Root.stage_0`", "Prompt diff for
  `Reasoner`", "Values of `question` (input)"). Sub-header has
  the `agent_path` if relevant. Right-aligned: collapse-to-rail
  button and close button.
- **Content area**: scrollable. Each view owns its own scroll.
- **Sticky footer** (optional): per-view actions (e.g. "open in
  new tab" for Langfuse).

The drawer **doesn't push** the main content; it docks on top
with a thin shadow. The main page can still be panned (the graph)
behind it. Reasoning: the user is comparing graph-state to
context-state side by side; the graph staying put is the point.

---

## State machine

The drawer is fully driven by `useUIStore.drawer`:

```ts
interface DrawerState {
  kind: "langfuse" | "events" | "prompts" | "values" | null;
  payload: { agentPath?: string; attr?: string; side?: "in" | "out"; [k: string]: unknown };
}
```

Open/close transitions are atomic. Calling `openDrawer(kind,
payload)` while another view is open swaps the view (no
intermediate close). When closed, the panel slides off-screen but
keeps the last-rendered content unmounted (don't preserve scroll
state across opens — clean slate).

If `kind` doesn't have a registered view, render `_stub.tsx`.

### Registry pattern

Sibling streams must add their views without conflicts:

```ts
// drawer-registry.ts
type DrawerView = (props: { payload: DrawerPayload; runId: string }) => JSX.Element;

const registry = new Map<DrawerKind, DrawerView>();
export function registerDrawerView(kind: DrawerKind, view: DrawerView): void {
  registry.set(kind, view);
}
export function getDrawerView(kind: DrawerKind): DrawerView | null {
  return registry.get(kind) ?? null;
}
```

Each iter-3 stream's `index.ts` calls `registerDrawerView` at
module load (idempotent). Document this in `index.ts` as a
comment so future view authors copy the pattern.

Avoid a global registry that loses entries on HMR; tie
registration to module-load and verify it survives Vite reloads.

---

## Implementation pointers

- Use Radix's `Dialog` or `Sheet` (shadcn) primitives, OR roll a
  simple slide-in with framer-motion. The drawer is non-modal so
  Radix `Sheet` (which makes it modal) needs to be configured
  carefully — you may want a custom impl. Pick what gives you the
  cleanest non-modal UX.
- Resize handle: a thin draggable bar on the left edge with a
  cursor-col-resize hint. Clamp width on resize. Save to
  localStorage on drop.
- The drawer should render lazily: don't even mount the content
  component until `kind != null` for the first time.
- The drawer's outer container should be position:fixed (or use
  a portal) so it overlays the page reliably.
- Make sure the page layout (2-1's `agents.json`) reserves
  *zero* horizontal space for the drawer — it floats on top of
  the existing content.

---

## Polish targets

- **Keyboard**: ESC closes, Cmd+\ also collapses the runs sidebar
  for full-bleed comparison views.
- **Focus**: when opening, focus moves to the drawer header X
  button. When closing, focus returns to the trigger element.
- **Backdrop tap**: NO modal backdrop. Don't dim the page.
- **Animation**: prefer transform-based slide for performance. No
  layout thrash on resize.
- **Per-view title prop**: give each registered view a
  `getTitle(payload, runId)` so the drawer header can render the
  right thing without the view having to render its own title.

---

## Be creative

- Multi-drawer? Probably not for v1, but if a "compare two
  invocations" use case is obvious, plan for it (a "split"
  toggle that puts two views side by side).
- A breadcrumb-style "back" history so the user can navigate
  between views (langfuse → prompt diff → langfuse) is a nice
  touch.
- The drawer's header should make it easy to see *what* you're
  looking at and *for which agent path* — the path is the
  context that ties the view to the graph.

---

## Verification

```bash
pnpm -C apps/frontend test
pnpm -C apps/frontend typecheck
make dashboard && make dev-frontend
# Confirm:
# - Click any "open drawer" trigger (e.g. invocations table row, type-node
#   "values" link). Drawer slides in. Title reflects payload.
# - Drag left edge to resize. Reload page. Width persisted.
# - X button closes. ESC closes.
# - Switching kinds (open kind A, then click a kind-B trigger) animates
#   smoothly without unmount-flash.
# - Stub view shows raw payload as JSON.
```
