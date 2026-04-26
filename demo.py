"""operad showcase — run this once, love the framework forever.

Requires: local llama-server at 127.0.0.1:9000 serving google/gemma-4-e2b
(see examples/_config.py). Run with:

    uv run python demo.py [--offline] [--dashboard [HOST:PORT]]

Override with OPERAD_LLAMACPP_HOST / OPERAD_LLAMACPP_MODEL. In
``--offline`` mode, only the schema-only stages (1, 2, 5) run; the live
invocation and trace dump are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import socket
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from rich.console import Console
from rich.panel import Panel

from operad import Sequential
from operad.core.config import Sampling
from operad.agents import Classifier, Reasoner
from operad.core.graph import to_mermaid
from operad.runtime.observers import RichDashboardObserver, registry as observers
from operad.runtime.trace import TraceObserver
from operad.utils.ops import AppendRule

sys.path.insert(0, str(Path(__file__).parent / "examples"))
from _config import DEFAULT_HOST, DEFAULT_MODEL, local_config, server_reachable  # noqa: E402


TRACE_PATH = Path("/tmp/operad-demo-trace.json")
DEFAULT_DASHBOARD = "127.0.0.1:7860"


class Question(BaseModel):
    text: str = Field(description="A short user question.")


class Answer(BaseModel):
    text: str = Field(default="", description="One-sentence answer.")


class Verdict(BaseModel):
    confidence: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="How confident the answer sounds.",
    )


def _build_agent() -> Sequential:
    cfg = local_config(sampling=Sampling(temperature=0.2, max_tokens=128))
    answerer = Reasoner(
        config=cfg,
        input=Question,
        output=Answer,
        role="You are a concise assistant.",
        task="Answer the user's question in one sentence.",
    )
    grader = Classifier(
        config=cfg,
        input=Answer,
        output=Verdict,
        role="You are a careful rater.",
        task="Label the answer's confidence as low, medium, or high.",
    )
    return Sequential(answerer, grader, input=Question, output=Verdict)


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


async def main(
    offline: bool = False,
    dashboard: str | None = None,
    no_open: bool = False,
) -> int:
    console = Console(width=120)
    cfg_host = local_config().host
    attached = False
    if dashboard is not None:
        attached = _attach_dashboard(dashboard, open_browser=not no_open)

    if not offline and not server_reachable(cfg_host):
        console.print(
            f"[red]llama-server not reachable at {cfg_host}.[/red]\n"
            f"Start one first, e.g.:\n"
            f"    llama-server -m {DEFAULT_MODEL} "
            f"--host {DEFAULT_HOST.split(':')[0]} "
            f"--port {DEFAULT_HOST.split(':')[1]}\n"
            f"Or re-run with --offline to skip the live stages."
        )
        return 1

    agent = _build_agent()
    await agent.abuild()

    # Stage 1 — rendered prompts.
    buf = io.StringIO()
    agent.operad(file=buf)
    console.print(Panel(buf.getvalue().rstrip(), title="1. Rendered prompts", border_style="cyan"))

    # Stage 2 — Mermaid graph.
    console.print(Panel(to_mermaid(agent._graph), title="2. Mermaid graph", border_style="cyan"))

    if offline:
        console.print("[demo] offline mode — skipping live invocation & trace dump")
    else:
        # Stage 3 — live invocation.
        dashboard = RichDashboardObserver()
        tracer = TraceObserver()
        observers.register(dashboard)
        observers.register(tracer)
        try:
            out = await agent(Question(text="What is the capital of Japan?"))
        finally:
            observers.unregister(dashboard)
            observers.unregister(tracer)
            dashboard.stop()

        console.print(Panel(
            f"response:     {out.response.model_dump_json()}\n"
            f"run_id:       {out.run_id}\n"
            f"agent_path:   {out.agent_path}\n"
            f"latency_ms:   {out.latency_ms}\n"
            f"hash_graph:   {out.hash_graph}\n"
            f"hash_input:   {out.hash_input}\n"
            f"hash_output:  {out.hash_output_schema}",
            title="3. Run output",
            border_style="cyan",
        ))

        # Stage 4 — trace dump.
        trace = tracer.last()
        if trace is not None:
            trace.save(TRACE_PATH)
            console.print(Panel(
                f"{len(trace.steps)} steps saved to {TRACE_PATH}",
                title="4. Trace artefact",
                border_style="cyan",
            ))

    # Stage 5 — mutation + diff. Fresh unbuilt copies keep the panel
    # focused on declared state; `.diff()` works on built agents too.
    base = _build_agent()
    mutated = _build_agent()
    AppendRule(path="", rule="Be terse.").apply(mutated)
    console.print(Panel(str(base.diff(mutated)), title="5. Mutation diff", border_style="cyan"))
    if attached:
        host, port = _parse_dashboard_target(dashboard or DEFAULT_DASHBOARD)
        console.print(
            f"[dashboard] still live at http://{host}:{port}  "
            "(ctrl+c the dashboard server to stop)"
        )

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run schema-only stages without contacting a model server.",
    )
    parser.add_argument(
        "--dashboard",
        nargs="?",
        const=DEFAULT_DASHBOARD,
        default=None,
        metavar="HOST:PORT",
        help="Attach to a running operad-dashboard server (default 127.0.0.1:7860).",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the browser when --dashboard attaches.",
    )
    args = parser.parse_args()
    sys.exit(
        asyncio.run(
            main(offline=args.offline, dashboard=args.dashboard, no_open=args.no_open)
        )
    )
