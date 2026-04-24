"""Live dashboard observer backed by `rich`.

Optional: the `rich` package is only required at construction time. If
not installed, the constructor raises with a clear install hint.
"""

from __future__ import annotations

from typing import Any

from ..events import AlgorithmEvent
from .base import AgentEvent, Event


_INSTALL_HINT = (
    "RichDashboardObserver requires `rich`. Install the observers extra:\n"
    "    uv add 'operad[observers]'\n"
    "or install rich directly: `uv add rich`."
)


class RichDashboardObserver:
    """Live tree of in-flight agents, one subtree per run_id.

    Algorithm-level events render as a sibling "algorithms" subtree under
    each run-id node, so the per-leaf tree is unaffected.
    """

    def __init__(self) -> None:
        try:
            from rich.live import Live
            from rich.tree import Tree
        except ImportError as e:
            raise ImportError(_INSTALL_HINT) from e

        self._Tree = Tree
        self._runs: dict[str, dict[str, str]] = {}
        self._algos: dict[str, dict[str, list[str]]] = {}
        self._root = Tree("operad")
        self._live = Live(self._root, refresh_per_second=8, transient=False)
        self._live.start()
        self._started = True

    async def on_event(self, event: Event) -> None:
        if isinstance(event, AlgorithmEvent):
            self._on_algorithm_event(event)
        else:
            self._on_agent_event(event)
        self._rerender()

    def _on_agent_event(self, event: AgentEvent) -> None:
        run = self._runs.setdefault(event.run_id, {})
        if event.kind == "start":
            run[event.agent_path] = "running"
        elif event.kind == "end":
            run[event.agent_path] = "ok"
        elif event.kind == "error":
            err = type(event.error).__name__ if event.error is not None else "error"
            run[event.agent_path] = f"error: {err}"
        elif event.kind == "chunk":
            piece = event.metadata.get("text", "") if event.metadata else ""
            current = run.get(event.agent_path, "")
            prefix = "streaming: " if not current.startswith("streaming: ") else ""
            buf = (current[len("streaming: "):] if current.startswith("streaming: ") else "") + piece
            if len(buf) > 80:
                buf = "…" + buf[-79:]
            run[event.agent_path] = prefix + buf if prefix else "streaming: " + buf

    def _on_algorithm_event(self, event: AlgorithmEvent) -> None:
        algos = self._algos.setdefault(event.run_id, {})
        lines = algos.setdefault(event.algorithm_path, [])
        lines.append(_render_algorithm_line(event))

    def _rerender(self) -> None:
        tree = self._Tree("operad")
        run_ids = set(self._runs) | set(self._algos)
        for run_id in run_ids:
            node = tree.add(f"run {run_id[:8]}")
            paths = self._runs.get(run_id, {})
            for path, status in paths.items():
                node.add(f"{path} — {status}")
            algos = self._algos.get(run_id, {})
            if algos:
                algo_node = node.add("algorithms")
                for path, lines in algos.items():
                    sub = algo_node.add(path)
                    for line in lines:
                        sub.add(line)
        self._root = tree
        self._live.update(tree)

    def stop(self) -> None:
        if getattr(self, "_started", False):
            self._live.stop()
            self._started = False

    def __del__(self) -> Any:
        try:
            self.stop()
        except Exception:
            pass


def _render_algorithm_line(event: AlgorithmEvent) -> str:
    payload = event.payload
    if event.kind == "generation":
        idx = payload.get("gen_index", "?")
        scores = payload.get("population_scores", [])
        return f"gen {idx} scores={scores}"
    if event.kind == "round":
        idx = payload.get("round_index", "?")
        scores = payload.get("scores", [])
        return f"round {idx} scores={scores}"
    if event.kind == "cell":
        idx = payload.get("cell_index", "?")
        params = payload.get("parameters", {})
        return f"cell {idx} {params}"
    if event.kind == "candidate":
        idx = payload.get("candidate_index", "?")
        score = payload.get("score")
        return f"candidate {idx} score={score}"
    if event.kind == "iteration":
        idx = payload.get("iter_index", "?")
        phase = payload.get("phase", "")
        score = payload.get("score")
        return f"iter {idx} {phase} score={score}"
    return f"{event.kind} {payload}"
