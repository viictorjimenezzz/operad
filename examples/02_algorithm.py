"""Example 2 - algorithm: `TalkerReasoner` walks a user through a process.

Run modes:

    uv run python examples/02_algorithm.py --scripted
    uv run python examples/02_algorithm.py
    uv run python examples/02_algorithm.py --offline
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
)
from operad.core.config import Resilience, Sampling

from _config import local_config, server_reachable
from utils import (
    attach_dashboard,
    parse_dashboard_target,
    print_panel,
    print_rule,
    print_scenario_tree,
    print_talker_summary,
    print_talker_turn,
)

_SCRIPT = "02_algorithm"
DEFAULT_DASHBOARD = "127.0.0.1:7860"


BRANCH_SENIORITY = ScenarioNode(
    id="branch_seniority",
    title="Branch on seniority",
    prompt="Identify the user's seniority and pick the matching goals branch.",
    instructions=(
        "Use available_children to pick goals_junior, goals_mid, or "
        "goals_senior. If seniority is unclear, STAY and ask one question."
    ),
    children=[
        ScenarioNode(
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
        ),
        ScenarioNode(
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
        ),
        ScenarioNode(
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
    ],
)

PROCESS = ScenarioTree(
    name="Career-development intake",
    purpose=(
        "Help an ambitious individual contributor pick a development "
        "direction in five quick turns."
    ),
    root=ScenarioNode(
        id="greet",
        title="Greet and explain",
        prompt=(
            "Greet the user warmly and explain that this is a five-step "
            "intake to suggest a career-development direction."
        ),
        children=[
            ScenarioNode(
                id="collect_role",
                title="Collect current role",
                prompt="Ask the user about their current role and years of experience.",
                instructions="Advance once you have role + rough years of experience.",
                children=[BRANCH_SENIORITY],
            )
        ],
    )
)

SCRIPT: list[str] = [
    "Hi! I want to talk about my career.",
    "I'm a senior software engineer with about ten years of experience.",
    "I'm honestly torn between leadership tracks.",
    "I think I want to go staff-engineer, not management.",
    "Yes - I want depth in distributed systems and cross-org influence.",
    "Thanks, that helps a lot.",
]


async def _run_scripted(tr: TalkerReasoner) -> Transcript:
    print_rule("Stage 3 - scripted run")
    transcript = await tr.run(SCRIPT)
    for turn in transcript.turns:
        print_talker_turn(turn)
    return transcript


async def _run_repl(tr: TalkerReasoner) -> Transcript:
    print_rule("Stage 3 - interactive run")
    print("Type `quit` or `exit` to stop.")
    while not tr.finished:
        try:
            user_message = input("you> ").strip()
        except EOFError:
            break
        if not user_message:
            continue
        if user_message.lower() in {"quit", "exit"}:
            break
        turn = await tr.step(user_message)
        print_talker_turn(turn)

    return Transcript(
        process_name=PROCESS.name,
        turns=list(tr._history),
        final_node_id=tr._current_id,
        finished=tr.finished,
    )


async def main(args: argparse.Namespace) -> None:
    if args.offline:
        print(
            f"[{_SCRIPT}] --offline: this example needs a real LLM; "
            "exiting 0 as no-op."
        )
        return

    attached = False
    if args.dashboard is not None:
        attached = attach_dashboard(
            args.dashboard,
            open_browser=not args.no_open,
            default=DEFAULT_DASHBOARD,
        )

    cfg = local_config(
        sampling=Sampling(temperature=0.3, max_tokens=2048),
        resilience=Resilience(max_retries=2, backoff_base=0.5),
    )
    print(f"[{_SCRIPT}] backend={cfg.backend} host={cfg.host} model={cfg.model}")
    if not server_reachable(cfg.host or ""):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} - start llama-server",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print_rule("Stage 1 - scenario tree")
    print_scenario_tree(PROCESS)

    print_rule("Stage 2 - instantiate algorithm + abuild()")
    tr = TalkerReasoner(tree=PROCESS, max_turns=args.max_turns, config=cfg)
    await tr.abuild()
    print_panel(
        "TalkerReasoner",
        (
            f"process:       {PROCESS.name}\n"
            f"start node:    {tr._current_id}\n"
            f"max_turns:     {tr.max_turns}\n"
            f"reasoner:      {type(tr.reasoner).__name__} "
            f"[{tr.reasoner.input.__name__} -> {tr.reasoner.output.__name__}]\n"
            f"talker:        {type(tr.talker).__name__} "
            f"[{tr.talker.input.__name__} -> {tr.talker.output.__name__}]"
        ),
    )

    transcript = await (_run_scripted(tr) if args.scripted else _run_repl(tr))

    print_rule("Stage 4 - run summary")
    print_talker_summary(transcript)

    if attached:
        host, port = parse_dashboard_target(args.dashboard, default=DEFAULT_DASHBOARD)
        print(
            f"[dashboard] still live at http://{host}:{port}  "
            "(ctrl+c the dashboard server to stop)"
        )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--scripted",
        action="store_true",
        help="Run the fixed scripted conversation instead of interactive input().",
    )
    p.add_argument(
        "--max-turns",
        type=int,
        default=10,
        help="Safety cap for interactive mode.",
    )
    p.add_argument(
        "--offline",
        action="store_true",
        help="No-op for verify.sh; this example needs a real LLM to run.",
    )
    p.add_argument(
        "--dashboard",
        nargs="?",
        const=DEFAULT_DASHBOARD,
        default=None,
        metavar="HOST:PORT",
        help="Attach to a running operad-dashboard server (default 127.0.0.1:7860).",
    )
    p.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the browser when --dashboard attaches.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
