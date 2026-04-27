"""Shared helpers for interactive examples."""

from __future__ import annotations

import socket
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel

from operad.metrics.metric import MetricBase

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


def print_agent_card(agent: Any, *, title: str = "Agent") -> None:
    """Render an agent with rich when available, else fall back to summary()."""
    if _RICH:
        Console(width=120).print(Panel.fit(agent, title=title, border_style="cyan"))
    else:
        print(f"\n{title}\n{'-' * len(title)}\n{agent.summary()}")


def print_dataset_table(
    rows: Sequence[tuple[BaseModel, BaseModel]],
    *,
    title: str = "Dataset",
    field: str = "text",
    width: int = 90,
) -> None:
    """Render a (input, expected) dataset as a small table.

    Each row shows the input value of `field` and whether the expected
    side carries any non-default content (length-band / reference-free
    metrics use empty expected values, which is itself worth showing).
    """
    if _RICH:
        table = Table(title=title, border_style="cyan", expand=False)
        table.add_column("#", justify="right", style="dim")
        table.add_column("input." + field, justify="left", overflow="fold")
        table.add_column("expected." + field, justify="left", overflow="fold")
        for i, (inp, exp) in enumerate(rows):
            inp_text = str(getattr(inp, field, ""))
            exp_text = str(getattr(exp, field, ""))
            table.add_row(
                str(i),
                _ellipsize(inp_text, width),
                _ellipsize(exp_text, width) if exp_text else "[dim](reference-free)[/]",
            )
        Console(width=120).print(table)
        return

    print(f"\n{title}")
    for i, (inp, exp) in enumerate(rows):
        exp_text = str(getattr(exp, field, "")) or "(reference-free)"
        print(f"  {i:>2}  in: {getattr(inp, field, '')!r}  exp: {exp_text!r}")


def print_mutation_generation(
    *,
    generation_index: int,
    candidates: Sequence[dict[str, Any]],
    selected_ids: Sequence[int],
    state_after: str | None = None,
    rationale_width: int = 70,
) -> None:
    """Print one generation's candidates with op, rationale, scores, and selection.

    `candidates` is a sequence of `MutationCandidate.model_dump()` dicts
    (as carried by the `generation` AlgorithmEvent payload). Rows for
    selected candidate ids are highlighted; `state_after` is appended as
    a one-line note describing the post-write-back state of the seed
    (e.g. `temperature 0.00 -> 0.42` or `rules: [...]`).
    """
    selected = set(int(i) for i in selected_ids)

    if not _RICH:
        print(f"\n[gen {generation_index}] {len(candidates)} candidate(s)")
        for c in candidates:
            cid = int(c.get("candidate_id", -1))
            mark = "*" if cid in selected else " "
            judge = c.get("score")
            judge_s = f"{float(judge):.3f}" if judge is not None else "  -  "
            print(
                f"  {mark} #{cid:>2}  {str(c.get('op', '')):<16}  "
                f"metric={float(c.get('metric_score', 0.0)):.3f}  judge={judge_s}  "
                f"-- {_ellipsize(str(c.get('rationale', '')), rationale_width)}"
            )
        if state_after:
            print(f"  -> {state_after}")
        return

    table = Table(box=None, padding=(0, 1), show_edge=False)
    table.add_column("", justify="center", width=2)
    table.add_column("id", justify="right", style="dim")
    table.add_column("op", justify="left")
    table.add_column("metric", justify="right")
    table.add_column("judge", justify="right")
    table.add_column("rationale", justify="left", overflow="fold")
    for c in candidates:
        cid = int(c.get("candidate_id", -1))
        is_sel = cid in selected
        mark = "[bold green]*[/]" if is_sel else ""
        judge = c.get("score")
        judge_s = f"{float(judge):.3f}" if judge is not None else "[dim]-[/]"
        op = str(c.get("op", ""))
        op_cell = f"[bold]{op}[/]" if is_sel else op
        rationale = _ellipsize(str(c.get("rationale", "")), rationale_width)
        table.add_row(
            mark,
            str(cid),
            op_cell,
            f"{float(c.get('metric_score', 0.0)):.3f}",
            judge_s,
            rationale,
        )

    body: Any = table
    if state_after:
        from rich.console import Group

        body = Group(table, "", f"[dim]-> {state_after}[/]")

    Console(width=120).print(
        Panel(
            body,
            title=f"generation {generation_index}",
            border_style="cyan",
            padding=(0, 1),
        )
    )


def print_rules_diff(before: Iterable[str], after: Iterable[str], *, title: str = "Rules diff") -> None:
    """Show which rules were added/removed/preserved between two snapshots.

    Order-preserving: rules are matched by exact string. New entries get a
    `+`, removed entries get a `-`, kept entries get a faded marker. This
    is enough to read what an evolutionary search actually mutated.
    """
    before_list = list(before)
    after_list = list(after)
    before_set = set(before_list)
    after_set = set(after_list)
    removed = [r for r in before_list if r not in after_set]
    added = [r for r in after_list if r not in before_set]
    kept = [r for r in after_list if r in before_set]

    if not _RICH:
        print(f"\n{title}")
        for r in kept:
            print(f"   {r}")
        for r in removed:
            print(f" - {r}")
        for r in added:
            print(f" + {r}")
        return

    lines: list[str] = []
    for r in kept:
        lines.append(f"[dim]  {_ellipsize(r, 100)}[/]")
    for r in removed:
        lines.append(f"[red]- {_ellipsize(r, 100)}[/]")
    for r in added:
        lines.append(f"[green]+ {_ellipsize(r, 100)}[/]")
    if not lines:
        lines.append("[dim](no rules)[/]")
    Console(width=120).print(
        Panel("\n".join(lines), title=title, border_style="cyan")
    )


def _ellipsize(text: str, width: int) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)].rstrip() + "..."
