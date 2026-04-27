# 09 — Algorithm: TalkerReasoner

**Stage:** 3 (parallel; depends on Briefs 01, 02, 14, 15)
**Branch:** `dashboard-redesign/09-algo-talker`
**Subagent group:** D (Algos-creative)

## Goal

TalkerReasoner is a graph-walking conversational agent: a `ScenarioTree`
defines stages of a process, and on each user message the algorithm
chooses to *stay*, *advance*, *branch*, or *finish*. The view should
make this graph walk visible — the **Tree** tab shows the scenario
graph with the walked path highlighted and the current node pulsing;
the **Transcript** tab shows the conversation as the user/assistant
exchanged it; the **Decisions** tab shows the navigation logic.

Q6 = interactive tree (use `@xyflow/react`).

## Read first

- `operad/algorithms/talker_reasoner.py` — `TalkerReasoner.run()` lines
  437-486; `_one_turn` lines 490-562. Event emit sites:
  - `algo_start` (lines 441-452): currently `{process, start_node_id, max_turns, scripted_messages}`
  - per-turn `iteration phase="navigate"` (lines 496-504): `{iter_index, phase, current_node_id}`
  - per-turn `iteration phase="speak"` (lines 523-533): `{iter_index, phase, decision_kind, from_node_id, to_node_id}`
  - `algo_end` (lines 466-476): `{turns, finished, final_node_id}`
- The `ScenarioTree`, `ScenarioNode`, `NavigationDecision`, `Turn`,
  `Transcript` schemas at `operad/algorithms/talker_reasoner.py:41-338`.
- The synthetic children: each turn invokes `ScenarioNavigator` then
  `Assistant`. Both are leaf agents with their own `agent_event`
  records; the `Assistant`'s output is the actual user-facing message.
- `00-CONTRACTS.md` §2.5 (`ScenarioTreeView`), §5.1 (algo_start
  payload extension to ship the tree).
- `INVENTORY.md` §7 (TalkerReasoner mention as a planned algorithm).

## Backend dependency

This brief **requires** the algo_start payload extension in Brief 14.
Specifically:

```python
algo_start.payload["tree"] = {
  "name": str,
  "purpose": str,
  "rootId": str,
  "nodes": [{"id": str, "title": str, "prompt": str,
             "terminal": bool, "parent_id": str | None}, ...]
}
```

Without this extension, the Tree tab cannot render anything more than
a "tree unavailable" empty state. Brief 14 ships this; this brief
**must** wait for it before merge (Stage 4 convergence handles the
sequencing).

## Files to touch

Create:

- `apps/frontend/src/layouts/talker_reasoner.json` (Brief 02 created
  the skeleton; this brief fills the per-algo tabs).
- `apps/frontend/src/components/algorithms/talker_reasoner/` (new
  folder):
  - `index.ts`
  - `registry.tsx`
  - `talker-detail-overview.tsx`
  - `scenario-tree-view.tsx` (per `00-CONTRACTS.md` §2.5)
  - `transcript-view.tsx`
  - `decisions-view.tsx`
- `apps/frontend/src/components/algorithms/registry.tsx` — add the
  talker_reasoner sub-registry to the spread.

## Tab structure

```
[ Overview ] [ Tree ] [ Transcript ] [ Decisions ] [ Agents ] [ Events ] [ Graph ]
```

### Overview

```
─── status strip ─────────────────────────────────
[ ● ended | live ]   process: "Career-development intake"
turns 6 / 10   final node: recap_senior   finished ✓

─── tree mini (small) ────────────────────────────
A static, read-only thumbnail of the ScenarioTree with the walked path
highlighted. Click → switches to Tree tab.

─── transcript mini (last 3 turns, last assistant message) ─
turn 6: user "..."  → advance to recap_senior
        assistant "Great, here's a summary of your senior path..."
[ View full transcript → /algorithms/:runId?tab=transcript ]

─── purpose card ─────────────────────────────────
Markdown render of process.purpose.
```

### Tree

The headline tab. `ScenarioTreeView` (per `00-CONTRACTS.md` §2.5):

```
─── interactive tree (xyflow, top-down dagre) ────
Each node is a card showing { title, prompt preview, terminal? }.
The walked path is highlighted (thick edges, accent color).
The current node pulses (cmd: `--color-live`).
Nodes with multiple turns show a chip "(2 turns)".
Click a node:
  - selects it
  - scrolls the Decisions tab's table to the matching turn
  - opens a side panel showing all turns spent in that node

─── side panel (slides from right when a node is selected) ─
Node: branch_seniority
Title: "Branch on seniority"
Prompt: "Identify the user's seniority and pick the matching goals branch."
Visited: 1 turn (#3)
[ Open turn 3 → ?turn=3 ]
```

Implementation hints:
- `@xyflow/react` is already a dep.
- Layout via `dagre` (already a dep — `AgentFlowGraph` uses it).
- Nodes: small cards (~180px wide). Use the curated palette for path
  highlighting (e.g., `--qual-7` for "walked", muted gray for "not
  walked", `--color-live` for "current" with a pulse).
- Edges: arrowheads point parent→child.
- Pan/zoom enabled; minimap for >15 nodes.

### Transcript

Chat-shaped view:

```
─── topic: process name ──────────────────────────

[user]    Hi! I want to talk about my career.                  [turn 1]
                                                          → advance to collect_role

[assist]  Welcome! Let's start with your role and years…       [turn 1]

[user]    I'm a senior software engineer with about 10 years.  [turn 2]
                                                          → advance to branch_seniority

[assist]  Got it. Let's focus on a senior development direction… [turn 2]

…
```

Each row is the user/assistant text rendered Markdown. Decision pills
on the right edge show `stay/advance/branch/finish` colored. URL
`?turn=N` pins a turn (auto-scroll).

The user_message is sourced from `iteration.payload` directly (it's in
the speak event metadata). The assistant_message comes from the
synthetic child of the `Assistant` agent for that turn — fetch
`/runs/:runId/children`, find children with `agent_path` matching
`Assistant`, sort by start time, align by index.

### Decisions

A `RunTable` of turns with columns:

```
[●][Turn][From node][Decision][To node][Latency][Reasoner cost][Assistant cost][Total]
```

Decision column color-coded by kind:
- `stay` → muted
- `advance` → ok green
- `branch` → accent
- `finish` → strong (final)

Click a row → URL `?turn=N` and switches to the Transcript tab.

### Agents

Universal tab. Default `groupBy: "hash"` collapses all
`ScenarioNavigator` calls into one row and all `Assistant` calls into
another. The user sees: "Reasoner ×6 invocations, Assistant ×6
invocations". Each is one click away.

### Graph

The `AgentFlowGraph` of the underlying composite (Reasoner, Assistant
inside the TalkerReasoner). For a single-leaf reasoner, the Brief 01
single-node fallback applies.

## Design alternatives

### A1: Tree shape

- **(a)** `@xyflow/react` interactive (recommended; per Q6).
- **(b)** Static SVG tree (simpler, fewer deps). Deferred.
- **(c)** Mermaid graph. **Reject:** Mermaid auto-layout for trees is
  worse than dagre.

### A2: Transcript style

- **(a)** Chat bubbles (recommended).
- **(b)** Threaded list with code-style "user>" / "assist>". Less
  modern; reject for the user-facing transcripts.

### A3: How to source assistant text

- **(a)** Synthetic children of `Assistant` (recommended; the actual
  source of truth).
- **(b)** Add the assistant message to the speak event payload.
  Possible (Brief 14 could add it), but couples the algorithm to its
  display. **Reject** unless (a) proves slow.

### A4: When the tree has 50+ nodes

- **(a)** Add a "fit walked path" button that auto-frames the walked
  path (recommended).
- **(b)** Default to "fit walked" on load. Better default; do this.

## Acceptance criteria

- [ ] Tabs render:
  `Overview · Tree · Transcript · Decisions · Agents · Events · Graph`.
- [ ] Tree tab uses `@xyflow/react` with dagre top-down layout, walked
  path highlighted, current node pulsing (when `live`), pan/zoom, mini-
  map.
- [ ] Tree node click → side panel + URL deep-link.
- [ ] Transcript tab renders user/assistant messages as Markdown chat
  bubbles, with decision pills.
- [ ] Decisions tab renders a RunTable with color-coded decision
  column; click → switches to Transcript with `?turn=N`.
- [ ] Overview's tree mini and transcript mini link to their tabs.
- [ ] When the algo_start payload's `tree` field is missing (e.g.,
  legacy runs prior to Brief 14), Tree tab shows
  `EmptyState title="tree payload missing — re-run with the latest TalkerReasoner"`.
- [ ] `pnpm test --run` green.

## Test plan

- **Unit:** `scenario-tree-view.test.tsx` (rendering, walked path,
  selection); `transcript-view.test.tsx`; `decisions-view.test.tsx`.
- **Layout schema:** `talker_reasoner.json` validates.
- **Manual smoke:** `examples/02_algorithm.py --scripted` generates a
  TalkerReasoner run; verify all tabs.

## Out of scope

- Backend payload extension (Brief 14).
- Universal tabs (Brief 15).
- Other algorithms (Briefs 05-08, 10-13, 16).

## Hand-off

PR body with checklist + a marquee screenshot of the Tree tab (this
view is the most visually distinctive new piece in the redesign).
