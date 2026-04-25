"""Example 1 — composition: a research analyst built from nested components.

Single `await agent(x)`; what's inside is a four-layer typed nesting where
every leaf is an existing component from `operad/agents/`:

    ResearchRequest
      └─ Pipeline (top-level)
           ├─ ResearchPlanner [ResearchRequest → ResearchPlan]
           ├─ Parallel        [ResearchPlan → _PerspectiveBundle]
           │     ├─ branch "biology":   Pipeline
           │     │      ├─ _BiologyFramer [ResearchPlan → Task]
           │     │      ├─ ReAct          [Task → Answer]              ← 4-leaf composite
           │     │      └─ _BiologyPacker [Answer → BranchView]
           │     ├─ branch "policy":    Pipeline (same shape)
           │     └─ branch "economic":  Pipeline (same shape)
           └─ _ResearchEditor [_PerspectiveBundle → ResearchReport]

That is **20 leaves under 4 nested composites**, every typed handoff
checked symbolically at `build()` time before a token is generated. The
example prints the Mermaid graph, runs the agent once, and prints the
output envelope (`run_id`, `latency_ms`, all five reproducibility hashes).

Run modes:

    uv run python examples/01_composition_research_analyst.py            # offline (FakeLeaf-style stubs)
    uv run python examples/01_composition_research_analyst.py --live     # hits a local llama-server
    uv run python examples/01_composition_research_analyst.py --offline  # parity flag for verify.sh
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import BaseModel, Field

from operad import Configuration, Pipeline
from operad.agents import (
    Actor,
    Evaluator,
    Extractor,
    Parallel,
    Planner,
    ReAct,
    Reasoner,
)
from operad.agents.reasoning.schemas import (
    Action,
    Answer,
    Observation,
    Task,
    Thought,
)
from operad.core.config import Sampling
from operad.core.graph import to_mermaid

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.tree import Tree

    _RICH = True
except ImportError:
    _RICH = False


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
    perspectives: list[BranchView] = Field(
        default_factory=list,
        description="Per-perspective views the editor weighed.",
    )


# `from __future__ import annotations` defers field-type resolution to
# `model_rebuild`; calling it explicitly here keeps the schema valid when
# the module is loaded out of order (e.g. via `importlib.exec_module`).
_PerspectiveBundle.model_rebuild()
ResearchReport.model_rebuild()


# ---------------------------------------------------------------------------
# Custom typed leaves (subclassed from existing reasoning components).
# ---------------------------------------------------------------------------


class ResearchPlanner(Planner):
    """Planner specialised to produce one sub-question per perspective."""

    input = ResearchRequest
    output = ResearchPlan
    role = (
        "You are a research lead who decomposes a question into one focused "
        "sub-question per analytic perspective: biology, policy, economic."
    )
    task = (
        "Read the request and write three independent sub-questions — one "
        "per perspective. Each must be answerable on its own."
    )
    rules = (
        "Each sub-question must use the same language as the request.",
        "Do not duplicate the original question verbatim.",
        "Sub-questions must be independent — answering one must not require the others.",
    )


class _BranchFramer(Reasoner):
    """Translate a `ResearchPlan` into a `Task` for one perspective.

    Three subclasses (`_BiologyFramer`, `_PolicyFramer`, `_EconomicFramer`)
    each pick out their slice of the plan; this base captures the shared
    contract so `build()` traces the typed handoff cleanly.
    """

    input = ResearchPlan
    output = Task
    rules = (
        "Set goal to the perspective's sub-question verbatim.",
        "Set context to a one-sentence framing that names the perspective.",
    )


class _BiologyFramer(_BranchFramer):
    role = "You frame biology research tasks."
    task = "Extract `biology_question` from the plan and frame it as a Task."


class _PolicyFramer(_BranchFramer):
    role = "You frame policy research tasks."
    task = "Extract `policy_question` from the plan and frame it as a Task."


class _EconomicFramer(_BranchFramer):
    role = "You frame economic research tasks."
    task = "Extract `economic_question` from the plan and frame it as a Task."


class _BranchPacker(Reasoner):
    """Wrap a `Task → Answer` chain into a perspective-tagged `BranchView`.

    Three subclasses each tag the result with a fixed `perspective` literal.
    """

    input = Answer
    output = BranchView
    rules = (
        "Set perspective to the value named in the role.",
        "Set sub_question to a one-line restatement of what was investigated.",
        "Carry the Answer's reasoning and answer fields through unchanged.",
    )


class _BiologyPacker(_BranchPacker):
    role = "You package the biology branch's findings; perspective is 'biology'."
    task = "Wrap the Answer into a BranchView tagged biology."


class _PolicyPacker(_BranchPacker):
    role = "You package the policy branch's findings; perspective is 'policy'."
    task = "Wrap the Answer into a BranchView tagged policy."


class _EconomicPacker(_BranchPacker):
    role = "You package the economic branch's findings; perspective is 'economic'."
    task = "Wrap the Answer into a BranchView tagged economic."


class _ResearchEditor(Reasoner):
    """Final stage: bundle of three views → ResearchReport."""

    input = _PerspectiveBundle
    output = ResearchReport
    role = (
        "You are the senior editor who turns three research perspectives "
        "into one decisive report."
    )
    task = (
        "Read all three BranchViews. Commit to a single headline and write "
        "a short reasoning paragraph. Carry every BranchView through into "
        "the report's `perspectives` list unchanged."
    )
    rules = (
        "The headline is one sentence and commits to a position.",
        "The reasoning paragraph references each perspective at least implicitly.",
        "Do NOT drop or reorder the perspectives — they are evidence.",
    )


# ---------------------------------------------------------------------------
# Composite assembly.
# ---------------------------------------------------------------------------


def _branch(
    *,
    framer_cls: type[_BranchFramer],
    packer_cls: type[_BranchPacker],
    cfg: Configuration | None,
) -> Pipeline:
    """One perspective branch: framer → ReAct → packer.

    `ReAct` itself is a four-leaf composite (Reasoner, Actor, Extractor,
    Evaluator), so each branch contributes 1 + 4 + 1 = 6 leaves under
    one composite.
    """
    return Pipeline(
        framer_cls(config=cfg, input=ResearchPlan, output=Task),
        ReAct(config=cfg),
        packer_cls(config=cfg, input=Answer, output=BranchView),
        input=ResearchPlan,
        output=BranchView,
    )


def _combine(views: dict[str, BaseModel]) -> _PerspectiveBundle:
    return _PerspectiveBundle(
        biology=views["biology"],  # type: ignore[arg-type]
        policy=views["policy"],  # type: ignore[arg-type]
        economic=views["economic"],  # type: ignore[arg-type]
    )


def assemble(*, cfg: Configuration | None) -> Pipeline:
    """Build the full nested composite."""
    branches = {
        "biology": _branch(framer_cls=_BiologyFramer, packer_cls=_BiologyPacker, cfg=cfg),
        "policy": _branch(framer_cls=_PolicyFramer, packer_cls=_PolicyPacker, cfg=cfg),
        "economic": _branch(framer_cls=_EconomicFramer, packer_cls=_EconomicPacker, cfg=cfg),
    }
    parallel = Parallel(
        branches,
        input=ResearchPlan,
        output=_PerspectiveBundle,
        combine=_combine,
    )
    return Pipeline(
        ResearchPlanner(
            config=cfg,
            input=ResearchRequest,
            output=ResearchPlan,
        ),
        parallel,
        _ResearchEditor(
            config=cfg,
            input=_PerspectiveBundle,
            output=ResearchReport,
        ),
        input=ResearchRequest,
        output=ResearchReport,
    )


# ---------------------------------------------------------------------------
# Offline determinism: subclass the leaves and override `forward`.
# When --live is not passed, we install offline shims for every leaf so the
# whole composite runs without contacting any LLM.
# ---------------------------------------------------------------------------


_OFFLINE_CFG = Configuration(
    backend="llamacpp",
    host="127.0.0.1:0",
    model="offline-stub",
    sampling=Sampling(temperature=0.0, max_tokens=16),
)


class _OfflinePlanner(ResearchPlanner):
    async def forward(self, x: ResearchRequest) -> ResearchPlan:  # type: ignore[override]
        q = x.question.rstrip("? ")
        return ResearchPlan(
            biology_question=f"What biological mechanisms underlie {q}?",
            policy_question=f"What policy levers exist to address {q}?",
            economic_question=f"What economic incentives shape {q}?",
        )


def _make_offline_framer(perspective: str) -> type[_BranchFramer]:
    class _F(_BranchFramer):
        input = ResearchPlan
        output = Task
        role = f"You frame {perspective} research tasks."
        task = f"Extract the {perspective}_question and frame it as a Task."

        async def forward(self, x: ResearchPlan) -> Task:  # type: ignore[override]
            sub = getattr(x, f"{perspective}_question")
            return Task(
                goal=sub,
                context=f"You are reasoning from the {perspective} perspective.",
            )

    _F.__name__ = f"_Offline{perspective.capitalize()}Framer"
    return _F


_OFFLINE_DRIVERS = {
    "biology": "neonicotinoid pesticide exposure compounding with Varroa-mite-driven immunosuppression",
    "policy": "fragmented pesticide regulation across jurisdictions and weak honey-import labeling",
    "economic": "below-cost pollination contracts that push commercial keepers to over-stock unhealthy hives",
}


def _perspective_of(text: str) -> str:
    """Extract the perspective tag the framer planted in `Task.context`."""
    if "from the " in text and " perspective" in text:
        return text.split("from the ", 1)[-1].split(" perspective", 1)[0]
    return "general"


def _perspective_from_action(details: str) -> str:
    for p in _OFFLINE_DRIVERS:
        if f"[{p}]" in details:
            return p
    return "general"


class _OfflineReasoner(Reasoner):
    async def forward(self, x: Task) -> Thought:  # type: ignore[override]
        perspective = _perspective_of(x.context)
        return Thought(
            reasoning=(
                f"From the {perspective} angle, the question decomposes into "
                f"upstream causes, immediate consequences, and feedback loops. "
                f"The single highest-leverage factor is the {perspective}-specific "
                f"upstream driver."
            ),
            next_action=f"[{perspective}] name the {perspective}-specific driver",
        )


class _OfflineActor(Actor):
    async def forward(self, x: Thought) -> Action:  # type: ignore[override]
        return Action(
            name="name_driver",
            details=x.next_action,
        )


class _OfflineExtractor(Extractor):
    async def forward(self, x: Action) -> Observation:  # type: ignore[override]
        perspective = _perspective_from_action(x.details)
        driver = _OFFLINE_DRIVERS.get(perspective, "the dominant upstream driver")
        return Observation(
            result=f"[{perspective}] driver identified: {driver}",
            success=True,
        )


class _OfflineEvaluator(Evaluator):
    async def forward(self, x: Observation) -> Answer:  # type: ignore[override]
        if "] driver identified: " in x.result:
            perspective, driver = x.result.split("] driver identified: ", 1)
            perspective = perspective.lstrip("[")
        else:
            perspective, driver = "general", "the dominant upstream driver"
        return Answer(
            reasoning=(
                f"Working through the {perspective} chain: upstream → "
                f"observed collapse → feedback. The driver that explains "
                f"the most variance is {driver}."
            ),
            answer=f"[{perspective}] {driver}",
        )


class _OfflineReAct(ReAct):
    """ReAct subclass that swaps in offline child leaves.

    Composite `forward` is unchanged — only the four child leaves are
    replaced with deterministic shims so the example runs without an LLM.
    """

    def __init__(self, *, config: Configuration | None) -> None:
        from operad.core.agent import Agent

        Agent.__init__(self, config=None, input=Task, output=Answer)
        self.reasoner = _OfflineReasoner(config=config, input=Task, output=Thought)
        self.actor = _OfflineActor(config=config, input=Thought, output=Action)
        self.extractor = _OfflineExtractor(
            config=config, input=Action, output=Observation
        )
        self.evaluator = _OfflineEvaluator(
            config=config, input=Observation, output=Answer
        )


def _make_offline_packer(
    perspective: str, sub_question_pattern: str
) -> type[_BranchPacker]:
    class _P(_BranchPacker):
        input = Answer
        output = BranchView
        role = f"You package the {perspective} branch."
        task = f"Wrap the Answer as a {perspective}-tagged BranchView."

        async def forward(self, x: Answer) -> BranchView:  # type: ignore[override]
            # Strip the "[perspective]" tag the offline evaluator planted.
            clean_answer = x.answer
            if clean_answer.startswith(f"[{perspective}] "):
                clean_answer = clean_answer.removeprefix(f"[{perspective}] ")
            return BranchView(
                perspective=perspective,
                sub_question=sub_question_pattern,
                reasoning=x.reasoning,
                answer=clean_answer,
            )

    _P.__name__ = f"_Offline{perspective.capitalize()}Packer"
    return _P


class _OfflineEditor(_ResearchEditor):
    async def forward(self, x: _PerspectiveBundle) -> ResearchReport:  # type: ignore[override]
        views = [x.biology, x.policy, x.economic]
        headline = (
            "The collapse is multi-causal: a biological stressor, a "
            "regulatory gap, and an economic squeeze each contribute "
            "independently and reinforce one another."
        )
        reasoning = (
            "All three perspectives surfaced a distinct driver. The "
            "biology branch flagged a chemical-and-pathogen interaction; "
            "the policy branch flagged regulatory fragmentation; the "
            "economic branch flagged contract pricing. Because the "
            "drivers act through different channels, no single intervention "
            "will resolve the collapse — a coordinated response across all "
            "three layers is required."
        )
        return ResearchReport(
            headline=headline,
            reasoning=reasoning,
            perspectives=views,
        )


def _install_offline_stubs(question: str) -> None:
    """Replace live leaf classes with offline shims at module level."""
    g = globals()
    g["ResearchPlanner"] = _OfflinePlanner
    g["_BiologyFramer"] = _make_offline_framer("biology")
    g["_PolicyFramer"] = _make_offline_framer("policy")
    g["_EconomicFramer"] = _make_offline_framer("economic")
    g["ReAct"] = _OfflineReAct
    q = question.rstrip("? ")
    g["_BiologyPacker"] = _make_offline_packer(
        "biology", f"What biological mechanisms underlie {q}?"
    )
    g["_PolicyPacker"] = _make_offline_packer(
        "policy", f"What policy levers exist to address {q}?"
    )
    g["_EconomicPacker"] = _make_offline_packer(
        "economic", f"What economic incentives shape {q}?"
    )
    g["_ResearchEditor"] = _OfflineEditor


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
        for v in report.perspectives:
            print(f"  ├── [{v.perspective}] {v.answer}")
            print(f"  │   reasoning: {v.reasoning}")
        return
    tree = Tree(f"[bold green]headline[/]  {report.headline}")
    tree.add(f"[dim]reasoning[/]  {report.reasoning}")
    branch = tree.add("[bold]perspectives[/]")
    for v in report.perspectives:
        node = branch.add(f"[cyan]{v.perspective}[/]")
        node.add(f"[bold]sub-question[/] {v.sub_question}")
        node.add(f"[bold]reasoning[/]    {v.reasoning}")
        node.add(f"[bold]answer[/]       {v.answer}")
    Console(width=120).print(tree)


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    if args.live:
        from _config import local_config, server_reachable

        cfg: Configuration | None = local_config(
            sampling=Sampling(temperature=0.4, max_tokens=512)
        )
        if not server_reachable(cfg.host or ""):
            print(
                f"[01_composition] cannot reach {cfg.host} — "
                "start llama-server or drop --live",
                file=sys.stderr,
            )
            raise SystemExit(1)
    else:
        _install_offline_stubs(args.question)
        cfg = _OFFLINE_CFG

    _rule("Stage 1 — assemble nested composite")
    agent = assemble(cfg=cfg)
    await agent.abuild()

    n_nodes = len(agent._graph.nodes) if agent._graph else 0
    n_edges = len(agent._graph.edges) if agent._graph else 0
    _panel(
        "Composite shape",
        (
            "top-level Pipeline — 3 stages\n"
            "  stage_0  ResearchPlanner   [ResearchRequest → ResearchPlan]\n"
            "  stage_1  Parallel × 3      [ResearchPlan → _PerspectiveBundle]\n"
            "             ├─ biology   Pipeline(framer → ReAct → packer)\n"
            "             ├─ policy    Pipeline(framer → ReAct → packer)\n"
            "             └─ economic  Pipeline(framer → ReAct → packer)\n"
            "  stage_2  _ResearchEditor   [_PerspectiveBundle → ResearchReport]\n"
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
            f"latency_ms:         {out.latency_ms}\n"
            f"hash_input:         {out.hash_input}\n"
            f"hash_graph:         {out.hash_graph}\n"
            f"hash_prompt:        {out.hash_prompt}\n"
            f"hash_model:         {out.hash_model}\n"
            f"hash_output_schema: {out.hash_output_schema}\n"
            f"agent.hash_content: {agent.hash_content}"
        ),
    )


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
    p.add_argument(
        "--question",
        default="Why are honeybee colonies collapsing in temperate regions?",
        help="The research question to feed the composite.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
