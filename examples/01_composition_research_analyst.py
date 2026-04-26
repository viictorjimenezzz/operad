"""Example 1 — composition: a research analyst built from existing components.

A single `await agent(x)` over four nested layers, every leaf a vanilla
component from `operad/agents/` instantiated directly with role/task
kwargs (no subclasses):

    ResearchRequest
      └─ Pipeline (top-level)
           ├─ Planner          [ResearchRequest → ResearchPlan]
           ├─ Parallel × 3     [ResearchPlan → _PerspectiveBundle]
           │     ├─ biology   Pipeline(Reasoner → ReAct → Reasoner)
           │     ├─ policy    Pipeline(Reasoner → ReAct → Reasoner)
           │     └─ economic  Pipeline(Reasoner → ReAct → Reasoner)
           └─ Reasoner         [_PerspectiveBundle → ResearchReport]

Every typed handoff is checked symbolically at `build()` time before a
token is generated. The example prints the Mermaid graph and the
envelope hashes.

Run modes:

    uv run python examples/01_composition_research_analyst.py            # hits the local llama-server
    uv run python examples/01_composition_research_analyst.py --offline  # no-op for verify.sh

Configure the backend via `_config.py` (defaults: `127.0.0.1:9000`,
`google/gemma-4-e2b`); override with `OPERAD_LLAMACPP_HOST` and
`OPERAD_LLAMACPP_MODEL`.
"""

from __future__ import annotations

import argparse
import asyncio
import socket
import sys
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from operad import Configuration, Pipeline
from operad.agents import Parallel, Planner, ReAct, Reasoner
from operad.agents.reasoning.schemas import Answer, Task
from operad.core.config import Resilience, Sampling
from operad.core.graph import to_mermaid

from _config import local_config, server_reachable

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.tree import Tree

    _RICH = True
except ImportError:
    _RICH = False


_SCRIPT = "01_composition_research_analyst"
DEFAULT_DASHBOARD = "127.0.0.1:7860"


# ---------------------------------------------------------------------------
# Domain schemas — typed edges between the composite stages.
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    """Top-level input: the research question + audience hint."""

    question: str = Field(description="The research question to answer.")
    audience: str = Field(
        default="a curious general reader",
        description="Who the final report is for; sets register and depth.",
    )


class ResearchPlan(BaseModel):
    """Planner output: per-perspective sub-questions."""

    biology_question: str = Field(description="Sub-question for the biology angle.")
    policy_question: str = Field(description="Sub-question for the policy angle.")
    economic_question: str = Field(description="Sub-question for the economic angle.")


class BranchView(BaseModel):
    """One perspective's investigated answer (output of one Parallel branch)."""

    perspective: str = Field(description="biology | policy | economic")
    sub_question: str = Field(description="The sub-question this branch attacked.")
    reasoning: str = Field(description="The branch's chain-of-thought.")
    answer: str = Field(description="The branch's committed answer.")


class _PerspectiveBundle(BaseModel):
    """Three branch views packaged for the editor."""

    biology: BranchView = Field(description="Biology perspective.")
    policy: BranchView = Field(description="Policy perspective.")
    economic: BranchView = Field(description="Economic perspective.")


class ResearchReport(BaseModel):
    """Top-level output: the synthesised final report."""

    headline: str = Field(description="One-sentence headline answer.")
    reasoning: str = Field(description="Why the headline is the right call.")


_PerspectiveBundle.model_rebuild()


# ---------------------------------------------------------------------------
# Composite assembly — every leaf is a direct `Planner(...)` / `Reasoner(...)`
# / `ReAct(...)` instance with role/task/rules passed as kwargs. No subclasses.
# ---------------------------------------------------------------------------


def _branch(*, perspective: str, attr: str, cfg: Configuration) -> Pipeline:
    """One perspective branch: framer → ReAct → packer.

    `ReAct` itself is a four-leaf composite (Reasoner, Actor, Extractor,
    Evaluator), so each branch contributes 1 + 4 + 1 = 6 leaves under
    one composite.
    """
    framer = Reasoner(
        config=cfg,
        input=ResearchPlan,
        output=Task,
        role=f"You frame {perspective} research tasks.",
        task=(
            f"Read the full ResearchPlan; pick out `{attr}`; restate it as "
            f"a Task whose `goal` is the sub-question and whose `context` "
            f"says you are reasoning from the {perspective} perspective."
        ),
        rules=(
            f"`goal` MUST be `{attr}` from the plan, verbatim.",
            f"`context` MUST mention 'the {perspective} perspective'.",
        ),
    )
    packer = Reasoner(
        config=cfg,
        input=Answer,
        output=BranchView,
        role=f"You package the {perspective} branch.",
        task=(
            f"Wrap the Answer into a BranchView. Set `perspective` to "
            f"'{perspective}'. Carry `reasoning` and `answer` through "
            f"unchanged. Set `sub_question` to a one-line restatement of "
            f"what was investigated."
        ),
        rules=(
            f"`perspective` MUST be exactly '{perspective}'.",
            "Do NOT shorten or paraphrase `reasoning` or `answer`.",
        ),
    )
    return Pipeline(
        framer,
        ReAct(config=cfg),
        packer,
        input=ResearchPlan,
        output=BranchView,
    )


def _combine(views: dict[str, BaseModel]) -> _PerspectiveBundle:
    return _PerspectiveBundle(
        biology=views["biology"],  # type: ignore[arg-type]
        policy=views["policy"],  # type: ignore[arg-type]
        economic=views["economic"],  # type: ignore[arg-type]
    )


def assemble(*, cfg: Configuration) -> Pipeline:
    planner = Planner(
        config=cfg,
        input=ResearchRequest,
        output=ResearchPlan,
        role=(
            "You are a research lead who decomposes a question into one "
            "focused sub-question per analytic perspective: biology, "
            "policy, economic."
        ),
        task=(
            "Read the request and write three independent sub-questions — "
            "one per perspective. Each must be answerable on its own."
        ),
        rules=(
            "Each sub-question must use the same language as the request.",
            "Do not duplicate the original question verbatim.",
            "Sub-questions must be independent: answering one must not require the others.",
        ),
    )
    branches = {
        "biology": _branch(perspective="biology", attr="biology_question", cfg=cfg),
        "policy": _branch(perspective="policy", attr="policy_question", cfg=cfg),
        "economic": _branch(perspective="economic", attr="economic_question", cfg=cfg),
    }
    parallel = Parallel(
        branches,
        input=ResearchPlan,
        output=_PerspectiveBundle,
        combine=_combine,
    )
    editor = Reasoner(
        config=cfg,
        input=_PerspectiveBundle,
        output=ResearchReport,
        role=(
            "You are the senior editor who turns three research perspectives "
            "into one decisive report."
        ),
        task=(
            "Read all three BranchViews. Commit to a single headline and "
            "write a short reasoning paragraph that synthesises the three "
            "perspectives into one decisive position."
        ),
        rules=(
            "The headline is one sentence and commits to a position.",
            "The reasoning paragraph references each perspective at least implicitly.",
        ),
    )
    return Pipeline(
        planner,
        parallel,
        editor,
        input=ResearchRequest,
        output=ResearchReport,
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


def _print_report(report: ResearchReport) -> None:
    if not _RICH:
        print(f"headline:  {report.headline}")
        print(f"reasoning: {report.reasoning}")
        return
    tree = Tree(f"[bold green]headline[/]  {report.headline}")
    tree.add(f"[dim]reasoning[/]  {report.reasoning}")
    Console(width=120).print(tree)


def _parse_dashboard_target(value: str) -> tuple[str, int]:
    raw = value or DEFAULT_DASHBOARD
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 7860
    return host, port


def _server_up(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _attach_dashboard(target: str, *, open_browser: bool = True) -> bool:
    host, port = _parse_dashboard_target(target)
    if not _server_up(host, port):
        print(
            f"[dashboard] no server at {host}:{port} — "
            "start one with `operad-dashboard --port 7860` then re-run with --dashboard"
        )
        return False
    from operad.dashboard import attach

    attach(host=host, port=port)
    url = f"http://{host}:{port}"
    print(f"[dashboard] attached → {url}")
    if open_browser:
        try:
            import webbrowser

            webbrowser.open_new_tab(url)
        except Exception:
            pass
    return True


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
    attached = False
    if args.dashboard is not None:
        attached = _attach_dashboard(args.dashboard, open_browser=not args.no_open)

    cfg = local_config(
        sampling=Sampling(temperature=0.4, max_tokens=2048),
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

    _rule("Stage 1 — assemble nested composite")
    agent = assemble(cfg=cfg)
    await agent.abuild()

    n_nodes = len(agent._graph.nodes) if agent._graph else 0
    n_edges = len(agent._graph.edges) if agent._graph else 0
    _panel(
        "Composite shape",
        (
            "top-level Pipeline — 3 stages\n"
            "  stage_0  Planner            [ResearchRequest → ResearchPlan]\n"
            "  stage_1  Parallel × 3       [ResearchPlan → _PerspectiveBundle]\n"
            "             ├─ biology   Pipeline(Reasoner → ReAct → Reasoner)\n"
            "             ├─ policy    Pipeline(Reasoner → ReAct → Reasoner)\n"
            "             └─ economic  Pipeline(Reasoner → ReAct → Reasoner)\n"
            "  stage_2  Reasoner (editor)  [_PerspectiveBundle → ResearchReport]\n"
            f"\nbuilt graph: {n_nodes} nodes, {n_edges} typed edges"
        ),
    )

    _rule("Stage 2 — Mermaid graph (typed handoffs)")
    _panel("Mermaid", to_mermaid(agent._graph))

    _rule("Stage 3 — invoke once")
    request = ResearchRequest(
        question=args.question,
        audience="a thoughtful general reader",
    )
    _panel(
        "Input",
        f"question: {request.question}\naudience: {request.audience}",
    )

    out = await agent(request)

    _rule("Stage 4 — final ResearchReport")
    _print_report(out.response)

    _panel(
        "Envelope (reproducibility fingerprint)",
        (
            f"run_id:             {out.run_id}\n"
            f"agent_path:         {out.agent_path}\n"
            f"latency_ms:         {out.latency_ms:.1f}\n"
            f"hash_input:         {out.hash_input}\n"
            f"hash_graph:         {out.hash_graph}\n"
            f"hash_prompt:        {out.hash_prompt}\n"
            f"hash_output_schema: {out.hash_output_schema}\n"
            f"agent.hash_content: {agent.hash_content}"
        ),
    )
    if attached:
        host, port = _parse_dashboard_target(args.dashboard)
        print(
            f"[dashboard] still live at http://{host}:{port}  "
            "(ctrl+c the dashboard server to stop)"
        )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--offline",
        action="store_true",
        help="No-op for verify.sh; this example needs a real LLM to run.",
    )
    p.add_argument(
        "--question",
        default="Why are honeybee colonies collapsing in temperate regions?",
        help="The research question to feed the composite.",
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
