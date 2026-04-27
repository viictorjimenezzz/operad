"""Background `Trainer.fit` launcher for Studio's train button."""

from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TrainingStatus:
    started: bool = False
    finished: bool = False
    error: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    bundle_out: str | None = None


class TrainingLauncher:
    """Coordinates one background training task per job.

    Usage::

        launcher = TrainingLauncher()
        await launcher.start("job-a.jsonl", bundle_path=..., data_dir=...)
        async for event in launcher.stream("job-a.jsonl"):
            ...
    """

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._statuses: dict[str, TrainingStatus] = {}
        self._event_queues: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    def status(self, job_name: str) -> TrainingStatus | None:
        return self._statuses.get(job_name)

    def subscribe(self, job_name: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._event_queues.setdefault(job_name, []).append(q)
        # Replay prior events so latecomers see full history.
        status = self._statuses.get(job_name)
        if status is not None:
            for ev in status.events:
                try:
                    q.put_nowait(ev)
                except asyncio.QueueFull:
                    break
        return q

    def unsubscribe(self, job_name: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        queues = self._event_queues.get(job_name, [])
        try:
            queues.remove(q)
        except ValueError:
            pass

    async def start(
        self,
        job_name: str,
        *,
        bundle_path: Path,
        ratings_path: Path,
        data_dir: Path,
        epochs: int = 1,
        lr: float = 1.0,
        dashboard_port: int | None = None,
        runner: Any = None,
    ) -> bool:
        """Start training for ``job_name`` unless already running.

        ``runner`` is an optional async callable used by tests to stub
        out the real `Trainer.fit` round-trip; if None, the default
        runner uses `Trainer.load` + `HumanFeedbackLoss`.
        """
        existing = self._tasks.get(job_name)
        if existing is not None and not existing.done():
            return False
        self._statuses[job_name] = TrainingStatus(started=True)
        task = asyncio.create_task(
            self._run(
                job_name,
                bundle_path=bundle_path,
                ratings_path=ratings_path,
                data_dir=data_dir,
                epochs=epochs,
                lr=lr,
                dashboard_port=dashboard_port,
                runner=runner,
            )
        )
        self._tasks[job_name] = task
        return True

    async def _run(
        self,
        job_name: str,
        *,
        bundle_path: Path,
        ratings_path: Path,
        data_dir: Path,
        epochs: int,
        lr: float,
        dashboard_port: int | None,
        runner: Any,
    ) -> None:
        status = self._statuses[job_name]
        try:
            self._emit(job_name, {"kind": "started", "job": job_name})
            if runner is None:
                runner = _default_runner
            bundle_out = await runner(
                bundle_path=bundle_path,
                ratings_path=ratings_path,
                data_dir=data_dir,
                job_name=job_name,
                epochs=epochs,
                lr=lr,
                dashboard_port=dashboard_port,
                on_event=lambda ev: self._emit(job_name, ev),
            )
            status.bundle_out = str(bundle_out) if bundle_out else None
            self._emit(
                job_name,
                {"kind": "finished", "job": job_name, "bundle_out": status.bundle_out},
            )
        except Exception as exc:  # pragma: no cover — defensive
            status.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            self._emit(
                job_name,
                {"kind": "error", "job": job_name, "error": str(exc)},
            )
        finally:
            status.finished = True

    def _emit(self, job_name: str, event: dict[str, Any]) -> None:
        status = self._statuses.setdefault(job_name, TrainingStatus())
        status.events.append(event)
        for q in list(self._event_queues.get(job_name, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass


async def _default_runner(
    *,
    bundle_path: Path,
    ratings_path: Path,
    data_dir: Path,
    job_name: str,
    epochs: int,
    lr: float,
    dashboard_port: int | None,
    on_event: Any,
) -> Path:
    """Load the saved trainer bundle, run fit with `HumanFeedbackLoss`.

    Exports the trained agent to ``data_dir / "{job_name}-trained.json"``
    so the Studio index lists it for the next round.
    """
    from operad.optim.optimizers.optimizer import Optimizer
    from operad.optim.optimizers.tgd import TextualGradientDescent
    from operad.train import HumanFeedbackLoss, Trainer

    # Dashboard forwarding — optional, scoped to this call.
    attached = None
    if dashboard_port is not None:
        try:
            from operad import dashboard as operad_dashboard
            attached = operad_dashboard.attach(port=dashboard_port)
        except Exception:
            attached = None

    loss_fn = HumanFeedbackLoss(ratings_path)

    def _opt_factory(agent: Any) -> Optimizer:
        return TextualGradientDescent(list(agent.parameters()), lr=lr)

    trainer = Trainer.load(
        bundle_path,
        loss_fn=loss_fn,
        optimizer_factory=_opt_factory,
    )

    # Build a tiny dataset from the ratings file for the fit loop.
    from operad.benchmark.dataset import Dataset
    from operad.benchmark.entry import Entry
    from operad.data.loader import DataLoader

    rows = []
    for line in ratings_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        import json as _json
        try:
            rows.append(_json.loads(line))
        except Exception:
            continue

    # Use the agent's input / output types to reconstruct entries.
    agent = trainer.agent
    input_cls = agent.input
    output_cls = agent.output
    entries: list[Entry[Any, Any]] = []
    for row in rows:
        try:
            x = input_cls.model_validate(row.get("input"))
            y = output_cls.model_validate(row.get("predicted"))
            entries.append(Entry(input=x, expected_output=y))
        except Exception:
            continue
    if not entries:
        on_event({"kind": "error", "error": "no valid entries"})
        raise RuntimeError("no valid entries in ratings file")

    ds = Dataset(entries, name=job_name, version="human-feedback")
    loader = DataLoader(ds, batch_size=1)

    on_event({"kind": "fit_start", "entries": len(entries), "epochs": epochs})
    try:
        await trainer.fit(loader, epochs=epochs)
    finally:
        if attached is not None:
            try:
                from operad.runtime.observers.base import registry
                registry.unregister(attached)
            except Exception:
                pass

    bundle_out = data_dir / f"{job_name}-trained.json"
    trainer.save(bundle_out)
    on_event({"kind": "saved", "bundle_out": str(bundle_out)})
    return bundle_out


__all__ = ["TrainingLauncher", "TrainingStatus"]
