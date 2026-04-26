"""Shared helpers for interactive examples."""

from __future__ import annotations

import socket
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel

from operad.metrics.base import MetricBase

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _RICH = True
except ImportError:
    _RICH = False


def rich_available() -> bool:
    return _RICH


def print_rule(title: str) -> None:
    if _RICH:
        Console(width=120).rule(f"[bold cyan]{title}")
    else:
        bar = "=" * (len(title) + 6)
        print(f"\n{bar}\n   {title}\n{bar}")


def print_panel(title: str, body: str) -> None:
    if _RICH:
        Console(width=120).print(Panel(body, title=title, border_style="cyan"))
    else:
        bar = "-" * 60
        print(f"\n{bar}\n{title}\n{bar}\n{body}\n{bar}")


def parse_dashboard_target(
    value: str | None,
    *,
    default: str = "127.0.0.1:7860",
) -> tuple[str, int]:
    raw = value or default
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 7860
    return host, port


def server_up(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def attach_dashboard(
    target: str,
    *,
    open_browser: bool = True,
    default: str = "127.0.0.1:7860",
) -> bool:
    host, port = parse_dashboard_target(target, default=default)
    if not server_up(host, port):
        print(
            f"[dashboard] no server at {host}:{port} - "
            "start one with `operad-dashboard --port 7860` then re-run with --dashboard"
        )
        return False
    from operad.dashboard import attach

    attach(host=host, port=port)
    url = f"http://{host}:{port}"
    print(f"[dashboard] attached -> {url}")
    if open_browser:
        try:
            import webbrowser

            webbrowser.open_new_tab(url)
        except Exception:
            pass
    return True


class LengthBandMetric(MetricBase):
    """Score by how close `len(predicted.text)` is to a target [lo, hi] band."""

    def __init__(
        self,
        *,
        lo: int,
        hi: int,
        over_decay: int,
        name: str = "length_band",
    ) -> None:
        self.lo = lo
        self.hi = hi
        self.over_decay = max(1, over_decay)
        self.name = name

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        _ = expected
        text = str(getattr(predicted, "text", ""))
        n = len(text)
        if self.lo <= n <= self.hi:
            return 1.0
        if n < self.lo:
            return max(0.0, 0.99 * n / self.lo)
        over = n - self.hi
        return max(0.0, 1.0 - over / self.over_decay)


def score_stats(scores: list[float]) -> tuple[float, float, float]:
    if not scores:
        return 0.0, 0.0, 0.0
    best = max(scores)
    mean = sum(scores) / len(scores)
    spread = max(scores) - min(scores)
    return best, mean, spread


def op_histogram(ops: list[str]) -> str:
    if not ops:
        return ""
    counts = Counter(ops)
    return ", ".join(f"{name}x{count}" for name, count in sorted(counts.items()))


def print_scenario_tree(tree: Any) -> None:
    if not _RICH:
        def walk(node: Any, depth: int = 0) -> None:
            bullet = "T" if node.terminal else "."
            print(f"{'  ' * depth}{bullet} [{node.id}] {node.title}")
            for child in node.children:
                walk(child, depth + 1)

        walk(tree.root)
        return

    from rich.tree import Tree as RichTree

    rich_tree = RichTree(f"[bold]{tree.name}[/]")
    rich_tree.add(f"[dim]{tree.purpose}[/]")

    def add(parent: Any, node: Any) -> None:
        marker = "[red]*[/]" if node.terminal else "[green]o[/]"
        rich_node = parent.add(f"{marker} [bold]{node.title}[/]  [dim]({node.id})[/]")
        if node.instructions:
            rich_node.add(f"[italic dim]instructions: {node.instructions}[/]")
        for child in node.children:
            add(rich_node, child)

    add(rich_tree, tree.root)
    Console(width=120).print(rich_tree)


def print_talker_turn(turn: Any) -> None:
    decision = turn.decision
    color_by_kind = {
        "stay": "yellow",
        "advance": "green",
        "branch": "blue",
        "finish": "magenta",
    }
    kind_color = color_by_kind.get(decision.kind, "white")
    if _RICH:
        body = (
            f"[bold]user[/]      -> {turn.user_message}\n"
            f"[dim]from[/]      -> {turn.from_node_id}\n"
            f"[bold {kind_color}]decision[/] -> {decision.kind}"
            f"{(' -> ' + decision.branch_to) if decision.branch_to else ''}"
            f"  [dim]({decision.rationale})[/]\n"
            f"[dim]to[/]        -> {turn.to_node_id}"
            f"{'  [bold magenta]TERMINAL[/]' if turn.is_terminal else ''}\n"
            f"[bold]assistant[/] <- {turn.assistant_message}"
        )
        Console(width=120).print(
            Panel(body, title=f"turn {turn.turn_index}", border_style=kind_color)
        )
        return

    print(f"\n--- turn {turn.turn_index} ---")
    print(f"user      -> {turn.user_message}")
    print(f"from      -> {turn.from_node_id}")
    print(
        f"decision  -> {decision.kind}"
        + (f" -> {decision.branch_to}" if decision.branch_to else "")
        + f"  ({decision.rationale})"
    )
    print(
        f"to        -> {turn.to_node_id}"
        + ("  TERMINAL" if turn.is_terminal else "")
    )
    print(f"assistant <- {turn.assistant_message}")


def print_talker_summary(transcript: Any) -> None:
    kinds: dict[str, int] = {}
    for turn in transcript.turns:
        kinds[turn.decision.kind] = kinds.get(turn.decision.kind, 0) + 1

    if not _RICH:
        print("\nSummary:")
        print(f"  process:        {transcript.process_name}")
        print(f"  turns:          {len(transcript.turns)}")
        print(f"  decision_kinds: {kinds}")
        print(f"  final_node_id:  {transcript.final_node_id}")
        print(f"  finished:       {transcript.finished}")
        return

    table = Table(title="Decision histogram", border_style="cyan")
    table.add_column("kind", justify="left")
    table.add_column("count", justify="right")
    for kind, count in sorted(kinds.items(), key=lambda item: -item[1]):
        table.add_row(kind, str(count))
    Console(width=120).print(table)
    Console(width=120).print(
        Panel(
            (
                f"process:        {transcript.process_name}\n"
                f"turns:          {len(transcript.turns)}\n"
                f"final_node_id:  {transcript.final_node_id}\n"
                f"finished:       {transcript.finished}"
            ),
            title="Run summary",
            border_style="cyan",
        )
    )
