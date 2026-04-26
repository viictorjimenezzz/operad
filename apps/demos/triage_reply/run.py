"""`triage_reply` — operad's compositionality + evolution showcase.

A small customer-support tree (Router + Sequential + four responders)
is evolved over N generations via `Agent.auto_tune`. Every sub-agent is
a deterministic offline leaf, so the whole demo runs without a model
server. The mutation pool targets specific sub-paths, so different
generations improve different branches — visible live in the dashboard's
graph and mutation panels.

Run:
    uv run python apps/demos/triage_reply/run.py
    uv run python apps/demos/triage_reply/run.py --dashboard
    uv run python apps/demos/triage_reply/run.py --generations 8 --population 8
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

from operad.benchmark import evaluate  # noqa: E402
from operad.runtime.events import AlgorithmEvent  # noqa: E402
from operad.runtime.observers.base import Event, registry  # noqa: E402

from dataset import build_dataset  # noqa: E402
from metric import TriageReplyMetric  # noqa: E402
from mutations import build_mutations  # noqa: E402
from tree import build_seed  # noqa: E402


DEFAULT_DASHBOARD = "127.0.0.1:7860"
TRACE_PATH = Path("/tmp/triage-reply-trace.jsonl")


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
            "op_attempt_counts": event.payload.get("op_attempt_counts"),
            "op_success_counts": event.payload.get("op_success_counts"),
        }
        with self.path.open("a") as f:
            f.write(json.dumps(row) + "\n")


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


def _attach_dashboard(target: str, *, open_browser: bool = True) -> bool:
    host, port = _parse_dashboard_target(target)
    if not _server_up(host, port):
        print(
            f"[dashboard] no server at {host}:{port} — "
            "start one with `operad-dashboard --port 7860` then re-run with --dashboard",
            file=sys.stderr,
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

    dataset = build_dataset()
    metric = TriageReplyMetric()
    mutations = build_mutations()

    seed_report = await evaluate(seed, dataset, [metric])
    seed_score = seed_report.summary[metric.name]

    evolved = await seed.auto_tune(
        dataset,
        metric,
        mutations=mutations,
        generations=args.generations,
        population_size=args.population,
        rng=random.Random(args.seed),
    )
    await evolved.abuild()
    evolved_report = await evaluate(evolved, dataset, [metric])
    evolved_score = evolved_report.summary[metric.name]

    print("=" * 60)
    print(f"seed    {metric.name}={seed_score:.3f}")
    print(f"evolved {metric.name}={evolved_score:.3f}")
    print("=" * 60)
    print("diff (seed → evolved):")
    print(seed.diff(evolved))
    print("=" * 60)
    print(f"fitness trace → {TRACE_PATH}")
    if attached:
        host, port = _parse_dashboard_target(args.dashboard)
        print(f"dashboard still live at http://{host}:{port}  (ctrl+c the dashboard server to stop)")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dashboard",
        nargs="?",
        const=DEFAULT_DASHBOARD,
        default=None,
        metavar="HOST:PORT",
        help="Attach to a running operad-dashboard server (default 127.0.0.1:7860).",
    )
    p.add_argument("--generations", type=int, default=6)
    p.add_argument("--population", type=int, default=8)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the browser when --dashboard attaches.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
