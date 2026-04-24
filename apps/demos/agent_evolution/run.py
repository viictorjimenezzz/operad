"""`agent_evolution` — the operad flagship demo.

A seed agent is evolved over N generations via `Agent.auto_tune`. The
fitness curve climbs monotonically as the offline metric rewards
longer rule lists. Prints a before/after diff; if ``--dashboard`` is
passed and a local dashboard server is running, events stream to it
live.

Run:
    uv run python apps/demos/agent_evolution/run.py --offline
    uv run python apps/demos/agent_evolution/run.py --offline --dashboard
    uv run python apps/demos/agent_evolution/run.py --offline --generations 6 --population 8
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

from operad.runtime.events import AlgorithmEvent  # noqa: E402
from operad.runtime.observers.base import Event, registry  # noqa: E402

from metric import RuleCountMetric  # noqa: E402
from seed import Q, R, build_seed  # noqa: E402


DEFAULT_DASHBOARD = "127.0.0.1:7860"
TRACE_PATH = Path("/tmp/agent-evolution-trace.jsonl")


class FitnessTraceObserver:
    """Append one JSONL row per `generation` AlgorithmEvent."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent):
            return
        if event.kind != "generation":
            return
        scores = event.payload.get("population_scores", [])
        row = {
            "gen_index": event.payload.get("gen_index"),
            "best": max(scores) if scores else None,
            "mean": sum(scores) / len(scores) if scores else None,
            "population_scores": scores,
        }
        with self.path.open("a") as f:
            f.write(json.dumps(row) + "\n")


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
    registry.register(FitnessTraceObserver(TRACE_PATH))
    attached = False
    if args.dashboard is not None:
        attached = _attach_dashboard(args.dashboard, open_browser=not args.no_open)

    seed = build_seed()
    await seed.abuild()

    dataset = [(Q(text=str(i)), R(value=3)) for i in range(5)]
    metric = RuleCountMetric(target=3)

    improved = await seed.auto_tune(
        dataset,
        metric,
        generations=args.generations,
        population_size=args.population,
        rng=random.Random(args.seed),
    )

    print("=" * 60)
    print(f"seed rules={len(seed.rules)}")
    print(f"evolved rules={len(improved.rules)}")
    print("=" * 60)
    print("diff (seed → evolved):")
    print(seed.diff(improved))
    print("=" * 60)
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
    parser.add_argument("--generations", type=int, default=4)
    parser.add_argument("--population", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the browser when --dashboard attaches.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
