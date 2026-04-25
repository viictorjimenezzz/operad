"""Example 2 — algorithm: `TalkerReasoner` walks a user through a process.

`TalkerReasoner` (added in `operad/algorithms/talker_reasoner.py`)
couples a typed **navigator Reasoner** with a **voice Reasoner**. Both
are vanilla `Reasoner(...)` instances installed at class-level — the
example does not subclass anything; it just passes `config=` through to
the algorithm constructor.

The algorithm is fed a four-stage **career-counselling intake** tree:

    root: greet & explain
      └─ collect_role     (single child → advance)
           └─ branch_seniority
                ├─ junior  → goals_junior   → recap (terminal)
                ├─ mid     → goals_mid      → recap (terminal)
                └─ senior  → goals_senior   → recap (terminal)

A scripted user (`SCRIPT`) walks the algorithm through the senior path,
clarifying once at the branch node so we exercise `stay` as well as
`advance`, `branch`, and `finish`.

Run modes:

    uv run python examples/02_talker_reasoner_intake.py            # hits the local llama-server
    uv run python examples/02_talker_reasoner_intake.py --offline  # no-op for verify.sh
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from operad.algorithms import (
    ScenarioNode,
    ScenarioTree,
    TalkerReasoner,
    Transcript,
    Turn,
)
from operad.core.config import Resilience, Sampling

from _config import local_config, server_reachable

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _RICH = True
except ImportError:
    _RICH = False


_SCRIPT = "02_talker_reasoner_intake"


# ---------------------------------------------------------------------------
# Scenario tree — the "career intake" process.
# ---------------------------------------------------------------------------


def _intake_tree() -> ScenarioTree:
    junior = ScenarioNode(
        id="goals_junior",
        title="Goals (junior)",
        prompt="Explore one or two beginner-friendly skill goals.",
        instructions="Advance only if the user names at least one concrete goal.",
        children=[
            ScenarioNode(
                id="recap_junior",
                title="Recap (junior)",
                prompt="Summarise the chosen junior path and offer next steps.",
                terminal=True,
            )
        ],
    )
    mid = ScenarioNode(
        id="goals_mid",
        title="Goals (mid-level)",
        prompt="Probe whether the user wants depth (specialist) or breadth (lead).",
        instructions="Advance once the user picks specialist or lead.",
        children=[
            ScenarioNode(
                id="recap_mid",
                title="Recap (mid)",
                prompt="Summarise the mid-level path and offer next steps.",
                terminal=True,
            )
        ],
    )
    senior = ScenarioNode(
        id="goals_senior",
        title="Goals (senior)",
        prompt=(
            "Discuss strategic moves: staff-eng, founder, or executive track. "
            "Probe risk tolerance and time horizon."
        ),
        instructions=(
            "If the user is ambiguous about which track, STAY and ask one "
            "clarifying question. Advance once the choice is clear."
        ),
        children=[
            ScenarioNode(
                id="recap_senior",
                title="Recap (senior)",
                prompt="Summarise the chosen senior path and offer next steps.",
                terminal=True,
            )
        ],
    )

    branch = ScenarioNode(
        id="branch_seniority",
        title="Branch on seniority",
        prompt="Identify the user's seniority and pick the matching goals branch.",
        instructions=(
            "Use available_children to pick goals_junior, goals_mid, or "
            "goals_senior. If seniority is unclear, STAY and ask one question."
        ),
        children=[junior, mid, senior],
    )
    collect = ScenarioNode(
        id="collect_role",
        title="Collect current role",
        prompt="Ask the user about their current role and years of experience.",
        instructions="Advance once you have role + rough years of experience.",
        children=[branch],
    )
    root = ScenarioNode(
        id="greet",
        title="Greet & explain",
        prompt=(
            "Greet the user warmly and explain that this is a five-step "
            "intake to suggest a career-development direction."
        ),
        children=[collect],
    )
    return ScenarioTree(
        name="Career-development intake",
        purpose=(
            "Help an ambitious individual contributor pick a development "
            "direction in five quick turns."
        ),
        root=root,
    )


SCRIPT: list[str] = [
    "Hi! I want to talk about my career.",                                 # greet → collect_role
    "I'm a senior software engineer with about ten years of experience.",  # collect_role → branch_seniority
    "I'm honestly torn between leadership tracks.",                        # branch ambiguous → STAY
    "I think I want to go staff-engineer, not management.",                # branch → goals_senior
    "Yes — I want depth in distributed systems and cross-org influence.",  # goals_senior → recap_senior
    "Thanks, that helps a lot.",                                           # recap_senior → finish
]


# ---------------------------------------------------------------------------
# Pretty terminal output.
# ---------------------------------------------------------------------------


def _rule(title: str) -> None:
    if _RICH:
        Console(width=120).rule(f"[bold cyan]{title}")
    else:
        bar = "═" * (len(title) + 6)
        print(f"\n{bar}\n   {title}\n{bar}")


def _panel(title: str, body: str) -> None:
    if _RICH:
        Console(width=120).print(Panel(body, title=title, border_style="cyan"))
    else:
        bar = "─" * 60
        print(f"\n{bar}\n{title}\n{bar}\n{body}\n{bar}")


def _print_tree(tree: ScenarioTree) -> None:
    if not _RICH:
        def walk(n: ScenarioNode, depth: int = 0) -> None:
            bullet = "T" if n.terminal else "."
            print(f"{'  ' * depth}{bullet} [{n.id}] {n.title}")
            for c in n.children:
                walk(c, depth + 1)
        walk(tree.root)
        return
    from rich.tree import Tree as RichTree

    rich_tree = RichTree(f"[bold]{tree.name}[/]")
    rich_tree.add(f"[dim]{tree.purpose}[/]")

    def add(parent, n: ScenarioNode) -> None:
        marker = "[red]●[/]" if n.terminal else "[green]○[/]"
        node = parent.add(f"{marker} [bold]{n.title}[/]  [dim]({n.id})[/]")
        if n.instructions:
            node.add(f"[italic dim]instructions: {n.instructions}[/]")
        for c in n.children:
            add(node, c)

    add(rich_tree, tree.root)
    Console(width=120).print(rich_tree)


def _print_turn(turn: Turn) -> None:
    decision = turn.decision
    color_by_kind = {
        "stay": "yellow",
        "advance": "green",
        "branch": "blue",
        "finish": "magenta",
    }
    kind_color = color_by_kind.get(decision.kind, "white")
    if _RICH:
        body = (
            f"[bold]user[/]      → {turn.user_message}\n"
            f"[dim]from[/]      → {turn.from_node_id}\n"
            f"[bold {kind_color}]decision[/] → {decision.kind}"
            f"{(' → ' + decision.branch_to) if decision.branch_to else ''}"
            f"  [dim]({decision.rationale})[/]\n"
            f"[dim]to[/]        → {turn.to_node_id}"
            f"{'  [bold magenta]TERMINAL[/]' if turn.is_terminal else ''}\n"
            f"[bold]assistant[/] ← {turn.assistant_message}"
        )
        Console(width=120).print(
            Panel(body, title=f"turn {turn.turn_index}", border_style=kind_color)
        )
    else:
        print(f"\n--- turn {turn.turn_index} ---")
        print(f"user      → {turn.user_message}")
        print(f"from      → {turn.from_node_id}")
        print(
            f"decision  → {decision.kind}"
            + (f" → {decision.branch_to}" if decision.branch_to else "")
            + f"  ({decision.rationale})"
        )
        print(
            f"to        → {turn.to_node_id}"
            + ("  TERMINAL" if turn.is_terminal else "")
        )
        print(f"assistant ← {turn.assistant_message}")


def _print_summary(transcript: Transcript) -> None:
    kinds: dict[str, int] = {}
    for t in transcript.turns:
        kinds[t.decision.kind] = kinds.get(t.decision.kind, 0) + 1
    if not _RICH:
        print("\nSummary:")
        print(f"  process:        {transcript.process_name}")
        print(f"  turns:          {len(transcript.turns)}")
        print(f"  decision_kinds: {kinds}")
        print(f"  final_node_id:  {transcript.final_node_id}")
        print(f"  finished:       {transcript.finished}")
        return
    table = Table(title="Decision histogram", border_style="cyan")
    table.add_column("kind", justify="left")
    table.add_column("count", justify="right")
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        table.add_row(k, str(v))
    Console(width=120).print(table)
    Console(width=120).print(
        Panel(
            (
                f"process:        {transcript.process_name}\n"
                f"turns:          {len(transcript.turns)}\n"
                f"final_node_id:  {transcript.final_node_id}\n"
                f"finished:       {transcript.finished}"
            ),
            title="Run summary",
            border_style="cyan",
        )
    )


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    if args.offline:
        print(
            f"[{_SCRIPT}] --offline: this example needs a real LLM; "
            "exiting 0 as no-op."
        )
        return

    cfg = local_config(
        sampling=Sampling(temperature=0.3, max_tokens=2048),
        resilience=Resilience(max_retries=2, backoff_base=0.5),
    )
    print(
        f"[{_SCRIPT}] backend={cfg.backend} host={cfg.host} model={cfg.model}"
    )
    if not server_reachable(cfg.host or ""):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} — start llama-server",
            file=sys.stderr,
        )
        raise SystemExit(1)

    tree = _intake_tree()

    _rule("Stage 1 — scenario tree")
    _print_tree(tree)

    _rule("Stage 2 — instantiate algorithm + abuild()")
    tr = TalkerReasoner(tree=tree, max_turns=10, config=cfg)
    await tr.abuild()
    _panel(
        "TalkerReasoner",
        (
            f"process:       {tree.name}\n"
            f"start node:    {tr._current_id}\n"
            f"max_turns:     {tr.max_turns}\n"
            f"reasoner:      {type(tr.reasoner).__name__} "
            f"[{tr.reasoner.input.__name__} → {tr.reasoner.output.__name__}]\n"
            f"talker:        {type(tr.talker).__name__} "
            f"[{tr.talker.input.__name__} → {tr.talker.output.__name__}]"
        ),
    )

    _rule("Stage 3 — scripted run")
    transcript = await tr.run(SCRIPT)
    for turn in transcript.turns:
        _print_turn(turn)

    _rule("Stage 4 — run summary")
    _print_summary(transcript)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--offline",
        action="store_true",
        help="No-op for verify.sh; this example needs a real LLM to run.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
