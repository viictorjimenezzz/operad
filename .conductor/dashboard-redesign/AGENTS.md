# Dashboard redesign — agent guidelines

You are working on a multi-agent redesign of the operad dashboard. There is
exactly one document per section in this folder; you have been assigned
one. Read this guideline in full before opening any code.

## What this redesign is for

The current dashboard works but feels "agent-shaped" everywhere — every
algorithm, every training run, every group page reuses the same Overview
/ Graph / Invocations / Cost / Drift tabs. This is wrong: an algorithm
has a fundamentally different structure from an agent, a training run has
its own optimization story, and a sweep cell has nothing to do with a
debate round. The redesign **restores per-context structure**: each
algorithm gets its own tab set that matches its data; each rail gets its
own visualization.

The visual reference is Weights & Biases (see screenshots in the parent
`proposal.md`). The structural reference is the operad data model, which
is exposed in `INVENTORY.md` (the canonical capability list).

## Reading order before you write a single line

1. `**/Users/viictorjimenezzz/Documents/operad/AGENTS.md`** — repo-wide
  working rules. The "Surgical Changes" rule is binding: every changed
   line must trace directly to your brief. The "Codebase Invariants"
   apply (Agent contracts, `build()` semantics, etc.) but you are
   editing `apps/dashboard/` and `apps/frontend/`, not core operad.
2. `**/Users/viictorjimenezzz/Documents/operad/METAPROMPT.md`** — only
  line 36 matters here: *DO NOT KEEP BACKWARDS COMPATIBILITY*. Wherever
   the current API/UX gets in the way, replace it.
3. `**/Users/viictorjimenezzz/Documents/operad/INVENTORY.md`** — the
  list of things operad can do. **Treat this as a feature menu.** Your
   brief points you at the relevant sections; cross-reference against
   the inventory and pull in capabilities that make your view richer.
   Examples: §13 (observers / OtelObserver / Langfuse deep-link), §17
   (cassette-replay), §20 (reproducibility hashes), §21 (`Parameter`
   family + `MetricLoss` + `Trainer`), §22 (`PromptTraceback`).
4. `**/Users/viictorjimenezzz/Documents/operad/proposal.md`** — the full
  redesign proposal, with file:line references to current code. Skim
   it; your brief was carved from it.
5. `**/.conductor/dashboard-redesign/00-CONTRACTS.md**` — the shared
   types, props, JSON-layout shape, backend route contracts. You **must**
   conform to this. If your brief and the
   contracts disagree, stop and ask before improvising.
6. **Your own brief.** Read it twice. Pay particular attention to the
  "Files to touch" and "Acceptance criteria" sections.
7. **Adjacent briefs**, only if your brief flags an explicit dependency.
  E.g., the per-algorithm briefs depend on Brief 02 (LayoutResolver
   wiring) and Brief 15 (universal Agents+Events tabs).

## How to think while writing

> *Every part of the UX needs to have a rationale considering the vision
> and the specificities of the backend.*

Concretely:

- **Rationale-first.** Before you add a panel, write one sentence on
*why this panel exists*. Tie it to data we actually emit (cite the
emit site by file:line) or a primitive we already ship (cite the
component file). If you can't justify a panel, drop it.
- **Per-class specificity.** A `MetricSeriesChart` for a `Trainer` run
is `train_loss + val_loss + lr`; for a `Beam` run it's `score histogram + top-k cutoff`; for a `Sweep` it doesn't make sense at all.
Don't reuse the same generic shape — pick the one that matches the
algorithm's data.
- **Exploit the inventory.** If the run has a `langfuse_url`, surface
it. If it has `hash_content`, color-code by it. If the agent has
`Parameter`s with `requires_grad`, expose their evolution. If the
algorithm has synthetic children with `parent_run_id`, link to them.
If a `Trace` was recorded, offer cassette replay. The more inventory
features you wire in, the more the dashboard becomes a *living* UI
for operad rather than a static log viewer.
- **Look at what's there before adding new components.**
`apps/frontend/src/components/charts/` has `FitnessCurve`,
`PopulationScatter`, `MutationHeatmap`, `OpSuccessTable`,
`GradientLog`, `TrainingLossCurve`, `LrScheduleCurve`,
`CheckpointTimeline`, `DriftTimeline`, `TrainingProgress`,
`BeamCandidateChart`, `ConvergenceCurve`, `IterationProgression`,
`SweepHeatmap`, `SweepBestCellCard`, `SweepCostTotalizer`,
`DebateRoundView`, `DebateTranscript`, `DebateConsensusTracker`,
`AgentGraph`, `MultiPromptDiff`, `OperatorRadar`, `MethodLeaderboard`,
`BenchmarkMatrix`, `CostVsQualityScatter`, `CurveOverlay`,
`PromptDriftDiff`. Read the file before assuming you need to build
something new.
- **Don't reuse the same shape twice.** If you reach for a generic
`MetaList` or a 2-col `PanelGrid` and it's the third one on the page,
that's a smell. Find a more specific layout.

## Hard rules

These are non-negotiable. Violating them will get the PR rejected.

1. **No backwards compatibility.** Delete the dead code. If you replace
  `RunsTable` with `RunTable`, the old `RunsTable` is gone, not aliased.
2. **No emoji in code or in shipped UI strings** (workspace policy).
3. **Match existing style.** Tabs/spaces, naming, file structure. If you
  would have done it differently, do it the existing way and move on.
4. **Surgical scope.** If you notice unrelated dead code or odd
  formatting, mention it in the PR body, do not fix it.
5. **Run the tests.** Before claiming done:
  ```bash
   cd apps/frontend && pnpm test --run
   uv run pytest apps/dashboard/tests/ -v
   uv run pytest tests/ -q  # only if you touched operad/
  ```
   Add new tests when your brief asks for them. The test plan in your
   brief is the floor, not the ceiling.
6. **Build the SPA.** `make build-frontend` must succeed. The dashboard
  serves a built bundle; if your TypeScript doesn't compile, the live
   `127.0.0.1:7860` is broken end-to-end.
7. **Use the curated palette.** Do not invent ad-hoc colors. Every
  chart series, sidebar dot, and table swatch resolves through
   `hashColor()` or `--qual-N`. The contract is in `00-CONTRACTS.md` §3.
8. **Always consult `00-CONTRACTS.md`** for any component prop, JSON
  layout shape, backend route, or shared type. If something is missing
   from the contracts, post an issue in your PR description, do not
   freelance.
9. **Cite file:line in your PR body.** When you write your handoff
  summary, every claim ("I removed the four-card Definition grid",
   "I switched algorithms to LayoutResolver") must point at the file
   and line range you changed. This is how the parent agent reviews
   your work without re-reading your diff.

## Soft rules (style guidance)

- **Density.** Tables tight (22-28px row height); panels generous
(12-16px inner padding around 200-280px tall content). Match
`tokens.css`.
- **Status iconography.** Running runs pulse (`StatusDot pulse`); errored
runs use `--color-err`; ended runs use the per-run color from
`hashColor()` (NOT just gray). This is the W&B identity-first move.
- **Empty states.** Use `EmptyState` (`apps/frontend/src/components/ui/empty-state.tsx`)
with a *specific* description. "no data" is not an empty state — "no
generations recorded yet — first emit lands at gen 1" is.
- **Loading states.** Use the existing skeleton pattern (`animate-pulse bg-bg-2`); do not inline spinners.
- **Markdown-aware text.** Where text fields are user-authored
(proposal/critique in Debate, prompt in TalkerReasoner, notes on a
run), render Markdown. Use the same renderer the I/O preview uses
(or a thin wrapper around `react-markdown`); ask if unsure.

## Coordination protocol

- **You work in your own git worktree.** Branch name in your brief.
- **Do not edit files outside your brief's "Files to touch" list.**
If your work needs an upstream change in `00-CONTRACTS.md` or another
brief's territory, **post a clarification request in your PR body and
pause** — do not edit shared territory unilaterally.
- **PR title:** `[dashboard-redesign/<brief-id>] <short summary>`.
- **PR body must include:**
  1. Brief ID and link to the brief file.
  2. Acceptance-criteria checklist (copy-paste from your brief, mark
    each item with file:line evidence).
  3. Test results.
  4. Screenshots for any visible UI change.
  5. Any contract violations or open questions surfaced during the work.

## A note on creativity vs rigor

Your brief contains a "Design alternatives" section with 2-3 options and
a recommendation. **You may pick a different option from the
recommendation if you can articulate why.** You may not invent a fourth
option without writing a one-paragraph rationale tied to the operad
inventory. Surprise me with a better option, but justify it.

The "Acceptance criteria" section is the rigor anchor. Your work is not
done until every item passes. If an item is impossible because the
backend cannot supply the data, ask before quietly dropping it.

## When you're done

Post the PR with the body shape above and stop. The parent agent will
review, request changes if needed, and merge. Do not start a new brief
unless asked.