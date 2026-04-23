"""Live dashboard observer backed by `rich`.

Optional: the `rich` package is only required at construction time. If
not installed, the constructor raises with a clear install hint.
"""

from __future__ import annotations

from typing import Any

from .base import AgentEvent


_INSTALL_HINT = (
    "RichDashboardObserver requires `rich`. Install the observers extra:\n"
    "    uv add 'operad[observers]'\n"
    "or install rich directly: `uv add rich`."
)


class RichDashboardObserver:
    """Live tree of in-flight agents, one subtree per run_id."""

    def __init__(self) -> None:
        try:
            from rich.live import Live
            from rich.tree import Tree
        except ImportError as e:
            raise ImportError(_INSTALL_HINT) from e

        self._Tree = Tree
        self._runs: dict[str, dict[str, str]] = {}
        self._root = Tree("operad")
        self._live = Live(self._root, refresh_per_second=8, transient=False)
        self._live.start()
        self._started = True

    async def on_event(self, event: AgentEvent) -> None:
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
        self._rerender()

    def _rerender(self) -> None:
        tree = self._Tree("operad")
        for run_id, paths in self._runs.items():
            node = tree.add(f"run {run_id[:8]}")
            for path, status in paths.items():
                node.add(f"{path} — {status}")
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
