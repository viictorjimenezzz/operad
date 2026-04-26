# Per-algorithm layouts

Each `*.json` here is a `LayoutSpec` that describes the dashboard
arrangement for one algorithm.

## Add a new algorithm dashboard

1. **Drop a JSON.** Create `<algorithm>.json` and adjust:
   - `algorithm`: the exact `algorithm_path` value the dashboard's
     `RunInfo.algorithm_path` carries (e.g. `Sweep`, `VerifierLoop`).
   - `dataSources`: which backend endpoints to fetch + optional
     `.sse` streams to live-update them. `$context.runId` substitutes
     in.
   - `spec.elements`: the UI tree, keyed by element id; `spec.root`
     is the entry id. Component types must exist in
     `src/components/catalog.ts`.
2. **Wire it up.** `index.ts` discovers all JSON files via
   `import.meta.glob`. The Zod parse on module load catches typos.
3. **Test it.** Add a Vitest spec in `src/tests/layouts.test.ts`
   loading the JSON through `LayoutSpec.parse(...)` and confirming
   the element graph reaches every node from `root`.
4. **(If a new component is needed)** Add it to
   `src/components/catalog.ts` *and* register an implementation in a
   `src/components/**/registry.tsx` module. The TypeScript
   compiler enforces both — registry registration without catalog
   declaration won't compile.

## Source expressions inside a layout

| Expression                       | Resolves to                                                      |
| -------------------------------- | ---------------------------------------------------------------- |
| `$context.<key>`                 | Value passed in the `<DashboardRenderer context>` prop (e.g. `runId`). |
| `$queries.<name>`                | The current value of the named data source (HTTP fetch + optional SSE override). |
| `$queries.<name>.foo.bar`        | Dotted-path lookup into the source value.                        |
| `$run.events`                    | Live event buffer for the current run from Zustand.              |
| `$run.summary`                   | Alias for `$queries.summary` if the layout declares one.         |

Props named `source` (or `source<X>`) are resolved to a runtime
value; everything else is forwarded literally. Resolved props are
renamed to `data` (or `data<X>`) before they reach the component
implementation, which keeps registry components decoupled from the
layout DSL.
