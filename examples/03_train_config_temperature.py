"""Example 3 — training: tune `config.sampling.temperature` of a real `Reasoner`.

A vanilla `Reasoner(input=Question, output=Answer, role=..., task=..., rules=...)`
answers science questions. `EvoGradient` mutates only
`config.sampling.temperature` (via a `SetTemperature` mutation pool)
and selects the agents whose answers land closest to a target length
band — a reference-free metric that's fast to evaluate (no second LLM
call), so the loop converges in just a few minutes against a local
model.

Per-generation rows are streamed to a Rich table; the seed-vs-final
temperature, hash, and score are highlighted at the end.

Run modes:

    uv run python examples/03_train_config_temperature.py            # hits the local llama-server
    uv run python examples/03_train_config_temperature.py --offline  # no-op for verify.sh
"""

from __future__ import annotations

import argparse
import asyncio
import random
import socket
import sys
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from operad import evaluate
from operad.agents import Reasoner
from operad.core.config import Resilience, Sampling
from operad.metrics.base import MetricBase
from operad.optim import EvoGradient
from operad.runtime import set_limit
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import Event, registry
from operad.utils.ops import SetTemperature

from _config import local_config, server_reachable

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _RICH = True
except ImportError:
    _RICH = False


_SCRIPT = "03_train_config_temperature"
DEFAULT_DASHBOARD = "127.0.0.1:7860"


# ---------------------------------------------------------------------------
# Domain.
# ---------------------------------------------------------------------------


class Question(BaseModel):
    text: str = Field(default="", description="A short user question.")


class Answer(BaseModel):
    text: str = Field(default="", description="The answer body.")


# ---------------------------------------------------------------------------
# Reference-free length-band metric: rewards answers whose length lands in
# the target [LO, HI] character range. With a real LLM, output length
# varies with temperature (and with sampling noise per-call), so the
# optimiser has a real signal to climb without needing a second LLM judge.
# ---------------------------------------------------------------------------


_TARGET_LO, _TARGET_HI = 200, 450


class _LengthBandMetric(MetricBase):
    """Score = 1.0 if `len(predicted.text) ∈ [LO, HI]`, decays linearly outside."""

    name = "length_band"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        _ = expected
        text = str(getattr(predicted, "text", ""))
        n = len(text)
        if _TARGET_LO <= n <= _TARGET_HI:
            return 1.0
        if n < _TARGET_LO:
            return max(0.0, 0.99 * n / _TARGET_LO)
        over = n - _TARGET_HI
        return max(0.0, 1.0 - over / 300)


# ---------------------------------------------------------------------------
# Per-generation observer for the Rich table.
# ---------------------------------------------------------------------------


class _GenerationLogger:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent) or event.kind != "generation":
            return
        scores = event.payload.get("population_scores", [])
        ops = [m["op"] for m in event.payload.get("mutations", [])]
        self.rows.append(
            {
                "gen": event.payload.get("gen_index", -1),
                "best": max(scores) if scores else None,
                "mean": sum(scores) / len(scores) if scores else None,
                "spread": (max(scores) - min(scores)) if scores else None,
                "ops": ops,
                "survivors": event.payload.get("survivor_indices", []),
            }
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


def _print_generation_table(logger: _GenerationLogger) -> None:
    if not _RICH:
        print("\ngen | best | mean | spread | survivors")
        for r in logger.rows:
            print(
                f"  {r['gen']:>2} | "
                f"{r['best']:.3f} | {r['mean']:.3f} | {r['spread']:.3f} | "
                f"{r['survivors']}"
            )
        return
    table = Table(title="Per-generation training report", border_style="cyan")
    table.add_column("gen", justify="right")
    table.add_column("best", justify="right")
    table.add_column("mean", justify="right")
    table.add_column("spread", justify="right")
    table.add_column("ops applied this gen", justify="left")
    table.add_column("survivors", justify="left")
    for r in logger.rows:
        op_counts: dict[str, int] = {}
        for op in r["ops"]:
            op_counts[op] = op_counts.get(op, 0) + 1
        ops_str = ", ".join(f"{k}×{v}" for k, v in sorted(op_counts.items()))
        table.add_row(
            str(r["gen"]),
            f"{r['best']:.3f}",
            f"{r['mean']:.3f}",
            f"{r['spread']:.3f}",
            ops_str,
            str(r["survivors"]),
        )
    Console(width=120).print(table)


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
        sampling=Sampling(temperature=0.0, max_tokens=1024),
        resilience=Resilience(max_retries=2, backoff_base=0.5, timeout=180.0),
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
    set_limit(backend=cfg.backend, host=cfg.host, concurrency=2)

    _rule("Stage 1 — assemble seed agent + dataset + metric")

    # Seed: a vanilla Reasoner with a focused role/task. The only thing
    # the optimiser will tune is `config.sampling.temperature`.
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
    seed.mark_trainable(temperature=True)
    await seed.abuild()

    metric = _LengthBandMetric()

    dataset = [
        (Question(text="Why is the sky blue?"), Answer()),
        (Question(text="What causes ocean tides?"), Answer()),
    ]

    seed_report = await evaluate(seed, dataset, [metric])
    seed_score = float(seed_report.summary[metric.name])
    seed_temp = seed.config.sampling.temperature
    seed_hash = seed.hash_content
    sample_question = Question(text="Why is the sky blue?")
    seed_answer = (await seed(sample_question)).response.text

    _panel(
        "Seed",
        (
            f"agent class:        {type(seed).__name__}\n"
            f"trainable:          config.sampling.temperature\n"
            f"target length band: [{_TARGET_LO}, {_TARGET_HI}] chars\n"
            f"metric:             reference-free length-band score\n"
            f"seed temperature:   {seed_temp:.2f}\n"
            f"seed length:        {len(seed_answer)} chars\n"
            f"seed score:         {seed_score:.3f}\n"
            f"seed hash:          {seed_hash}\n"
            f"sample answer:      {seed_answer[:200]}"
            + ("…" if len(seed_answer) > 200 else "")
        ),
    )

    _rule("Stage 2 — build EvoGradient with SetTemperature mutations")
    mutations = [
        SetTemperature(path="", temperature=0.1),
        SetTemperature(path="", temperature=0.3),
        SetTemperature(path="", temperature=0.5),
        SetTemperature(path="", temperature=0.7),
        SetTemperature(path="", temperature=0.9),
    ]
    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=mutations,
        metric=metric,
        dataset=dataset,
        population_size=3,
        rng=random.Random(0),
    )
    _panel(
        "Optimizer",
        (
            f"class:           {type(optimizer).__name__}\n"
            f"population_size: 3\n"
            f"mutation pool:   {len(mutations)} × SetTemperature ∈ "
            "{0.1, 0.3, 0.5, 0.7, 0.9}\n"
            "rng seed:        0"
        ),
    )

    _rule("Stage 3 — fit (2 generations)")
    logger = _GenerationLogger()
    registry.register(logger)
    n_generations = 2
    try:
        for gen in range(n_generations):
            print(
                f"  gen {gen + 1}/{n_generations} — "
                "evaluating population (each individual runs the dataset)…"
            )
            await optimizer.step()
    finally:
        registry.unregister(logger)

    _print_generation_table(logger)

    _rule("Stage 4 — final evaluation")
    final_report = await evaluate(seed, dataset, [metric])
    final_score = float(final_report.summary[metric.name])
    final_temp = seed.config.sampling.temperature
    final_hash = seed.hash_content
    final_answer = (await seed(sample_question)).response.text

    _panel(
        "Result",
        (
            f"seed temperature:   {seed_temp:.2f}     →  final: {final_temp:.2f}\n"
            f"seed length:        {len(seed_answer)} chars  →  final: {len(final_answer)} chars\n"
            f"seed score:         {seed_score:.3f}    →  final: {final_score:.3f}\n"
            f"seed hash:          {seed_hash}\n"
            f"final hash:         {final_hash}\n"
            f"hash changed:       {seed_hash != final_hash}\n\n"
            f"sample answer at final temperature:\n  {final_answer[:_TARGET_HI + 50]}"
            + ("…" if len(final_answer) > _TARGET_HI + 50 else "")
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
