# Agent-view rewrite — overview

The `apps/dashboard/` agent-detail experience is being rebuilt from
the ground up. **No backwards compatibility**: old code under
`apps/frontend/src/registry/`, `src/shared/`, `src/components/` (the
monolithic renderer), and `apps/frontend/src/layouts/default.json`
is demolished and rebuilt under a new convention.

The goal: when a user clicks any non-algorithm run in the dashboard
sidebar, they land on a view that exploits **every** observable
surface operad ships — graph topology, hashes, invocation history,
prompts, configuration, langfuse traces — and exposes them through
a single fluid UI. See the agent-facing `INVENTORY.md` at the repo
root for the full surface.

Read this overview, then your task brief, then start coding. Read
`METAPROMPT.md` if you haven't already; the library invariants apply
to apps work too.

---

## What we're building

| Area | What it looks like |
| --- | --- |
| **Run sidebar** | Collapsible (rail mode), grouped by algorithm class, search/filter intact. |
| **Metadata header** | Class name, hash_content, script origin, invocations table with per-call latency / tokens / langfuse link. |
| **Insights row** | Reproducibility fingerprint (7 hashes, copyable), prompt-drift strip, cost/latency sparklines, backend/model badges, per-attribute value distributions. |
| **Interactive graph** | React Flow. **Inverted semantics: input/output types as nodes, agents as edges.** Pan, zoom, minimap. Click a node → I/O field popup with `name (type): description` + S/U flag. Click an edge → agent popup with config toggle + langfuse / events / prompt links. |
| **Side drawer** | Right-hand resizable panel that opens whenever a popup link fires. Holds: langfuse iframe, filtered event timeline, prompt diff across invocations, value timeline for one attribute. |
| **Advanced (iter 4)** | Forward-hook indicators, streaming chunk replay, trainable-parameters panel, AgentDiff between invocations, "run this example" inline experimentation. |

---

## Layout convention (json-render style, per-folder registry)

Every component domain owns its own folder with this shape:

```
apps/frontend/src/components/<domain>/
├── <component>.tsx     # React impl(s)
├── registry.tsx        # exports { <domain>Definitions, <domain>Components }
└── index.ts            # re-export of the above
```

A top-level `apps/frontend/src/components/registry.tsx` composes all
domain bundles via spread:

```tsx
import { defineRegistry } from "@json-render/react";
import { uiDefinitions, uiComponents } from "./ui";
import { panelDefinitions, panelComponents } from "./panels";
import { agentViewDefinitions, agentViewComponents } from "./agent-view";

export const catalog = { ...uiDefinitions, ...panelDefinitions, ...agentViewDefinitions };
export const { registry } = defineRegistry(catalog, {
  components: { ...uiComponents, ...panelComponents, ...agentViewComponents },
});
```

`agent-view/` itself splits into sub-folders (`metadata/`, `graph/`,
`drawer/`, `insights/`) so multiple parallel streams can build inside
it without merge conflicts. Each sub-folder is self-contained.

---

## Iterations and parallel streams

| Iter | Theme | Streams |
| --- | --- | --- |
| 1 | Foundation | `1-1-frontend-foundation`, `1-2-graph-inversion`, `1-3-dashboard-endpoints` |
| 2 | Agent-view core | `2-1-metadata-and-layout`, `2-2-interactive-graph`, `2-3-drawer-shell`, `2-4-insights` |
| 3 | Drawer content | `3-1-drawer-langfuse-events`, `3-2-drawer-prompt-diff`, `3-3-drawer-value-timeline` |
| 4 | Advanced features | `4-1-hooks-and-stream-replay`, `4-2-trainable-params-and-diff`, `4-3-prompt-experimentation` |

Streams within an iteration ship in parallel, merge as a batch, then
the next iteration kicks off. Each brief states what it depends on
from earlier iterations and what contract it exposes for siblings.

---

## Working agreements

- **Break things.** No backcompat shims, no `// removed` comments,
  no soft migrations. If the new code obsoletes an old file, delete
  the old file.
- **One PR per stream.** Title with the brief filename.
- **Offline tests must pass.** `pnpm test`, `pnpm typecheck`,
  `uv run pytest tests/`. Integration tests stay gated.
- **Contracts before code.** Each brief states the contracts. If
  you discover a sibling needs something different, post an update
  to your brief and theirs before diverging.
- **Be ambitious.** The bar is "best agent dashboard view we can
  build", not "checkbox passed". Investigate `INVENTORY.md` and the
  operad source — there's far more material to surface than any one
  brief enumerates. Where a brief says "include X", treat it as a
  floor, not a ceiling.
- **Be opinionated.** If a hint in your brief is wrong, push back.
  We'd rather argue about UX than ship the obvious thing.

---

## Verification baseline (every iteration)

```bash
pnpm -C apps/frontend install
pnpm -C apps/frontend typecheck
pnpm -C apps/frontend test
pnpm -C apps/frontend lint
uv run pytest tests/                          # operad core
uv run pytest apps/dashboard/tests/ -q        # dashboard backend
uv run python -c "import operad"              # smoke
```

UI changes additionally require a manual smoke: run `make dashboard`
+ `make dev-frontend`, open `http://localhost:5173/runs/<some-id>`,
verify the agent view renders end-to-end without console errors.
