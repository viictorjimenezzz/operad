# 01-02 Primitives and tokens

**Branch**: `dashboard/primitives-and-tokens`
**Wave**: Sequence 1, parallel batch
**Dependencies**: none
**Estimated scope**: medium (UI primitives + tokens; consumed by every later brief)

## Goal

Land every primitive that the rest of the redesign consumes: density
tokens, four new `RunTable` cell kinds, the `HashRow` primitive, and
the identity-color extension across `MetricSeriesChart` /
`MultiSeriesChart` / drawer rails. Without this brief, downstream
briefs duplicate primitives.

## Why this exists

- §3 of `00-contracts.md` mandates identity colors everywhere; today
  `MetricSeriesChart` and `MultiSeriesChart` only color when a caller
  passes an `identity` prop. Centralizing this prevents drift.
- §4 introduces density tokens; without them the visual pass in
  Sequence 2 looks inconsistent.
- §5 reserves new cell kinds (`param`, `score`, `diff`, `image`); the
  per-algorithm Invocations tables in Sequence 5 need them.
- §6 reserves the `HashRow` primitive; the single-invocation
  Reproducibility section (brief 02-01) and Compare mode (brief 06-04)
  consume it.

## Files to touch

- `apps/frontend/src/styles/tokens.css` — add the density tokens listed
  in §4.
- `apps/frontend/src/components/ui/run-table.tsx:37-48` — extend
  `RunFieldValue` union; extend `renderCell` (`run-table.tsx:487-537`).
- `apps/frontend/src/components/ui/hash-row.tsx` — new file.
- `apps/frontend/src/components/ui/index.ts` — export `HashRow`.
- `apps/frontend/src/components/ui/multi-series-chart.tsx` and
  `metric-series-chart.tsx` — accept and use a per-series identity
  string for color resolution; document the rule in a JSDoc comment.
- `apps/frontend/src/components/ui/run-table.test.tsx` — extend with
  cases for the four new cell kinds.
- `apps/frontend/src/components/ui/hash-row.test.tsx` — new test file.

Do NOT touch `apps/frontend/src/lib/hash-color.ts`; it already
exposes the helpers (verified).

## Contract reference

`00-contracts.md` §3 (palette), §4 (density), §5 (RunTable cells),
§6 (HashRow).

## Implementation steps

### Step 1 — Density tokens

Add to `@theme` in `tokens.css`:

```css
--row-h: 28px;
--row-h-tight: 22px;
--panel-pad-y: 8px;
--panel-pad-x: 12px;
--canvas-gutter: 1px;
--drawer-width: 50vw;
--drawer-min: 480px;
--drawer-max: 720px;
```

Existing `--row-height-sm`/`--row-height-xs` (28/22) stay as-is; they're
consumed by `RunTable`. The new tokens are reserved for downstream
briefs and documented in `00-contracts.md` §4.

### Step 2 — Four new `RunTable` cell kinds

Extend `RunFieldValue`:

```ts
| { kind: "param"; value: unknown; previous?: unknown; format?: "auto" | "text" | "number" }
| { kind: "score"; value: number | null; min?: number; max?: number }
| { kind: "diff"; value: string; previous?: string }
| { kind: "image"; src: string; alt: string; width?: number; height?: number }
```

Renderers:
- `param` — format the value using existing helpers
  (`formatNumber`, `formatTokens`, `formatCost`) when `format` is
  `"number"`; otherwise stringify with `JSON.stringify` for nested
  objects, plain string for primitives. When `previous != null` and
  `previous !== value`, append a small ` ↑ +Δ` or `↓ −Δ` suffix in
  `text-muted` if numeric, else a colored dot.
- `score` — render `value.toFixed(3)` + a 4px-tall horizontal bar
  positioned at `(value - min) / (max - min)`. Default `min=0`,
  `max=1`. Bar color: `--color-ok` if value > 0, `--color-warn` for
  zero, `--color-err` for negative.
- `diff` — show `value` truncated to ~80ch with hover-expand; if
  `previous != null`, render `previous` struck-through and `value`
  highlighted. Use a tiny `<details>` for full-text expansion.
- `image` — `<img>` (or `<svg>` if `src` starts with `data:image/svg`),
  default 24x24, clamp to provided dims.

Sort order: `param` sorts on the value (numeric then string);
`score` sorts on the number; `diff` sorts on `value`; `image` is
non-sortable.

### Step 3 — `HashRow` primitive

```tsx
// apps/frontend/src/components/ui/hash-row.tsx
import { hashColor } from "@/lib/hash-color";
import * as Tooltip from "@radix-ui/react-tooltip";

const HASH_KEYS = [
  "hash_model", "hash_prompt", "hash_input",
  "hash_output_schema", "hash_config", "hash_graph", "hash_content",
] as const;

export type HashKey = (typeof HASH_KEYS)[number];
export interface HashRowProps {
  current: Partial<Record<HashKey, string | null>>;
  previous?: Partial<Record<HashKey, string | null>>;
  size?: "sm" | "md";
  onCopy?: (key: HashKey, value: string) => void;
}

export function HashRow({ current, previous, size = "sm", onCopy }: HashRowProps) {
  return (
    <div role="list" className="flex flex-wrap gap-1.5">
      {HASH_KEYS.map((key) => {
        const value = current[key] ?? null;
        const prev = previous?.[key] ?? null;
        const changed = prev != null && value != null && prev !== value;
        return (
          <HashChip
            key={key}
            label={key}
            value={value}
            changed={changed}
            size={size}
            onCopy={onCopy}
          />
        );
      })}
    </div>
  );
}
```

Each chip:
- Tiny dot (6px) at `hashColor(value)`.
- 12-char monogram of the value (or `"—"` if null).
- Tooltip on hover with the full hex, copy button.
- When `changed`, outline `--color-warn` and tiny ↻ icon.

Export in `components/ui/index.ts` next to other primitives.

### Step 4 — Identity-aware chart colors

`MetricSeriesChart` already accepts an `identity` prop and resolves to
`hashColor(identity)` when passed. Audit every call site and remove
ad-hoc color overrides; pass `identity` instead.

`MultiSeriesChart`'s `series` prop already has an `id`; default the
line color to `hashColor(series.id)` unless an explicit `color` is
provided. Document this in JSDoc on the props interface.

Caller-side audit list (frontend search for `MultiSeriesChart` and
`MetricSeriesChart`); fix every site to pass identity rather than
hard-coding `--color-accent` or similar. This audit is part of
acceptance.

## Design alternatives

1. **`HashRow` as a chip strip vs. a 7-row vertical key/value list.**
   Recommendation: chip strip (matches the W&B visual reference; fits
   into the breadcrumb). Vertical loses density.
2. **`param` cell: render previous value or just the delta?**
   Recommendation: just the delta indicator; previous value lives in
   the prior row, repeating it bloats the cell.
3. **`HashRow` consumes `RunSummary` directly vs. a `current/previous`
   record?** Recommendation: generic `current/previous` record; lets
   us reuse the primitive in Compare mode (brief `06-04`) where the
   two sides aren't "current" and "previous".

## Acceptance criteria

- [ ] `tokens.css` has all six new tokens listed in §4.
- [ ] `RunTable` renders each of the four new cell kinds correctly,
  with sort behavior matching the spec.
- [ ] `HashRow` renders 7 chips, each with hover tooltip and copy
  affordance; chips outline `--color-warn` when `previous` differs.
- [ ] Every existing call to `MultiSeriesChart` and `MetricSeriesChart`
  passes an `identity` (or per-series `id`) such that two runs with the
  same `hash_content` get the same color across all panels.
- [ ] `pnpm test --run` passes.

## Test plan

- `run-table.test.tsx` — render rows with each new cell kind; assert
  on `getByText` and `getByRole`.
- `hash-row.test.tsx` — render with 7 hashes; assert all chips render;
  assert `changed` chips have `--color-warn` outline.
- Visual sanity: open `/__dev/primitives` (the `PrimitivesGallery`
  page); add `HashRow` and the new cell kinds to the gallery so future
  agents have a reference.

## Out of scope

- Consuming the new primitives in pages; that's Sequence 2.
- Backend changes (brief `01-01`).
- Layout JSON registry changes.

## Stretch goals

- Add a `param.formatPretty` helper that prettifies long strings
  (collapses whitespace, truncates with middle ellipsis at 60ch).
- Add a `score.bandColors` prop so per-algorithm tables can override
  the `ok/warn/err` mapping (e.g. Trainer's `train_loss` is
  "lower-is-better" → reverse bands).
- Add a `density="cozy" | "compact" | "dense"` prop to `RunTable` and
  apply the row-height token by name. Currently it has
  `compact | cozy`; rename and add `dense=22px`.
