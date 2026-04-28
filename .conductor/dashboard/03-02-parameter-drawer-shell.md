# 03-02 Parameter drawer shell

**Branch**: `dashboard/parameter-drawer-shell`
**Wave**: Sequence 3, parallel batch
**Dependencies**: `01-02` (density tokens; `--drawer-width`)
**Estimated scope**: small

## Goal

Build the right-side sliding drawer that hosts the parameter
evolution view. URL-driven so links are shareable. Accepts the
per-type view as a child render prop. Brief `04-01` will wire the
drawer to the StructureTree; per-type views (briefs `03-03`, `03-04`,
`03-05`) plug in via the render prop.

## Why this exists

- §9 of `00-contracts.md` defines the URL-driven drawer pattern.
- The user explicitly chose "drawer" over "full-page evolution view"
  in the design discussion.
- A reusable shell prevents per-algorithm briefs from each rolling
  their own drawer.

## Files to touch

- New: `apps/frontend/src/components/agent-view/structure/parameter-drawer.tsx` —
  the shell.
- New: `apps/frontend/src/components/agent-view/structure/use-parameter-drawer.ts` —
  hook returning `{ paramPath, stepIndex, open, close, selectStep }`.
- New: `apps/frontend/src/components/agent-view/structure/parameter-drawer.test.tsx`.

## Contract reference

`00-contracts.md` §4 (drawer width tokens), §9 (URL state), §13
(folder convention).

## Implementation steps

### Step 1 — Hook

```ts
export function useParameterDrawer(): {
  paramPath: string | null;
  stepIndex: number | null;
  open: (paramPath: string, step?: number) => void;
  close: () => void;
  selectStep: (step: number) => void;
} {
  const [param, setParam] = useUrlState("param");
  const [stepRaw, setStep] = useUrlState("step");
  const stepIndex = stepRaw == null ? null : Number(stepRaw);
  const validStep = Number.isInteger(stepIndex) ? stepIndex : null;
  return {
    paramPath: param,
    stepIndex: validStep,
    open: (p, s) => { setParam(p); if (s != null) setStep(String(s)); },
    close: () => { setParam(null); setStep(null); },
    selectStep: (s) => setStep(String(s)),
  };
}
```

### Step 2 — Shell component

```tsx
export interface ParameterDrawerProps {
  open: boolean;
  identity: string;                              // for color rail
  title: string;                                 // e.g. "Planner.role"
  subtitle?: string;                             // e.g. "TextParameter · trainable"
  onClose: () => void;
  children: ReactNode;
}

export function ParameterDrawer({ open, ... }: ParameterDrawerProps) {
  // backdrop + animated slide-in from right
  // width: clamp(--drawer-min, --drawer-width, --drawer-max)
  // colored 4px left rail using hashColor(identity)
  // header with title/subtitle + close button
  // body scrolls
}
```

Behavior:
- Slide-in animation uses `--motion-inspector` (220ms) easing tokens
  already in `tokens.css`.
- Backdrop click closes; Escape key closes.
- When `open` flips false, animate out, then unmount (no flash).
- The drawer is portal-rendered via `createPortal` to `document.body`
  so it sits above everything (including the topbar).

### Step 3 — URL behavior

- The hook synchronizes drawer open/closed state with `?param=` in
  the URL.
- `?step=` selects a step within the timeline; the parent component
  consumes this through the hook.
- Closing the drawer clears both query params (single
  `navigate(...)` call).
- Browser back/forward navigates between drawer states.

### Step 4 — Composition

```tsx
const drawer = useParameterDrawer();
const node = ... // resolve from drawer.paramPath
return (
  <>
    <StructureTree
      root={tree}
      selectedParamPath={drawer.paramPath}
      onSelectParameter={(p) => drawer.open(p.fullPath)}
    />
    <ParameterDrawer
      open={drawer.paramPath != null}
      identity={node?.hashContent ?? ""}
      title={node?.label ?? ""}
      subtitle={...}
      onClose={drawer.close}
    >
      {/* per-type evolution view rendered by the integration brief */}
    </ParameterDrawer>
  </>
);
```

Brief `04-01` does the composition.

## Design alternatives

1. **Modal vs side drawer.** Recommendation: side drawer (user's
   explicit choice).
2. **Resizable width vs fixed.** Recommendation: fixed via tokens for
   v1; resizable in stretch.
3. **One drawer or stack drawers (one per opened parameter).**
   Recommendation: one drawer at a time. Stacking confuses the URL.

## Acceptance criteria

- [ ] Opening the drawer sets `?param=...` in the URL.
- [ ] Closing the drawer (X, backdrop, Escape) clears `?param` and
  `?step`.
- [ ] Browser back navigates between drawer states.
- [ ] Drawer width respects the clamp; on a 1000px viewport the
  drawer takes 50vw clamped to ≥ 480px.
- [ ] Drawer header has a 4px-wide colored left rail using
  `hashColor(identity)`.
- [ ] `pnpm test --run` passes.

## Test plan

- `parameter-drawer.test.tsx`:
  - Render with `open=false` → not in DOM.
  - Render with `open=true` → in DOM with title/subtitle.
  - Click backdrop → `onClose` fires.
  - Press Escape → `onClose` fires.
- `use-parameter-drawer.test.ts`: simulate URL state transitions.

## Out of scope

- The per-type evolution content (briefs `03-03`, `03-04`).
- Wiring to the Training tab (brief `04-01`).

## Stretch goals

- Drag-handle on the left edge to resize; persist width in
  `localStorage`.
- A small `← prev / next →` chip in the drawer header that, when a
  StructureTree selection exists, jumps to the previous/next
  trainable parameter without closing the drawer.
- A "compare with previous step" toggle that splits the drawer body
  into two columns for the selected step and its predecessor.
