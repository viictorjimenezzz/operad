# 06-01 Hash-drift visualization across panels

**Branch**: `dashboard/hash-drift-row`
**Wave**: Sequence 6, parallel batch
**Dependencies**: `01-02` (`HashRow` primitive)
**Estimated scope**: small

## Goal

Promote the 7-hash reproducibility fingerprint (§20 of inventory)
from a buried "Reproducibility" section to a first-class signal
across the dashboard. Specifically:

1. Drawer headers (graph inspector, parameter drawer): inline hash
   monogram + tooltip listing all 7 hashes.
2. RunTable: a new optional hash-drift column that shows a 7-cell
   strip of pulsing dots when any hash changed since the previous
   row.
3. Algorithm Invocations tabs: include the hash-drift strip as a
   default-visible column (toggleable).

## Why this exists

- §20 of the inventory: hashes are operad's "tell me what's
  different" indicator. Today they live only on the
  Reproducibility section of the single-invocation Overview.
- The user said "be ambitious" and "exploit the inventory".

## Files to touch

- `apps/frontend/src/components/agent-view/graph/inspector/inspector-shell.tsx` —
  add hash monogram next to the title.
- `apps/frontend/src/components/agent-view/structure/parameter-drawer.tsx` —
  same.
- `apps/frontend/src/components/ui/run-table.tsx` — add a new
  `hashDriftStrip` cell kind (or implement as an extension of the
  existing `hash` kind, configurable). Coordinate with brief
  `01-02` if landing concurrently.
- `apps/frontend/src/components/ui/hash-row.tsx` — add a `compact`
  variant that shows just the monogram + tooltip (no chip strip).

## Contract reference

`00-contracts.md` §6 (HashRow), §3 (palette).

## Implementation steps

### Step 1 — `HashRow` compact variant

Add a `variant?: "full" | "compact" | "strip"` prop:

- `full`: existing chip-strip rendering (brief `01-02`).
- `compact`: a single `hash_content` monogram + dot, tooltip listing
  all 7 hashes.
- `strip`: a horizontal 7-cell strip showing dots colored by
  `hashColor(value)` — null cells get muted dot. Width: 60px. Used
  in tables.

### Step 2 — Inspector + drawer header

```tsx
<header>
  ...
  <HashRow variant="compact" current={meta.hashes} previous={prevHashes} />
</header>
```

`previous` only set when a previous invocation/group-mate exists;
chip outlines glow `--color-warn` for changed hashes.

### Step 3 — Table column

Add to the algorithm Invocations table (brief `05-11`):

```ts
{
  id: "drift",
  label: "Drift",
  source: "_drift",
  width: 80,
  defaultVisible: true,
}
```

`source: "_drift"` resolves to a `hash` kind value in `run-table.tsx`
that triggers the strip rendering.

### Step 4 — Tooltip content

The compact tooltip lists all 7 hashes, each as `key: short` with a
copy button. When `previous` is provided, changed keys are bolded
with a `Δ` prefix.

## Design alternatives

1. **One `compact` chip vs strip.** Recommendation: support both.
   Drawer headers want one chip; tables want the strip.
2. **Show hash drift only when something changed vs always.**
   Recommendation: always render in tables, hide in drawer headers
   when no `previous`.

## Acceptance criteria

- [ ] Inspector header has a hash monogram with tooltip.
- [ ] Parameter drawer header has the same monogram.
- [ ] Algorithm Invocations table shows the drift column by default.
- [ ] Tooltip lists all 7 hashes with copy affordance.
- [ ] `pnpm test --run` passes.

## Test plan

- `hash-row.test.tsx` (extend): render in `compact` and `strip`
  variants.
- Visual: examples 02 and 04 show the drift indicator in their
  Invocations tabs.

## Stretch goals

- A "diff highlights" mode in the strip that pulses changed cells
  for 3 seconds after a row appears live.
- A click-to-pin behavior: clicking a hash chip in the strip pins
  that hash as a sort key.
