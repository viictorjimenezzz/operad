"""Example 3 - training: optimize a task prompt with OPRO.

What this script illustrates:

* a reference-free metric (length-band) used as the optimization signal,
* `OPROOptimizer` rewriting one task prompt from metric score history,
* live per-step candidate prompts, their scores, and answer lengths,
* `agent.hash_content` shifting once the accepted task prompt changes.

Run modes:

    uv run python examples/03_training.py
    uv run python examples/03_training.py --epochs 2 --candidates 3
    uv run python examples/03_training.py --offline
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from pydantic import BaseModel, Field

from operad import evaluate
from operad.agents import Reasoner
from operad.core.config import Resilience, Sampling
from operad.optim.optimizers.opro import OPROAgent, OPROOptimizer
from operad.runtime import set_limit

from _config import local_config, server_reachable
from utils import (
    LengthBandMetric,
    attach_dashboard,
    parse_dashboard_target,
    print_agent_card,
    print_dataset_table,
    print_panel,
    print_rule,
    rich_available,
)

_RICH = rich_available()


_SCRIPT = "03_training"
DEFAULT_DASHBOARD = "127.0.0.1:7860"
_TARGET_LO, _TARGET_HI = 200, 450
_OVER_DECAY = 1500


class Question(BaseModel):
    text: str = Field(default="", description="A short user question.")


class Answer(BaseModel):
    text: str = Field(default="", description="The answer body.")


class LengthTaskOPRO(OPROAgent):
    """OPRO agent specialized for the length-band training objective."""

    role = "You optimize one task prompt for a science question-answering agent."
    task = (
        "Propose a replacement task instruction that improves the metric score. "
        "The metric rewards final answers whose `text` is 200 to 450 characters "
        "while remaining clear, factual, and useful to a general reader."
    )
    rules = OPROAgent.rules + (
        "Return only the replacement task instruction in `new_value`.",
        "Prefer explicit brevity controls such as 2-3 sentences or 200-450 characters.",
        "Do not change the domain; this remains science question answering.",
    )
    default_sampling = {"temperature": 0.8, "max_tokens": 1024}


def _task_parameter(seed: Any) -> Any:
    for name, param in seed.named_parameters(recurse=False):
        if name == "task":
            return param
    raise RuntimeError("Reasoner task parameter was not found")


def _one_line(value: Any, limit: int = 110) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _candidate_body(
    *,
    step: int,
    before_task: str,
    after_task: str,
    records: list[dict[str, Any]],
    history_size: int,
) -> str:
    lines = [
        f"step:          {step}",
        f"history size:  {history_size}",
        f"before task:   {_one_line(before_task)}",
        f"after task:    {_one_line(after_task)}",
        f"accepted:      {after_task != before_task}",
        "",
        "candidates:",
    ]
    if not records:
        lines.append("  (no valid candidates reached evaluation)")
    for i, record in enumerate(records):
        selected = "*" if record["task"] == after_task else " "
        lines.append(
            f" {selected} #{i} score={record['score']:.3f} "
            f"lengths={record['lengths']}"
        )
        lines.append(f"      task={_one_line(record['task'])}")
    return "\n".join(lines)


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
        sampling=Sampling(temperature=0.0, max_tokens=1024),
        resilience=Resilience(max_retries=2, backoff_base=0.5, timeout=180.0),
    )
    print(f"[{_SCRIPT}] backend={cfg.backend} host={cfg.host} model={cfg.model}")
    if not server_reachable(cfg.host or ""):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} - start llama-server",
            file=sys.stderr,
        )
        raise SystemExit(1)
    set_limit(backend=cfg.backend, host=cfg.host, concurrency=2)

    print_rule("Stage 1 - seed agent + dataset + metric")

    seed = Reasoner(
        config=cfg.model_copy(deep=True),
        input=Question,
        output=Answer,
        role="You answer science questions for a curious general reader.",
        task="Write a clear, factual answer.",
        rules=(
            "Use plain language; avoid jargon unless you define it.",
            "Cite at least one concrete example or mechanism.",
        ),
    )
    await seed.abuild()
    print_agent_card(seed, title="Seed agent")

    metric = LengthBandMetric(
        lo=_TARGET_LO,
        hi=_TARGET_HI,
        over_decay=_OVER_DECAY,
    )
    dataset = [
        (Question(text="Why is the sky blue?"), Answer()),
        (Question(text="What causes ocean tides?"), Answer()),
    ]
    print_dataset_table(dataset, title="Eval dataset")
    print_panel(
        "Metric",
        (
            f"name:               {metric.name}\n"
            f"target band:        len(answer.text) in [{_TARGET_LO}, {_TARGET_HI}] chars\n"
            f"over-length decay:  {metric.over_decay} chars\n"
            "expected side:      empty (reference-free length scorer)"
        ),
    )

    seed_report = await evaluate(seed, dataset, [metric])
    seed_score = float(seed_report.summary[metric.name])
    seed_hash = seed.hash_content
    sample_question = Question(text="Why is the sky blue?")
    seed_answer = (await seed(sample_question)).response.text
    seed_task = seed.task

    print_panel(
        "Seed evaluation",
        (
            f"seed task:          {_one_line(seed_task)}\n"
            f"seed length:        {len(seed_answer)} chars (target [{_TARGET_LO}, {_TARGET_HI}])\n"
            f"seed score:         {seed_score:.3f}\n"
            f"seed hash:          {seed_hash}\n"
            f"sample answer:      {seed_answer[:200]}"
            + ("..." if len(seed_answer) > 200 else "")
        ),
    )

    print_rule("Stage 2 - OPRO (metric-feedback task rewrites)")
    task_param = _task_parameter(seed)
    task_param.momentum_state["opro"] = [(str(task_param.value), seed_score)]
    candidate_records: list[dict[str, Any]] = []
    eval_lock = asyncio.Lock()

    async def evaluate_task_candidate(param: Any, candidate: Any) -> float:
        async with eval_lock:
            old = param.read()
            candidate_text = str(candidate)
            param.write(candidate_text)
            try:
                await seed.abuild()
                report = await evaluate(seed, dataset, [metric])
                score = float(report.summary[metric.name])
                lengths = [
                    len(str((row.get("predicted") or {}).get("text", "")))
                    for row in report.rows
                ]
                candidate_records.append(
                    {"task": candidate_text, "score": score, "lengths": lengths}
                )
                return score
            finally:
                param.write(old)
                await seed.abuild()

    optimizer_cfg = cfg.model_copy(
        deep=True,
        update={"sampling": Sampling(temperature=0.8, max_tokens=1024)},
    )

    async def opro_factory() -> LengthTaskOPRO:
        return await LengthTaskOPRO(config=optimizer_cfg).abuild()

    optimizer = OPROOptimizer(
        [task_param],
        objective_metric=metric,
        evaluator=evaluate_task_candidate,
        opro_factory=opro_factory,
        max_retries=args.candidates,
    )
    print_panel(
        "Optimizer",
        (
            f"class:             {type(optimizer).__name__}\n"
            "parameter:         task\n"
            f"steps:             {args.epochs}\n"
            f"candidate retries: {args.candidates}\n"
            "selection:         accept only candidates that beat history best"
        ),
    )

    print_rule("Stage 3 - fit (live per-step candidate detail)")
    for step in range(args.epochs):
        before_task = str(task_param.value)
        start = len(candidate_records)
        await optimizer.step()
        await seed.abuild()
        after_task = str(task_param.value)
        records = candidate_records[start:]
        history = task_param.momentum_state.get("opro", [])
        print_panel(
            f"OPRO step {step}",
            _candidate_body(
                step=step,
                before_task=before_task,
                after_task=after_task,
                records=records,
                history_size=len(history),
            ),
        )

    print_rule("Stage 4 - final evaluation")
    final_report = await evaluate(seed, dataset, [metric])
    final_score = float(final_report.summary[metric.name])
    final_hash = seed.hash_content
    final_answer = (await seed(sample_question)).response.text
    final_task = seed.task
    delta = final_score - seed_score
    delta_arrow = "+" if delta >= 0 else ""

    print_panel(
        "Result",
        (
            f"task before:   {_one_line(seed_task)}\n"
            f"task after:    {_one_line(final_task)}\n"
            f"answer length: {len(seed_answer)} chars  ->  {len(final_answer)} chars\n"
            f"score:         {seed_score:.3f}  ->  {final_score:.3f}  "
            f"({delta_arrow}{delta:.3f})\n"
            f"hash:          {seed_hash}\n"
            f"               -> {final_hash}\n"
            f"hash changed:  {seed_hash != final_hash} "
            f"(only `task` was optimized)\n\n"
            f"sample answer after training:\n  {final_answer[:_TARGET_HI + 50]}"
            + ("..." if len(final_answer) > _TARGET_HI + 50 else "")
        ),
    )

    if attached:
        host, port = parse_dashboard_target(args.dashboard, default=DEFAULT_DASHBOARD)
        print(
            f"[dashboard] still live at http://{host}:{port}  "
            "(ctrl+c the dashboard server to stop)"
        )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--epochs",
        type=int,
        default=2,
        help="Number of OPRO optimization steps.",
    )
    p.add_argument(
        "--candidates",
        type=int,
        default=3,
        help="Maximum candidate attempts per OPRO step.",
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
