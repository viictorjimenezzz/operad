# Dashboard redesign v2 — agent guidelines

You are part of a planned, multi-wave redesign of the operad dashboard. The
previous attempt landed structure but missed identity, density, per-algorithm
specificity, and the parameter-evolution story. This wave fixes that.

Each agent is assigned exactly one brief (file `<seq>-<par>-<name>.md` in this
folder). Read this guideline in full before opening any code.

## Reading order before you write a single line

1. `**/Users/viictorjimenezzz/Documents/operad/AGENTS.md`** — repo-wide
   working rules. The "Surgical Changes" rule is binding: every changed line
   must trace directly to your brief. The "Codebase Invariants" apply.
2. `**/Users/viictorjimenezzz/Documents/operad/METAPROMPT.md`** — line 36 in
   particular: *DO NOT KEEP BACKWARDS COMPATIBILITY*. Wherever the current
   API/UX gets in the way, replace it.
3. `**/Users/viictorjimenezzz/Documents/operad/INVENTORY.md`** — treat as a
   feature menu. Cross-reference §13 (observers/Langfuse), §17 (cassette),
   §19 (typed mutations), §20 (reproducibility hashes), §21 (Parameter
   family + Trainer + tape + backward), §22 (PromptTraceback).
4. `00-contracts.md` (this folder) — shared types, palette, density tokens,
   JSON layout element types, backend route shapes. **Conform to it.** If
   your brief and the contracts disagree, post a question and stop. Never
   freelance shared-territory edits.
5. **Your brief.** Read twice. The "Files to touch", "Acceptance criteria",
   and "Test plan" sections are binding.
6. **Adjacent briefs** only when your brief flags a dependency.

## How to think while writing

> *Every part of the UX needs a rationale tied to data we actually emit.*

- **Rationale-first.** Before adding a panel, write one sentence on *why
  this panel exists*. Cite the emit site (`file:line`) or the component
  you're reusing. If you can't justify it, drop it.
- **Per-class specificity.** A `MetricSeriesChart` for a `Trainer` is not
  the same as for a `Sweep`. Don't reuse the same generic shape; pick the
  one that matches the data.
- **Identity-first colors.** Every chart series, table swatch, sidebar
  dot, and drawer rail resolves through `hashColor()` (per-instance) or
  `paletteIndex()` (per-class). Never invent ad-hoc colors.
- **Look at what's there.** The components in
  `apps/frontend/src/components/charts/`, `components/ui/`, and
  `components/agent-view/` are dense and reusable. Read the file before
  building something new.
- **Don't reuse the same shape twice.** Three `PanelGrid cols={2}` in a
  row is a smell.

## Hard rules

These are non-negotiable; violating them gets the PR rejected.

1. **No backwards compatibility.** Delete dead code. If you replace
   component X with component Y, the old X is gone — not aliased.
2. **No emoji in code or shipped UI strings.** Workspace policy.
3. **Match existing style.** Tabs/spaces, naming, file structure. If you
   would have done it differently, do it the existing way and move on.
4. **Surgical scope.** Every changed line must trace to your brief. If
   you notice unrelated dead code or odd formatting, mention it in the
   PR body — do not fix it.
5. **Run the tests.** Before claiming done:
   ```bash
   cd apps/frontend && pnpm test --run
   uv run pytest apps/dashboard/tests/ -v
   uv run pytest tests/ -q   # only if you touched operad/
   make build-frontend       # the SPA bundle must compile
   ```
   The test plan in your brief is the floor, not the ceiling.
6. **Use the curated palette.** Identity colors via `hashColor()`,
   per-class via `paletteIndex()`. The contract is in `00-contracts.md`
   §3.
7. **Monitor only.** The dashboard never mutates state. No buttons that
   call `agent_invoke`, no replay actions, no edit dialogs. If your
   brief asks for a button, it's a bug — stop and ask.
8. **Cite file:line in your PR body.** Every claim should point at the
   file and lines you changed.

## Soft rules (style guidance)

- **Density.** Tables are tight (22-28px rows). Panels are generous on
  the inside (`--panel-pad-y/--panel-pad-x` from `tokens.css`), thin on
  the outside (single divider, no `rounded-lg border` wrapping every
  inner block).
- **Status iconography.** Running runs pulse (`StatusDot pulse`); errored
  runs use `--color-err`; ended runs use the per-run `hashColor()` (NOT
  gray). This is the W&B identity-first move.
- **Empty states.** Use `EmptyState` with a *specific* description.
  "no data" is not an empty state — "no generations recorded yet — first
  emit lands at gen 1" is.
- **Loading states.** Use the existing skeleton pattern
  (`animate-pulse bg-bg-2`); do not inline spinners.
- **Markdown-aware text.** Where text is user-authored
  (proposal/critique in Debate, prompt in TalkerReasoner, notes on a
  run, gradient messages), render Markdown via `MarkdownView`.

## Coordination protocol

- **You work in your own git worktree.** Branch name in your brief:
  `dashboard/<task-name>`.
- **Do not edit files outside your brief's "Files to touch" list.** If
  your work needs an upstream change in `00-contracts.md` or another
  brief's territory, post a clarification question in your PR body and
  pause — do not unilaterally edit shared territory.
- **PR title:** `[dashboard/<seq>-<par>] <short summary>`.
- **PR body must include:**
  1. Brief ID and link to the brief file.
  2. Acceptance-criteria checklist, each item with file:line evidence.
  3. Test results (commands + outcomes).
  4. Screenshots or terminal output for any visible UI change.
  5. Contract violations or open questions surfaced during the work.

## How the wave engine treats this folder

- Briefs share a sequence number iff they can run in parallel.
- All sequence-N briefs must merge before sequence-(N+1) briefs start.
- Within a sequence, briefs touch disjoint files (or shared files only
  through additive registries like JSON layouts and the component
  registry — see `00-contracts.md` §13).

## A note on creativity vs rigor

Each brief contains a "Design alternatives" section with 2-3 options and
a recommendation. **You may pick a different option from the
recommendation if you can articulate why.** You may not invent a fourth
option without a one-paragraph rationale tied to the operad inventory.
Surprise me with a better option, but justify it.

The "Acceptance criteria" section is the rigor anchor. Your work is not
done until every item passes. If an item is impossible because the
backend cannot supply the data, ask before quietly dropping it.

Each brief also contains a **"Stretch goals"** section — opportunities
the parent agent flagged but did not require. You are encouraged to take
them on if your scope allows. Do not skip the required acceptance
criteria to chase a stretch goal.

## When you're done

Post the PR with the body shape above and stop. The parent agent will
review, request changes if needed, and merge. Do not start a new brief
unless asked.
