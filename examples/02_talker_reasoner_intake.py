"""Example 2 — algorithm: `TalkerReasoner` walks a user through a process.

`TalkerReasoner` (newly added under `operad/algorithms/`) couples a typed
**Reasoner** (the navigator) with a **Talker** (the voice). At every
turn the reasoner picks the next node in a `ScenarioTree`, the talker
produces the user-facing message, and the algorithm walks the tree
until a terminal node is reached.

The example feeds it a four-stage **career-counselling intake** tree:

    root: greet & explain
      └─ collect_role     (single child → advance)
           └─ branch_seniority
                ├─ junior  → goals_junior   → recap (terminal)
                ├─ mid     → goals_mid      → recap (terminal)
                └─ senior  → goals_senior   → recap (terminal)

A scripted user (`SCRIPT`) walks the algorithm through the senior path,
clarifying once on the goals node so we exercise the `stay` decision
branch as well as `advance`, `branch`, and `finish`.

Run modes:

    uv run python examples/02_talker_reasoner_intake.py            # offline (deterministic stubs)
    uv run python examples/02_talker_reasoner_intake.py --live     # live llama-server
    uv run python examples/02_talker_reasoner_intake.py --offline  # parity flag for verify.sh
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from operad import Configuration
from operad.algorithms import (
    NavigationDecision,
    ScenarioNode,
    ScenarioTree,
    TalkerReasoner,
    Transcript,
)
from operad.algorithms.talker_reasoner import (
    _NavigationReasoner,
    _UserFacingTalker,
    AssistantMessage,
    NavigationInput,
    TalkerInput,
)
from operad.core.config import Sampling

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _RICH = True
except ImportError:
    _RICH = False


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


# ---------------------------------------------------------------------------
# Scripted user — exercises stay/advance/branch/finish.
# ---------------------------------------------------------------------------


SCRIPT: list[str] = [
    "Hi! I want to talk about my career.",                              # greet → collect_role
    "I'm a senior software engineer with about ten years of experience.",  # collect_role → branch_seniority
    "I'm honestly torn between leadership tracks.",                     # branch ambiguous → STAY
    "I think I want to go staff-engineer, not management.",             # branch → goals_senior
    "Yes — I want depth in distributed systems and cross-org influence.",  # goals_senior → recap_senior
    "Thanks, that helps a lot.",                                        # recap_senior → finish
]


# ---------------------------------------------------------------------------
# Offline determinism: subclass the navigator + talker leaves.
# ---------------------------------------------------------------------------


_OFFLINE_CFG = Configuration(
    backend="llamacpp",
    host="127.0.0.1:0",
    model="offline-stub",
    sampling=Sampling(temperature=0.0, max_tokens=16),
)


def _classify_seniority(message: str) -> str | None:
    m = message.lower()
    if "junior" in m or ("years" in m and any(d in m for d in ("one", "two", "1", "2"))):
        return "goals_junior"
    if "mid" in m or "five" in m or "five years" in m:
        return "goals_mid"
    if "senior" in m or "ten" in m or "principal" in m or "staff" in m:
        return "goals_senior"
    return None


class _OfflineNavigator(_NavigationReasoner):
    async def forward(self, x: NavigationInput) -> NavigationDecision:  # type: ignore[override]
        # `abuild()` constructs the input via `model_construct` (no defaults),
        # so getattr-with-default keeps the trace-time call safe.
        node_id = getattr(x, "current_node_id", "")
        msg = getattr(x, "user_message", "")

        if node_id == "greet":
            return NavigationDecision(
                kind="advance",
                rationale="Greeting acknowledged; move to role collection.",
                next_message_brief=(
                    "Acknowledge the user warmly and ask about their current "
                    "role and roughly how many years of experience they have."
                ),
            )

        if node_id == "collect_role":
            if any(token in msg.lower() for token in ("engineer", "manager", "designer", "developer", "year")):
                return NavigationDecision(
                    kind="advance",
                    rationale="User supplied role + experience; advance to branch.",
                    next_message_brief=(
                        "Briefly reflect what you heard about their role and "
                        "years; then ask which leadership track interests them."
                    ),
                )
            return NavigationDecision(
                kind="stay",
                rationale="Role/experience not yet supplied.",
                next_message_brief="Ask once more for their role and years of experience.",
            )

        if node_id == "branch_seniority":
            if "torn" in msg.lower() or "not sure" in msg.lower() or "between" in msg.lower():
                return NavigationDecision(
                    kind="stay",
                    rationale="User is ambiguous about which track; clarify.",
                    next_message_brief=(
                        "Acknowledge the dilemma and ask one focused question: "
                        "which sounds more energising right now, individual-"
                        "contributor depth or people leadership?"
                    ),
                )
            target = _classify_seniority(msg) or "goals_senior"
            return NavigationDecision(
                kind="branch",
                branch_to=target,
                rationale=f"User pattern matched {target} branch.",
                next_message_brief=(
                    f"Confirm the chosen track ({target.removeprefix('goals_')}) "
                    "and ask about specific goals on it."
                ),
            )

        if node_id.startswith("goals_"):
            if "yes" in msg.lower() or "want" in msg.lower() or "depth" in msg.lower():
                return NavigationDecision(
                    kind="advance",
                    rationale="User named concrete goals; advance to recap.",
                    next_message_brief=(
                        "Mirror back the named goals and tee up a recap of "
                        "the path you would recommend."
                    ),
                )
            return NavigationDecision(
                kind="stay",
                rationale="No concrete goals yet; ask for one.",
                next_message_brief="Ask the user to name one concrete near-term goal.",
            )

        if node_id.startswith("recap_"):
            return NavigationDecision(
                kind="finish",
                rationale="User acknowledged the recap; close the conversation.",
                next_message_brief=(
                    "Acknowledge the close warmly, summarise the chosen path "
                    "in one sentence, and offer one concrete external resource."
                ),
            )
        return NavigationDecision(
            kind="stay",
            rationale="Unknown node; default to stay.",
            next_message_brief="Ask the user to clarify what they need.",
        )


class _OfflineTalker(_UserFacingTalker):
    async def forward(self, x: TalkerInput) -> AssistantMessage:  # type: ignore[override]
        # Deterministic warm response keyed on (target_node, decision_kind).
        node_id = getattr(x, "target_node_id", "")
        if getattr(x, "is_terminal", False):
            return AssistantMessage(
                text=(
                    "Glad we got there! Your path: pursue staff-engineer-track "
                    "depth in distributed systems while building cross-org "
                    "influence through technical writing. A great next step is "
                    "to shadow a current staff engineer for a sprint and "
                    "compare notes. Anything else I can help with?"
                )
            )
        if node_id == "collect_role":
            return AssistantMessage(
                text=(
                    "Welcome! I'll guide you through a five-step intake to "
                    "suggest a career-development direction. To start: what is "
                    "your current role, and roughly how many years of "
                    "experience do you have?"
                )
            )
        if node_id == "branch_seniority":
            if getattr(x, "decision_kind", "") == "stay":
                return AssistantMessage(
                    text=(
                        "That dilemma is very common at your level. To help me "
                        "narrow this down: which sounds more energising right "
                        "now — individual-contributor depth (staff-engineer "
                        "track) or people leadership (manager/director)?"
                    )
                )
            return AssistantMessage(
                text=(
                    "Got it — senior IC with ~ten years. Which leadership "
                    "track sounds most appealing: staff-engineer, founder, or "
                    "executive?"
                )
            )
        if node_id == "goals_senior":
            if getattr(x, "decision_kind", "") == "stay":
                return AssistantMessage(
                    text=(
                        "Makes sense. To make this concrete, can you name one "
                        "specific area you want depth in over the next year?"
                    )
                )
            return AssistantMessage(
                text=(
                    "Great — staff-engineer track it is. What concrete goals "
                    "do you want to anchor on this year? Depth in a specific "
                    "domain? Cross-org influence? Both?"
                )
            )
        if node_id.startswith("recap_"):
            return AssistantMessage(
                text=(
                    "To recap: senior IC, ~ten years, staff-engineer track, "
                    "with depth in distributed systems and cross-org "
                    "influence as the two anchors. Sound right?"
                )
            )
        return AssistantMessage(text="Could you tell me a bit more?")


def _install_offline_stubs() -> None:
    """Patch `TalkerReasoner` class-level defaults with offline shims."""
    TalkerReasoner.reasoner = _OfflineNavigator(
        config=_OFFLINE_CFG,
        input=NavigationInput,
        output=NavigationDecision,
    )
    TalkerReasoner.talker = _OfflineTalker(
        config=_OFFLINE_CFG,
        input=TalkerInput,
        output=AssistantMessage,
    )


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


def _print_turn(turn) -> None:
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
        title = f"turn {turn.turn_index}"
        Console(width=120).print(Panel(body, title=title, border_style=kind_color))
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
    if not _RICH:
        kinds: dict[str, int] = {}
        for t in transcript.turns:
            kinds[t.decision.kind] = kinds.get(t.decision.kind, 0) + 1
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
    kinds: dict[str, int] = {}
    for t in transcript.turns:
        kinds[t.decision.kind] = kinds.get(t.decision.kind, 0) + 1
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
    if args.live:
        from _config import local_config, server_reachable

        cfg = local_config(sampling=Sampling(temperature=0.3, max_tokens=512))
        if not server_reachable(cfg.host or ""):
            print(
                f"[02_talker_reasoner] cannot reach {cfg.host} — "
                "start llama-server or drop --live",
                file=sys.stderr,
            )
            raise SystemExit(1)
        # In live mode the class-level defaults are the real reasoning leaves.
        TalkerReasoner.reasoner = _NavigationReasoner(
            config=cfg, input=NavigationInput, output=NavigationDecision
        )
        TalkerReasoner.talker = _UserFacingTalker(
            config=cfg, input=TalkerInput, output=AssistantMessage
        )
    else:
        _install_offline_stubs()

    tree = _intake_tree()

    _rule("Stage 1 — scenario tree")
    _print_tree(tree)

    _rule("Stage 2 — instantiate algorithm + abuild()")
    tr = TalkerReasoner(tree=tree, max_turns=10)
    await tr.abuild()
    _panel(
        "TalkerReasoner",
        (
            f"process:       {tree.name}\n"
            f"start node:    {tr._current_id}\n"
            f"max_turns:     {tr.max_turns}\n"
            f"reasoner:      {type(tr.reasoner).__name__} [{tr.reasoner.input.__name__} → {tr.reasoner.output.__name__}]\n"
            f"talker:        {type(tr.talker).__name__} [{tr.talker.input.__name__} → {tr.talker.output.__name__}]"
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
        "--live",
        action="store_true",
        help="Hit a real llama-server (requires OPERAD_LLAMACPP_HOST/_MODEL).",
    )
    p.add_argument(
        "--offline",
        action="store_true",
        help="Parity flag for verify.sh; the example runs offline by default.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
