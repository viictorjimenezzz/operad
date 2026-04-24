"""End-to-end offline training demo for `operad.optim` + `operad.train`.

Deterministically trains a single-leaf agent against a keyword-matching
critic using `TextualGradientDescent`. The agent's output is the
concatenation of its `role` and `task`; the critic rewards the presence
of target keywords; across epochs the optimizer grows those prompt
fields until every keyword is covered. We expect:

- `report.epochs[-1].hash_content != report.seed_hash_content`
- `report.epochs[-1].val_metrics["keyword_match"] >= epochs[0]. ...`

No LLM, no network, under 30s. Run:

    uv run python examples/train_demo.py --offline
"""

from __future__ import annotations

import argparse
import asyncio

from operad.optim import CriticLoss, StepLR, TextualGradientDescent
from operad.train import Trainer, TrainingReport

from examples._train_helpers import (
    build_demo_agent_and_data,
    build_fake_critic,
    build_fake_rewriter,
    offline_backward,
    role_task_parameters,
)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _RICH = True
except ImportError:
    _RICH = False


TARGETS = ["concise", "rigorous"]


def _panel(title: str, body: str) -> None:
    if _RICH:
        Console(width=120).print(Panel(body, title=title, border_style="cyan"))
    else:
        bar = "-" * 60
        print(f"\n{bar}\n== {title} ==\n{body}\n{bar}")


def _epoch_table(rows: list[tuple[str, ...]], headers: tuple[str, ...]) -> None:
    if _RICH:
        table = Table(title="2. Per-epoch report", border_style="cyan")
        for h in headers:
            table.add_column(h, justify="right" if h != "hash[:12]" else "left")
        for row in rows:
            table.add_row(*row)
        Console(width=120).print(table)
        return
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:>{w}}}" for w in widths)
    print("\n== 2. Per-epoch report ==")
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        print(fmt.format(*row))


async def main(offline: bool = False) -> TrainingReport:
    _ = offline  # demo is offline unconditionally; flag is for verify.sh parity
    agent, loader, val_ds, metric = await build_demo_agent_and_data(TARGETS)
    critic = await build_fake_critic(TARGETS)
    rewriter = await build_fake_rewriter()

    loss_fn = CriticLoss(
        critic,
        name="critic_score",
        severity_from="score",
        null_threshold=1.0,
    )
    optimizer = TextualGradientDescent(
        role_task_parameters(agent),
        lr=1.0,
        rewriter_factory=lambda _kind: rewriter,
    )
    scheduler = StepLR(optimizer, step_size=2, gamma=0.5)
    trainer = Trainer(
        agent, optimizer, loss_fn, scheduler=scheduler, metrics=[metric]
    )

    seed_hash = agent.hash_content
    seed_report = await trainer.evaluate(val_ds)
    seed_metric = float(seed_report.summary.get(metric.name, float("nan")))

    _panel(
        "1. Seed",
        (
            f"role:         {agent.role!r}\n"
            f"task:         {agent.task!r}\n"
            f"targets:      {TARGETS}\n"
            f"hash_content: {seed_hash}\n"
            f"val {metric.name}: {seed_metric:.3f}"
        ),
    )

    with offline_backward():
        report = await trainer.fit(loader, val_ds=val_ds, epochs=5)

    rows: list[tuple[str, ...]] = []
    prev_hash = seed_hash
    for e in report.epochs:
        cs = e.val_loss if e.val_loss is not None else float("nan")
        km = e.val_metrics.get(metric.name, float("nan"))
        lr = e.lr[0] if e.lr else float("nan")
        delta = "yes" if e.hash_content != prev_hash else "."
        rows.append(
            (
                str(e.epoch),
                f"{cs:.3f}",
                f"{km:.3f}",
                f"{lr:.3f}",
                e.hash_content[:12],
                delta,
            )
        )
        prev_hash = e.hash_content
    _epoch_table(
        rows,
        ("epoch", "critic_score", metric.name, "lr", "hash[:12]", "Δ"),
    )

    final = report.epochs[-1]
    final_metric = float(final.val_metrics.get(metric.name, float("nan")))
    _panel(
        "3. Summary",
        (
            f"role:         {agent.role!r}\n"
            f"task:         {agent.task!r}\n"
            f"seed hash:    {seed_hash}\n"
            f"final hash:   {final.hash_content}\n"
            f"seed {metric.name}:  {seed_metric:.3f}\n"
            f"final {metric.name}: {final_metric:.3f}"
        ),
    )

    assert final.hash_content != seed_hash, (
        f"hash_content did not change: {final.hash_content}"
    )
    assert final_metric + 1e-9 >= seed_metric, (
        f"val metric regressed: seed={seed_metric} final={final_metric}"
    )

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Parity flag (the demo always runs offline).",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
