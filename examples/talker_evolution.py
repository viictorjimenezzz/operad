"""Evolve a `Talker`'s prompt against a conversational dataset.

A seed `Talker` agent is cloned, mutated, evaluated, and selected over
several generations via `Agent.auto_tune` (which wraps `EvoGradient`).
Per-generation fitness events stream live to:

  - the terminal (Rich TUI), and
  - the web dashboard (optional, when `--dashboard` is passed and a
    dashboard server is up), and
  - an NDJSON trace at `/tmp/talker-evolution-trace.jsonl` for offline
    post-analysis / replay.

The demo defaults to fully offline mode via a deterministic
`FakeTalker` subclass, so you do not need a model server running to
see the whole optimization loop. Pass `--live` to talk to a real
llama-server instead.

Commands
--------

# 0. one-time install of the web dashboard (optional)
uv pip install -e apps/dashboard/

# 1. offline, Rich terminal only
uv run python examples/talker_evolution.py

# 2. offline, Rich + web dashboard (two terminals)
#    terminal A:
operad-dashboard --port 7860
#    terminal B:
uv run python examples/talker_evolution.py --dashboard

# 3. live, against a local llama-server
#    terminal A:
operad-dashboard --port 7860
#    terminal B:
OPERAD_LLAMACPP_HOST=127.0.0.1:8080 \
OPERAD_LLAMACPP_MODEL=qwen2.5-7b-instruct \
  uv run python examples/talker_evolution.py --live --dashboard

# 4. replay a past run in the dashboard
operad-dashboard --replay /tmp/talker-evolution-trace.jsonl --speed 0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel

from operad import Configuration
from operad.agents.conversational import Talker
from operad.agents.conversational.schemas import TalkerInput, TextResponse
from operad.metrics.base import MetricBase
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import Event, registry


TRACE_PATH = Path("/tmp/talker-evolution-trace.jsonl")
DEFAULT_DASHBOARD = "127.0.0.1:7860"


# --- deterministic offline talker -------------------------------------------


class FakeTalker(Talker):
    """Offline Talker: `forward` is a pure function of declared state.

    Longer rule lists + a role that mentions "warm" produce longer,
    better-formed canned answers. The metric below rewards that
    combination, so `EvoGradient` should climb monotonically when
    fed `AppendRule` / `TweakRole` mutations.
    """

    async def forward(self, x: TalkerInput) -> TextResponse:  # type: ignore[override]
        n_rules = len(self.rules)
        warmth = "warm" in (self.role or "").lower() or "friendly" in (self.role or "").lower()
        body = (
            "Great question — here's a focused take. "
            + ("This builds on what we discussed. " if x.belief_summary else "")
            + "· " * max(n_rules - 1, 0)
        )
        closer = "Happy to go deeper — which part should we explore?" if warmth else "Done."
        return TextResponse(text=f"{body}{closer}")


# --- reference-free quality metric -------------------------------------------


class TalkerQualityMetric(MetricBase):
    """Reward responses that are in a target length band and end warmly.

    Three signals are combined:

    - `length_ok`  — response length within [80, 320] chars.
    - `warm_close` — response ends with `?` or `!`.
    - `no_preamble`— does not open with "Answer:" / "Here is" / etc.

    Score is the mean of the three (0-1). Higher is better.
    """

    name = "talker_quality"

    async def score(
        self, predicted: TextResponse, _expected: TextResponse
    ) -> float:
        text = (predicted.text or "").strip()
        if not text:
            return 0.0
        length_ok = 80 <= len(text) <= 320
        warm_close = text.rstrip().endswith(("?", "!"))
        no_preamble = not text.lower().startswith(
            ("answer:", "here is", "sure,", "okay", "of course")
        )
        return (int(length_ok) + int(warm_close) + int(no_preamble)) / 3


# --- small FitnessTraceObserver (mirrors apps/demos/agent_evolution) --------


class FitnessTraceObserver:
    """Append one NDJSON row per `generation` AlgorithmEvent."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent) or event.kind != "generation":
            return
        scores = event.payload.get("population_scores", [])
        row = {
            "gen_index": event.payload.get("gen_index"),
            "best": max(scores) if scores else None,
            "mean": sum(scores) / len(scores) if scores else None,
            "population_scores": scores,
            "survivor_indices": event.payload.get("survivor_indices"),
        }
        with self.path.open("a") as f:
            f.write(json.dumps(row) + "\n")


# --- dashboard attachment helpers (same pattern as apps/demos/agent_evolution)


def _parse_dashboard_target(value: str) -> tuple[str, int]:
    raw = value or DEFAULT_DASHBOARD
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    return (parsed.hostname or "127.0.0.1", parsed.port or 7860)


def _server_up(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _attach_web_dashboard(target: str) -> None:
    host, port = _parse_dashboard_target(target)
    if not _server_up(host, port):
        print(
            f"[dashboard] no server at {host}:{port} — "
            "start one with `operad-dashboard --port 7860` "
            "then re-run with --dashboard",
            file=sys.stderr,
        )
        return
    from operad.dashboard import attach

    attach(host=host, port=port)
    print(f"[dashboard] attached → http://{host}:{port}")


def _register_rich() -> None:
    """Register the Rich TUI observer; gracefully no-op if `rich` missing."""
    try:
        from operad.runtime.observers.rich import RichDashboardObserver
    except ImportError:
        print(
            "[rich] `rich` not installed — install with `uv sync --extra observers` "
            "to enable the terminal dashboard",
            file=sys.stderr,
        )
        return
    registry.register(RichDashboardObserver())


# --- main --------------------------------------------------------------------


def _build_seed(*, live: bool) -> Talker:
    """Return a weak seed that the metric will reward improving.

    The seed starts with a cold role, a minimal task, and zero rules
    — all prime targets for the `default_mutations` set
    (AppendRule / TweakRole / EditTask).
    """
    if live:
        cfg = Configuration(
            backend="llamacpp",
            host=os.environ.get("OPERAD_LLAMACPP_HOST", "127.0.0.1:8080"),
            model=os.environ.get("OPERAD_LLAMACPP_MODEL", "qwen2.5-7b-instruct"),
        )
        seed_cls: type[Talker] = Talker
    else:
        cfg = None
        seed_cls = FakeTalker

    return seed_cls(
        config=cfg,
        role="You are an assistant.",
        task="Respond.",
        rules=[],
        examples=[],
    )


async def main(args: argparse.Namespace) -> None:
    registry.register(FitnessTraceObserver(TRACE_PATH))
    _register_rich()
    if args.dashboard is not None:
        _attach_web_dashboard(args.dashboard)

    seed = _build_seed(live=args.live)
    await seed.abuild()

    # reference-free metric, so `expected` is an unused sentinel
    dataset: list[tuple[TalkerInput, TextResponse]] = [
        (
            TalkerInput(
                message="Hi", context="You're a chemistry tutor."
            ),
            TextResponse(),
        ),
        (
            TalkerInput(
                message="Who are you?", context="You're a chemistry tutor."
            ),
            TextResponse(),
        ),
        (
            TalkerInput(
                message="What can you help with?",
                context="You're a chemistry tutor.",
            ),
            TextResponse(),
        ),
        (
            TalkerInput(
                message="How do I store sodium safely?",
                context="You're a chemistry tutor.",
            ),
            TextResponse(),
        ),
        (
            TalkerInput(
                message="Remind me what we covered.",
                context="You're a chemistry tutor.",
                belief_summary="We discussed reactive metals and inert-gas storage.",
            ),
            TextResponse(),
        ),
    ]
    metric = TalkerQualityMetric()

    # evaluate the seed once so the delta is obvious in the output
    from operad.benchmark import evaluate

    seed_report = await evaluate(seed, dataset, [metric])
    seed_score = seed_report.summary[metric.name]

    # the whole optimization loop — one call
    evolved = await seed.auto_tune(
        dataset,
        metric,
        generations=args.generations,
        population_size=args.population,
        rng=random.Random(args.seed),
    )
    await evolved.abuild()
    evolved_report = await evaluate(evolved, dataset, [metric])
    evolved_score = evolved_report.summary[metric.name]

    print("=" * 60)
    print(f"seed    {metric.name}={seed_score:.3f}   rules={len(seed.rules)}")
    print(
        f"evolved {metric.name}={evolved_score:.3f}   rules={len(evolved.rules)}"
    )
    print("=" * 60)
    print("diff (seed → evolved):")
    print(seed.diff(evolved))
    print("=" * 60)
    print(f"fitness trace → {TRACE_PATH}")
    if args.dashboard is not None:
        host, port = _parse_dashboard_target(args.dashboard)
        print(f"dashboard     → http://{host}:{port}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--live",
        action="store_true",
        help=(
            "Use a real llama-server (requires OPERAD_LLAMACPP_HOST / "
            "_MODEL env vars). Default is offline via FakeTalker."
        ),
    )
    p.add_argument(
        "--dashboard",
        nargs="?",
        const=DEFAULT_DASHBOARD,
        default=None,
        metavar="HOST:PORT",
        help=(
            "Attach to a running `operad-dashboard` server "
            "(default 127.0.0.1:7860)."
        ),
    )
    p.add_argument("--generations", type=int, default=4)
    p.add_argument("--population", type=int, default=6)
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
