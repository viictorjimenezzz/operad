"""`agent_evolution` — the operad flagship demo.

A seed agent is evolved over N generations via an explicit `EvoGradient`
population loop. Each generation: mutate the population, score all
individuals, keep the top half, refill from survivors. The fitness curve
climbs as the offline metric rewards longer rule lists; diversity collapses
as the population converges. Runs entirely offline — no model server needed.

Run:
    uv run python apps/demos/agent_evolution/run.py --offline
    uv run python apps/demos/agent_evolution/run.py --offline --dashboard
    uv run python apps/demos/agent_evolution/run.py --offline --generations 5 --population 8
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from operad.optim.optimizers.evo import EvoGradient  # noqa: E402
from operad.runtime.observers.base import registry  # noqa: E402
from operad.utils.ops import (  # noqa: E402
    AppendRule,
    EditTask,
    ReplaceRule,
    SetTemperature,
    TweakRole,
)

from metric import RuleCountMetric  # noqa: E402
from population import GENERATIONS, POPULATION_SIZE, diversity  # noqa: E402
from seed import Q, R, build_seed  # noqa: E402


DEFAULT_DASHBOARD = "127.0.0.1:7860"
TRACE_PATH = Path("/tmp/agent-evolution-trace.jsonl")


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


async def main(args: argparse.Namespace) -> None:
    attached = False
    if args.dashboard is not None:
        attached = _attach_dashboard(args.dashboard, open_browser=not args.no_open)

    seed = build_seed()
    await seed.abuild()

    metric = RuleCountMetric(target=7)
    dataset = [(Q(text=str(i)), R(value=metric.target)) for i in range(6)]
    ops = [
        AppendRule(path="", rule="State the main reason before caveats."),
        AppendRule(path="", rule="Cite one concrete clue from the input."),
        AppendRule(path="", rule="Flag uncertainty explicitly."),
        TweakRole(path="", role="You are a precise evaluator."),
        EditTask(path="", task="Rank answer quality and return the best concise response."),
        SetTemperature(path="", temperature=0.3),
        SetTemperature(path="", temperature=0.7),
        ReplaceRule(path="", index=0, rule="Prefer grounded, checkable claims."),
    ]

    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=ops,
        metric=metric,
        dataset=dataset,
        population_size=args.population,
        rng=random.Random(args.seed),
    )

    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACE_PATH.write_text("")

    print(f"{'gen':>4}  {'best':>6}  {'mean':>6}  {'diversity':>9}")
    print("-" * 34)

    async with optimizer.session():
        with TRACE_PATH.open("a") as trace_file:
            for gen in range(args.generations):
                await optimizer.step()
                scores = list(optimizer._last_scores or [])
                pop = optimizer._population or []
                d = diversity(pop)
                best = max(scores) if scores else 0.0
                mean = sum(scores) / len(scores) if scores else 0.0
                print(f"{gen:>4}  {best:>6.3f}  {mean:>6.3f}  {d:>9}")
                row = {
                    "gen": gen,
                    "best": best,
                    "mean": mean,
                    "population_scores": scores,
                    "diversity": d,
                }
                trace_file.write(json.dumps(row) + "\n")
                trace_file.flush()

    print("=" * 34)
    print(f"seed rules  : {2}")
    print(f"evolved rules: {len(seed.rules)}")
    print(f"fitness trace → {TRACE_PATH}")
    if attached:
        host, port = _parse_dashboard_target(args.dashboard)
        print(f"dashboard still live at http://{host}:{port}  (ctrl+c the dashboard server to stop)")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        default=True,
        help="Run without any model server (default; the seed is synthetic).",
    )
    parser.add_argument(
        "--dashboard",
        nargs="?",
        const=DEFAULT_DASHBOARD,
        default=None,
        metavar="HOST:PORT",
        help="Attach to a running operad-dashboard server (default 127.0.0.1:7860).",
    )
    parser.add_argument("--generations", type=int, default=GENERATIONS)
    parser.add_argument("--population", type=int, default=POPULATION_SIZE)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the browser when --dashboard attaches.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
