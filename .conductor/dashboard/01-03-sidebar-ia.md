# 01-03 Sidebar IA — three-level agents and class-first algorithms

**Branch**: `dashboard/sidebar-ia`
**Wave**: Sequence 1, parallel batch
**Dependencies**: none (uses fields already on `RunSummary`/
`AgentGroupSummary`; coexists with `01-01` which adds richer data).
**Estimated scope**: medium (touches the sidebar, the routes, and one
new index page)

## Goal

Restructure the agents sidebar to a stable three-level tree
(Class → Instance → Invocation), regardless of singleton counts, and
refit the algorithms sidebar so each row's primary label is the
algorithm class instead of the run id. Add a per-class index page
under `/agents/_class_/<className>` to keep the URL space coherent.

## Why this exists

- §1 of `00-contracts.md`: identity model is three levels for agents,
  two levels for algorithms; the user explicitly chose to surface this
  even when counts are 1.
- The current sidebar (`agents-tree.tsx:95-106`) collapses
  single-invocation groups into a single row. The user calls this
  wrong; W&B shows `Group` → `Run` even with one run.
- The current algorithm row label is the truncated `run_id`
  (`algorithms-tree.tsx:116-122`); the user wants the class name with
  run id as secondary.

## Files to touch

- `apps/frontend/src/components/panels/section-sidebar/agents-tree.tsx` —
  rewrite `buildRow` and `onSelect` to handle three levels.
- `apps/frontend/src/components/panels/section-sidebar/algorithms-tree.tsx` —
  flip primary label to class name; demote run id to meta.
- `apps/frontend/src/components/ui/group-tree.tsx` (or wherever
  `GroupTreeRow` lives) — verify it supports nested children at depth
  3; extend if needed.
- `apps/frontend/src/dashboard/routes.tsx` — add
  `/agents/_class_/:className` route.
- `apps/frontend/src/dashboard/pages/AgentsByClassPage.tsx` — new page.
- `apps/frontend/src/dashboard/pages/AgentsIndexPage.tsx` — flip from
  flat list to class-grouped list (uses `/api/agent-classes` if
  `01-01` lands first; falls back to client-side grouping otherwise).
- `apps/frontend/src/hooks/use-runs.ts` — add `useAgentClasses` hook
  reading `/api/agent-classes` (with client-side fallback grouping if
  the route is absent — be defensive, since `01-01` is parallel).

## Contract reference

`00-contracts.md` §1 (identity model), §3 (palette — class rows use
`paletteIndex(className)`), §13 (component registry).

## Implementation steps

### Step 1 — Class-level index

`/agents` becomes a list of agent *classes*, not a list of instances:

```
Class            instances  last_seen   running   errors
research_analyst  1          5m ago     0         0
Reasoner          3          1h ago     0         1
Trainer           2          1d ago     0         0
```

Click a class row → navigate to `/agents/_class_/<className>`. Class
row color dot uses `var(--qual-${paletteIndex(className) + 1})`.

### Step 2 — Per-class index page (`AgentsByClassPage`)

Renders the instances of one class:

```
research_analyst                                         (1 instance)

  hash_content      runs  last_seen   running  errors  cost
  abc123…           1     5m ago      0        0       $0.00
```

Click an instance row → `/agents/<hashContent>`. Color dot uses
`hashColor(hashContent)`. Use the existing `RunTable` primitive with
column descriptors.

### Step 3 — Three-level sidebar tree

`AgentsTree` becomes:

```
Classes
  ▾ research_analyst (1)
    ▾ abc123… (1)               ← always shown, even with count==1
       └─ <run_id> (5m ago)     ← always shown, even with count==1
  ▾ Reasoner (3)
    ▸ def456… (2)
    ▾ ghi789… (1)
       └─ <run_id> (now)
```

URL routing rules:
- Click class row → `/agents/_class_/<className>`.
- Click instance row → `/agents/<hashContent>`.
- Click invocation row → `/agents/<hashContent>/runs/<runId>`.

The "single-invocation collapse" branch in
`agents-tree.tsx:95-106` is removed; every instance always renders an
invocation child list.

### Step 4 — Algorithms sidebar primary label flip

`algorithms-tree.tsx:106-126` builds the row with
`label = truncateMiddle(run_id, 14)`. Change to:

```tsx
{
  ...,
  label: <span className="text-text">{group.class_name ?? "Algorithm"}</span>,
  meta: (
    <span className="font-mono text-[10px] text-muted-2">
      {truncateMiddle(r.run_id, 12)} · {formatRelativeTime(r.started_at)}
    </span>
  ),
  trailing: r.algorithm_terminal_score != null
    ? r.algorithm_terminal_score.toFixed(3)
    : undefined,
}
```

Note: the `GroupTreeSection` already shows the class name as a header.
With the per-row label also being the class name, the section header
becomes redundant. Drop the `label={group.class_name}` and instead use
a single flat list under the rail title (`"Algorithms"`).

For the dot color in the algorithms tree, use class-categorical:

```ts
colorIdentity: r.algorithm_class ?? r.run_id,
```

Combined with §3 of contracts, two `Sweep` rows get the same
`paletteIndex("Sweep") + 1` color, two `Beam` rows another, etc.

### Step 5 — Route registration

In `routes.tsx`, between `/agents` and `/agents/:hashContent`:

```tsx
{ path: "agents/_class_/:className", element: <AgentsByClassPage /> },
```

`useParams<{ className: string }>()` gives the class. URL-encode on
write, `decodeURIComponent` on read.

## Design alternatives

1. **Class index as a card grid vs a `RunTable`.** Recommendation:
   `RunTable` — consistent with everything else and the column picker
   is a free win.
2. **Sidebar dot color for invocations: by run_id or by hash_content.**
   Recommendation: `hash_content` — same instance always glows the
   same color across runs.
3. **Should the algorithms sidebar still group by class?** If we flip
   the primary label, the per-class header becomes redundant. The
   class color dot does the categorical job. Recommendation: ungroup,
   flat list. Easier to scan; class is identifiable at a glance.

## Acceptance criteria

- [ ] `/agents` shows classes, not instances. Each class row navigates
  to `/agents/_class_/<className>`.
- [ ] `/agents/_class_/research_analyst` shows the single instance for
  example 01.
- [ ] `/agents/<hashContent>` (existing route) still works.
- [ ] The agents sidebar always shows three levels even when an
  instance has one invocation. Examples 01-04 produce the expected
  tree shape.
- [ ] The algorithms sidebar shows the class name as the dominant
  label; run id is in the meta line.
- [ ] Two algorithm runs of the same class share a dot color; two of
  different classes don't.
- [ ] `pnpm test --run` passes.

## Test plan

- `agents-tree.test.tsx` (extend existing): assert three rows for one
  class with one instance with one invocation.
- `algorithms-tree.test.tsx` (extend or create): assert primary label
  is class name; assert dot color matches `paletteIndex(class)`.
- Manual: open `/agents`, navigate Class → Instance → Invocation;
  bookmark each level and reload; URLs work.
- Manual: with examples 01-04 running, the agents tree renders all
  four trees correctly.

## Out of scope

- Renaming `Train` → `Training` in `agentGroupTabs` (that's brief
  `02-04`).
- Per-class breadcrumb KPIs (brief `02-05`).
- `/api/agent-classes` route implementation (brief `01-01`); use a
  client-side grouping fallback that reads `/api/agents` and groups by
  `class_name`.

## Stretch goals

- Search inside the sidebar by class name promotes the class to the
  top and expands its children.
- Add a "pin instance" affordance: a star button that pins the
  instance to the top of the sidebar (state in `localStorage`).
- The class color dot becomes a small histogram of recent invocation
  states (running/ended/error proportions over the last 12).
