"""Example 5 - dashboard algorithm gallery.

This script runs the algorithm shapes that have dedicated dashboard
layouts but are not already covered by examples/01..04:

* Beam
* Sweep
* Debate
* SelfRefine
* AutoResearcher
* VerifierAgent

Run modes:

    uv run python examples/05_algorithm_gallery.py
    uv run python examples/05_algorithm_gallery.py --only beam
    uv run python examples/05_algorithm_gallery.py --dashboard --no-open
    uv run python examples/05_algorithm_gallery.py --offline
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from typing import Any

from operad import Configuration, Example
from operad.agents import (
    Critic,
    DebateCritic,
    Proposer,
    Reasoner,
    Reflector,
    Retriever,
    Synthesizer,
    VerifierAgent,
)
from operad.agents.debate.schemas import DebateTopic
from operad.agents.reasoning.schemas import (
    Answer,
    Candidate as JudgeCandidate,
    Hit,
    Query,
    Score,
    Task,
)
from operad.algorithms import (
    AutoResearcher,
    Beam,
    Debate,
    RefineInput,
    ResearchContext,
    ResearchInput,
    ResearchPlan,
    SelfRefine,
    Sweep,
)
from operad.core.config import Resilience, Sampling
from operad.runtime import set_limit
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import Event, registry

from _config import local_config, server_reachable
from utils import (
    attach_dashboard,
    parse_dashboard_target,
    print_panel,
    print_rule,
)


_SCRIPT = "05_algorithm_gallery"
DEFAULT_DASHBOARD = "127.0.0.1:7860"
_LOCAL_BACKENDS = {"llamacpp", "lmstudio", "ollama"}
_CHOICES = ("beam", "sweep", "debate", "selfrefine", "autoresearcher", "verifier")


class _RunIdCollector:
    """Collect top-level algorithm run ids for the final dashboard index."""

    def __init__(self) -> None:
        self.run_ids: dict[str, list[str]] = defaultdict(list)

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent):
            return
        if event.kind != "algo_start":
            return
        runs = self.run_ids[event.algorithm_path]
        if event.run_id and event.run_id not in runs:
            runs.append(event.run_id)

    def body(self) -> str:
        if not self.run_ids:
            return "(no algorithm runs captured)"
        lines: list[str] = []
        for name in sorted(self.run_ids):
            ids = ", ".join(self.run_ids[name])
            lines.append(f"{name}: {ids}")
        return "\n".join(lines)


def _cfg_for(
    cfg: Configuration,
    *,
    temperature: float,
    max_tokens: int = 1024,
) -> Configuration:
    return cfg.model_copy(
        deep=True,
        update={"sampling": Sampling(temperature=temperature, max_tokens=max_tokens)},
    )


def _answer_text(value: Any) -> str:
    answer = getattr(value, "answer", None)
    if isinstance(answer, str):
        return answer
    text = getattr(value, "text", None)
    if isinstance(text, str):
        return text
    return str(value)


async def _run_beam(cfg: Configuration) -> None:
    print_rule("Beam - candidates + prune")
    beam: Beam[Task, Answer] = Beam(
        context="Dashboard example: compare short implementation strategies.",
        criteria="Prefer concrete, low-risk answers with clear tradeoffs.",
        n=3,
        top_k=2,
    )
    beam.generator = Reasoner(
        config=_cfg_for(cfg, temperature=0.95),
        input=Task,
        output=Answer,
        role="You propose distinct engineering rollout strategies.",
        task=(
            "Answer with one concrete rollout option and its rationale. "
            "Prefer a specific release mechanic such as feature flags, "
            "canary cohorts, opt-in beta, shadow mode, or phased team rollout."
        ),
        rules=(
            "Keep the final answer under 120 words.",
            "Name one tradeoff explicitly.",
            "Include one concrete inspection or rollback mechanism.",
            "Avoid generic 'roll out gradually' wording unless the rollout stages are explicit.",
        ),
    )
    beam.judge = Critic(
        config=_cfg_for(cfg, temperature=0.0),
        task=(
            "Score the rollout answer from 0.0 to 1.0. Reward concrete mechanics, "
            "inspection, rollback, and a named tradeoff. Penalize generic or incomplete plans."
        ),
        rules=(
            "Use the full scoring range; do not assign 1.0 unless the answer "
            "is specific, complete, and directly inspectable.",
            "0.85-0.95: concrete rollout with inspection or rollback and a tradeoff.",
            "0.55-0.75: plausible rollout but missing a key operational detail.",
            "0.0-0.45: vague, risky, or not aligned with an internal dashboard feature.",
            "Keep the rationale under two sentences.",
        ),
        examples=(
            Example[JudgeCandidate, Score](
                input=JudgeCandidate(
                    input=Task(
                        goal="Choose a rollout strategy for a small dashboard feature.",
                        context=(
                            "The feature is internal, low risk, "
                            "and should be easy to inspect."
                        ),
                    ),
                    output=Answer(
                        reasoning=(
                            "Feature flags allow a small group to try the page "
                            "while the team watches traces."
                        ),
                        answer=(
                            "Ship behind a feature flag to five maintainers, "
                            "inspect Langfuse traces and dashboard errors daily, "
                            "then raise exposure after two clean days. "
                            "Tradeoff: needs flag cleanup."
                        ),
                    ),
                ),
                output=Score(
                    score=0.92,
                    rationale=(
                        "Specific rollout mechanics, inspection, rollback control, "
                        "and a concrete tradeoff."
                    ),
                ),
            ),
            Example[JudgeCandidate, Score](
                input=JudgeCandidate(
                    input=Task(
                        goal="Choose a rollout strategy for a small dashboard feature.",
                        context=(
                            "The feature is internal, low risk, "
                            "and should be easy to inspect."
                        ),
                    ),
                    output=Answer(
                        reasoning="Gradual release is generally safe.",
                        answer=(
                            "Roll it out slowly to internal users and gather feedback. "
                            "Tradeoff: slower adoption."
                        ),
                    ),
                ),
                output=Score(
                    score=0.58,
                    rationale=(
                        "Plausible but generic; it lacks concrete inspection "
                        "and rollback details."
                    ),
                ),
            ),
        ),
    )

    top = await beam.run(
        Task(
            goal="Choose a rollout strategy for a small dashboard feature.",
            context="The feature is internal, low risk, and should be easy to inspect.",
        )
    )
    print_panel(
        "Beam top candidates",
        "\n\n".join(f"#{i}: {_answer_text(candidate)}" for i, candidate in enumerate(top)),
    )


async def _run_sweep(cfg: Configuration) -> None:
    print_rule("Sweep - 2x2 parameter grid")
    seed = Reasoner(
        config=_cfg_for(cfg, temperature=0.2),
        input=Task,
        output=Answer,
        role="You are a concise release-note writer.",
        task="Write a terse release note with one concrete user impact.",
        rules=("Use plain language.",),
    )
    await seed.abuild()

    sweep: Sweep[Task, Answer] = Sweep(
        {
            "task": [
                "Write a terse release note with one concrete user impact.",
                "Write a release note with a risk note and one user impact.",
            ],
            "config.sampling.temperature": [0.0, 0.6],
        },
        context="Dashboard example: scored grid for cells, axes, child runs, and cost.",
        concurrency=2,
    )
    sweep.seed = seed
    sweep.judge = Critic(config=_cfg_for(cfg, temperature=0.0))
    report = await sweep.run(
        Task(
            goal="Summarize a new dashboard tab for algorithm runs.",
            context="Audience: maintainers deciding whether to inspect a trace.",
        )
    )
    print_panel(
        "Sweep cells",
        "\n".join(
            f"#{i}: score={cell.score if cell.score is not None else '-'} "
            f"{cell.parameters} -> {_answer_text(cell.output)[:120]}"
            for i, cell in enumerate(report.cells)
        ),
    )


async def _run_debate(cfg: Configuration) -> None:
    print_rule("Debate - proposals, critiques, synthesis")
    debate = Debate(
        context="Dashboard example: multiple rounds with distinct proposer stances.",
        rounds=3,
    )
    debate.proposers = [
        Proposer(
            config=_cfg_for(cfg, temperature=0.8),
            context="Argue for a narrow first release.",
        ),
        Proposer(
            config=_cfg_for(cfg, temperature=0.8),
            context="Argue for a broader integrated release.",
        ),
        Proposer(
            config=_cfg_for(cfg, temperature=0.8),
            context="Argue for a staged release that expands coverage over time.",
        ),
    ]
    debate.critic = DebateCritic(config=_cfg_for(cfg, temperature=0.0))
    debate.synthesizer = Synthesizer(config=_cfg_for(cfg, temperature=0.2))

    answer = await debate.run(
        DebateTopic(
            topic="Should a dashboard example suite prioritize breadth or speed?",
            details=(
                "The suite is for maintainers checking UI layouts after algorithm runs. "
                "It should expose enough variation for score and agreement charts to move."
            ),
        )
    )
    print_panel("Debate synthesis", _answer_text(answer))


async def _run_selfrefine(cfg: Configuration) -> None:
    print_rule("SelfRefine - generate, reflect, refine")
    refine = SelfRefine(
        context="Dashboard example: force the full two-iteration ladder.",
        max_iter=2,
        stop_when=lambda state: False,
    )
    refine.generator = Reasoner(
        config=_cfg_for(cfg, temperature=0.5),
        input=Task,
        output=Answer,
        role="You draft concise dashboard QA guidance.",
        task="Draft a compact answer with a concrete checklist.",
        rules=("Keep it practical.",),
    )
    refine.reflector = Reflector(config=_cfg_for(cfg, temperature=0.0))
    refine.refiner = Reasoner(
        config=_cfg_for(cfg, temperature=0.4),
        input=RefineInput,
        output=Answer,
        role="You revise drafts using critique.",
        task="Rewrite the candidate answer to address the critique directly.",
        rules=("Preserve useful concrete details.",),
    )

    answer = await refine.run(
        Task(
            goal="How should a maintainer inspect a new dashboard example run?",
            context="Mention event tabs, algorithm-specific tabs, and run ids.",
        )
    )
    print_panel("SelfRefine final answer", _answer_text(answer))


async def _run_auto_researcher(cfg: Configuration) -> None:
    print_rule("AutoResearcher - plan, retrieve, attempts, best")

    async def lookup(query: Query) -> list[Hit]:
        text = query.text.lower()
        corpus = [
            Hit(
                text=(
                    "Dashboard algorithm layouts are selected by algorithm_path and "
                    "show algorithm-specific tabs plus shared Agents and Events tabs."
                ),
                score=0.94,
                source="dashboard-readme",
            ),
            Hit(
                text=(
                    "Run summaries expose iterations, candidates, rounds, "
                    "generations, parameter snapshots, and terminal scores."
                ),
                score=0.88,
                source="run-summary",
            ),
            Hit(
                text="Live examples attach to the dashboard by forwarding runtime observer events.",
                score=0.82,
                source="examples-readme",
            ),
        ]
        if "trainer" in text:
            corpus.append(
                Hit(
                    text="Trainer runs emit batch_end, epoch_end, gradient_applied, and PromptDrift events.",
                    score=0.9,
                    source="trainer-events",
                )
            )
        return corpus[: max(1, query.top_k)]

    researcher = AutoResearcher(n=2, max_iter=1, threshold=1.1)
    researcher.planner = PlannerLike(
        config=_cfg_for(cfg, temperature=0.2),
        input=ResearchContext,
        output=ResearchPlan,
    )
    researcher.retriever = await Retriever(lookup=lookup).abuild()
    researcher.reasoner = Reasoner(
        config=_cfg_for(cfg, temperature=0.4),
        input=ResearchInput,
        output=Answer,
        role="You synthesize dashboard inspection guidance from retrieved notes.",
        task="Answer the research request using the hits and any prior reflection.",
        rules=(
            "Use retrieved evidence only.",
            "Mention which dashboard tab or rail the maintainer should inspect.",
        ),
    )
    researcher.critic = Critic(config=_cfg_for(cfg, temperature=0.0))
    researcher.reflector = Reflector(config=_cfg_for(cfg, temperature=0.0))

    answer = await researcher.run(
        ResearchContext(
            goal="What should a maintainer verify after running the algorithm gallery example?",
            domain="developer tooling",
            audience="operad maintainers",
            constraints="Keep the answer brief.",
        )
    )
    print_panel("AutoResearcher best answer", _answer_text(answer))


class PlannerLike(Reasoner):
    """Reasoner-shaped planner with a clearer prompt for ResearchPlan."""

    role = "You plan one focused retrieval query for dashboard QA."
    task = "Convert the research context into one specific search query."
    rules = (
        "Set query to a compact phrase.",
        "Preserve dashboard and algorithm terminology from the request.",
    )


async def _run_verifier(cfg: Configuration) -> None:
    print_rule("VerifierAgent - generate until verified")
    verifier = VerifierAgent(
        config=_cfg_for(cfg, temperature=0.3),
        threshold=1.1,
        max_iter=2,
    )
    await verifier.abuild()
    answer = (
        await verifier(
            Task(
                goal="Give one acceptance criterion for dashboard example coverage.",
                context="The verifier threshold is intentionally unreachable so the dashboard sees two iterations.",
            )
        )
    ).response
    print_panel("Verifier final candidate", _answer_text(answer))


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
        sampling=Sampling(temperature=0.4, max_tokens=1024),
        resilience=Resilience(max_retries=2, backoff_base=0.5, timeout=180.0),
    )
    print(f"[{_SCRIPT}] backend={cfg.backend} host={cfg.host} model={cfg.model}")
    if cfg.backend in _LOCAL_BACKENDS and not server_reachable(cfg.host or ""):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} - start llama-server",
            file=sys.stderr,
        )
        raise SystemExit(1)
    set_limit(backend=cfg.backend, host=cfg.host, concurrency=4)

    selected = list(_CHOICES if args.only == "all" else (args.only,))
    print_panel("Selected algorithms", ", ".join(selected))

    collector = _RunIdCollector()
    registry.register(collector)
    try:
        for name in selected:
            if name == "beam":
                await _run_beam(cfg)
            elif name == "sweep":
                await _run_sweep(cfg)
            elif name == "debate":
                await _run_debate(cfg)
            elif name == "selfrefine":
                await _run_selfrefine(cfg)
            elif name == "autoresearcher":
                await _run_auto_researcher(cfg)
            elif name == "verifier":
                await _run_verifier(cfg)
    finally:
        registry.unregister(collector)

    print_rule("Dashboard run ids")
    print_panel("Algorithm runs", collector.body())
    if attached:
        host, port = parse_dashboard_target(args.dashboard, default=DEFAULT_DASHBOARD)
        print(
            f"[dashboard] still live at http://{host}:{port}  "
            "(ctrl+c the dashboard server to stop)"
        )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--only",
        choices=(*_CHOICES, "all"),
        default="all",
        help="Run one algorithm family or the full gallery.",
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
