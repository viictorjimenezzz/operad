# 03-01 StructureTree component

**Branch**: `dashboard/structure-tree`
**Wave**: Sequence 3, parallel batch
**Dependencies**: `01-01` (parameters route enrichment), `01-02`
(density tokens)
**Estimated scope**: medium

## Goal

Build the `StructureTree` component: a navigable representation of the
agent's structural composition (Sequential / Parallel / Switch trees
of leaves), with each leaf expandable to show its declared attributes
(role, task, rules, examples, config, plus any trainable
`Parameter`s). This component is the spine of the new Training tab
and the algorithm Parameters tab.

## Why this exists

- §7 of `00-contracts.md` defines `StructureTreeNode` as the canonical
  shape for the structural view.
- The user explicitly drew the desired shape:

  ```
  research_analyst
  ├── Planner
  ├── biology
  │   ├── Reasoner
  │   ├── loop
  │   │   ├── Reasoner · Actor · Extractor · Evaluator
  │   └── Reasoner
  ├── policy / economic (same shape)
  └── Reasoner
  ```

- Without this component, the Training tab cannot show the structure
  the user requested.

## Files to touch

- New: `apps/frontend/src/lib/structure-tree.ts` — pure builder:
  `buildStructureTree(graph: AgentGraphResponse, params: AgentParametersResponse[]): StructureTreeNode`.
- New: `apps/frontend/src/components/agent-view/structure/structure-tree.tsx` —
  the rendering component.
- New: `apps/frontend/src/components/agent-view/structure/structure-tree.test.tsx`.
- New: `apps/frontend/src/components/agent-view/structure/index.ts` —
  exports.

## Contract reference

`00-contracts.md` §7 (`StructureTreeNode`), §3 (palette — leaf nodes
use `hashColor(node.hashContent)`; class color uses
`paletteIndex(className)`), §4 (density), §13 (folder convention).

## Implementation steps

### Step 1 — `buildStructureTree`

Input: `AgentGraphResponse` (the existing `/runs/{id}/agent_graph`
shape) plus an array of per-leaf `AgentParametersResponse` records.

Output: a single `StructureTreeNode` rooted at the root agent.

Key rules:
- `kind` = `"composite"` for nodes that have children in the graph;
  `"leaf"` otherwise.
- `parameters` is populated for leaves only (composites don't carry
  declared attributes).
- `parameters` for a leaf includes:
  - The four declared attributes always: `role`, `task`, `rules`,
    `examples`. They're rendered even if not trainable; the
    `requiresGrad` field tells the UI whether they're clickable for
    evolution.
  - Plus per-leaf `Configuration` if present (one entry per dotted
    sub-path, e.g. `config.sampling.temperature`).
- Default expansion (per user choice in the design discussion):
  composites with > 5 children are collapsed; ≤ 5 are expanded.
  Leaves are always collapsed; clicking them expands their
  parameters.

Type inference for `parameters[i].type`:
- `role`, `task` → `"text"`
- `rules` → `"rule_list"`
- `examples` → `"example_list"`
- `config.<numeric>` (e.g. temperature, top_p, max_tokens) → `"float"`
- `config.<categorical>` (model, backend, renderer) → `"categorical"`
- `config` (whole) → `"configuration"`

### Step 2 — Component shape

```tsx
export interface StructureTreeProps {
  root: StructureTreeNode;
  selectedParamPath?: string | null;       // matches drawer URL state
  onSelectParameter?: (param: ParameterDescriptor, node: StructureTreeNode) => void;
  onSelectAgent?: (node: StructureTreeNode) => void;
  density?: "compact" | "comfortable";
}

export function StructureTree({ root, ... }: StructureTreeProps) { ... }
```

Rendering:
- Indentation by depth × 16px.
- Composite rows: chevron (▾/▸) + class name + child count.
- Leaf rows: dot (`hashColor(hashContent)`) + class name + label
  (last segment of path) + ⚙ icon when `parameters.some(requiresGrad)`.
- Expanded leaf rows: child rows for each parameter, with:
  - Trainable: tinted text + chevron leading to evolution drawer.
  - Non-trainable: muted text, click reveals current value
    (collapsible inline).

Click handlers:
- Click a composite chevron → toggle expansion (local state).
- Click a leaf row → expand/collapse leaf parameters; also fire
  `onSelectAgent`.
- Click a trainable parameter row → fire `onSelectParameter`.
- Highlight the row whose `param.fullPath === selectedParamPath`.

### Step 3 — Performance

For agents with > 50 leaves, virtualize. Use
`@tanstack/react-virtual` (already a dep) over the flat-list
representation when `flat.length > 200`. Up to 200 rows, render all.

### Step 4 — Accessibility

- Composite chevron is a `<button>` with `aria-expanded`.
- Leaf row is a `<button>` with proper role.
- Tree container has `role="tree"`; nodes have `role="treeitem"`.
- Keyboard: `↑/↓` move, `→` expand, `←` collapse, `Enter` select.

## Design alternatives

1. **Embed parameter rows as tree children vs render them in a
   side-by-side list when leaf is selected.** Recommendation:
   embed as children — matches the user's mental model and avoids a
   second navigation step.
2. **Compute structure tree on the frontend vs on the backend.**
   Recommendation: frontend — `agent_graph` + `parameters` are both
   already exposed; reshape locally. Avoids a third route.
3. **Render `Parallel` branches with named keys (`biology`, `policy`)
   vs unnamed indices.** Recommendation: named keys — read directly
   from the graph node's `path` segment. The user's tree example uses
   named branches.

## Acceptance criteria

- [ ] `buildStructureTree` produces the user-drawn tree shape for
  example 01.
- [ ] Composites with > 5 children render collapsed by default;
  ≤ 5 expanded.
- [ ] Leaves with at least one trainable parameter render the ⚙
  icon.
- [ ] Click a trainable parameter row fires `onSelectParameter` with
  the descriptor and node.
- [ ] Keyboard navigation works (↑/↓/→/←/Enter).
- [ ] `pnpm test --run` passes; new tests cover both the builder and
  the component.

## Test plan

- `structure-tree.test.tsx`: build a 3-level fixture (composite of
  composites of leaves) and assert tree shape; click a parameter row
  and assert callback fires.
- `lib/structure-tree.test.ts`: unit-test `buildStructureTree` with
  fixture graphs.

## Out of scope

- The drawer (brief `03-02`).
- Per-type evolution views (briefs `03-03`, `03-04`).
- Wiring into the Training tab (brief `04-01`).

## Stretch goals

- Show the `hash_content` mini-dot for every leaf, even non-trainable
  ones (more identity-first signal).
- A "show only trainable" filter chip at the top of the tree.
- Show per-leaf invocation count from `useAgentInvocations(runId, path)`
  next to the class name (already partially wired in
  `agent-flow-graph.tsx`).
- Support search-within-tree: a slim search box above the tree
  filters nodes by class name or path.
