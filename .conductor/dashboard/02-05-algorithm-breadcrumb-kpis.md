# 02-05 Algorithm breadcrumb KPIs

**Branch**: `dashboard/algorithm-breadcrumb-kpis`
**Wave**: Sequence 2, parallel batch
**Dependencies**: none
**Estimated scope**: small

## Goal

The algorithm detail breadcrumb currently shows generic
`ago / dur / tok / $` metrics. Add per-class KPIs so the user can read
"how this run went" at a glance: `cells / best` for Sweep, `K / top`
for Beam, etc.

## Why this exists

- §12 of `00-contracts.md` reserves a per-class KPI table.
- The user said the algorithm pages should show "different things for
  every algorithm" — this is the lightweight, breadcrumb-level
  manifestation. The full per-tab specificity is Sequence 5.

## Files to touch

- `apps/frontend/src/dashboard/pages/run-detail/AlgorithmDetailLayout.tsx:107-153` —
  rewrite `RunBreadcrumb`'s trailing metrics to be class-aware.
- New: `apps/frontend/src/lib/algorithm-kpis.ts` — pure function:
  `computeAlgorithmKpis(run: RunSummary): KpiSpec[]`. Single source of
  truth.
- `apps/frontend/src/lib/algorithm-kpis.test.ts` — unit tests per
  class.

## Contract reference

`00-contracts.md` §12.

## Implementation steps

### Step 1 — Pure KPI function

```ts
export type KpiSpec = { label: string; value: string; sub?: string };

export function computeAlgorithmKpis(run: RunSummary): KpiSpec[] {
  const cls = run.algorithm_class ?? "";
  switch (cls) {
    case "Sweep": return sweepKpis(run);
    case "Beam": return beamKpis(run);
    case "Debate": return debateKpis(run);
    case "EvoGradient": return evoKpis(run);
    case "Trainer": return trainerKpis(run);
    case "OPRO": return oproKpis(run);
    case "SelfRefine": return selfRefineKpis(run);
    case "AutoResearcher": return autoResearcherKpis(run);
    case "TalkerReasoner": return talkerKpis(run);
    case "Verifier": return verifierKpis(run);
    default: return [];
  }
}
```

Each per-class function reads only fields already on `RunSummary`
(see `00-contracts.md` §12 for the mapping). Examples:

```ts
function sweepKpis(run: RunSummary): KpiSpec[] {
  const cells = run.generations.length;
  const best = Math.max(...run.generations.flatMap(g => g.scores));
  return [
    { label: "cells", value: String(cells) },
    { label: "best", value: Number.isFinite(best) ? best.toFixed(3) : "-" },
  ];
}

function beamKpis(run: RunSummary): KpiSpec[] {
  const candidates = run.candidates;
  const top = candidates.length > 0
    ? Math.max(...candidates.map(c => c.score ?? -Infinity))
    : null;
  return [
    { label: "K", value: String(candidates.length) },
    { label: "top", value: top != null && Number.isFinite(top) ? top.toFixed(3) : "-" },
  ];
}
```

Cover all classes in `00-contracts.md` §12.

### Step 2 — Wire to `RunBreadcrumb`

After the existing `Metric label="ago/dur/tok/$"`, append the
class-specific KPIs:

```tsx
{computeAlgorithmKpis(run).map((kpi) => (
  <Metric key={kpi.label} label={kpi.label} value={kpi.value} sub={kpi.sub} />
))}
```

When the function returns `[]` (unknown class), the breadcrumb is
unchanged.

## Design alternatives

1. **Compute KPIs server-side vs client-side.** Recommendation:
   client-side. The data is already on `RunSummary`; round-trip is
   noise.
2. **Show KPIs always or only when run has ended.** Recommendation:
   always. Live runs benefit from the running tally
   (`gens / 5 of 10`).
3. **One generic KPI line vs class-specific.** Recommendation:
   class-specific (the user's literal request).

## Acceptance criteria

- [ ] On a Sweep run, the breadcrumb shows `cells N · best 0.xxx`.
- [ ] On a Beam run, `K N · top 0.xxx`.
- [ ] On a Trainer run, `epochs N · best_val 0.xxx · lr ...`.
- [ ] On every other class in `00-contracts.md` §12, the appropriate
  KPI pair appears.
- [ ] Unknown classes show no extra KPIs (breadcrumb unchanged).
- [ ] `pnpm test --run` passes.

## Test plan

- `algorithm-kpis.test.ts` — one fixture per class; assert the KPI
  array matches expected.
- Manual: examples 02 (Sweep) and 04 (EvoGradient) show the right
  KPIs.

## Out of scope

- The per-algorithm tab views (Sequence 5).
- The per-algorithm sidebar dot color (already in brief `01-03`).

## Stretch goals

- Add color-coded trend arrows (↑ green, ↓ red, → muted) when the
  KPI has a previous value to compare against (use the second-most
  recent run of the same class).
- Show a tiny sparkline next to `best` for `Sweep`/`EvoGradient`/
  `Trainer` showing the score's trajectory through the run.
- Add a `?compact=1` URL flag that drops the verbose `ago/dur/tok/$`
  metrics and keeps only the class-specific KPIs (for tight
  screens).
