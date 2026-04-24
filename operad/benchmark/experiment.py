"""`Experiment` — content-addressed bundle of agent, dataset, metrics, traces.

An ``Experiment`` is the reproducibility container: one subject ``agent``,
one ``Dataset`` of inputs and expected outputs, zero or more ``Metric``
implementations, and — after ``run()`` — every ``Trace`` the observer saw
plus the final ``EvalReport``. ``save(folder)`` writes a deterministic
multi-file layout; ``load(folder)`` reconstitutes the state.

v1 limitations:
- ``run()`` is not reentrant. ``TraceObserver`` registers against the
  global observer registry, so two concurrent ``Experiment.run()`` calls
  would cross-capture each other's traces.
- Metrics do not round-trip through JSON. ``save()`` records the metric
  names; ``load()`` returns ``metrics=[]`` and the caller re-supplies
  implementations if they want to re-run.
- Agent reconstruction requires the agent's class to be importable at a
  dotted module path. Throwaway subclasses defined inside a function or
  a test file without a stable import path cannot be loaded.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..core.agent import Agent
from ..core.freeze import (
    _new_agent,
    _qualified_class_name,
    _redact_state,
    _resolve_class,
)
from ..core.graph import to_json as _graph_to_json
from ..core.state import AgentState
from ..metrics.base import Metric
from ..runtime.observers.base import registry
from ..runtime.trace import Trace, TraceObserver
from ..utils.errors import BuildError
from ..utils.hashing import hash_json
from .dataset import Dataset
from .evaluate import EvalReport, evaluate


class Experiment:
    """Agent × Dataset × Metrics + captured traces + final report."""

    def __init__(
        self,
        *,
        agent: Agent[Any, Any],
        dataset: Dataset[Any, Any],
        metrics: list[Metric],
        name: str = "",
    ) -> None:
        self.agent = agent
        self.dataset = dataset
        self.metrics: list[Metric] = list(metrics)
        self.name = name
        self.report: EvalReport | None = None
        self.traces: list[Trace] = []

    @property
    def experiment_id(self) -> str:
        """Stable 16-hex content address.

        Function of ``agent.hash_content``, ``dataset.hash_dataset``, the
        sorted metric names, and ``name``. Identical inputs produce
        identical IDs across machines.
        """
        parts = {
            "agent": self.agent.hash_content,
            "dataset": self.dataset.hash_dataset,
            "metrics": sorted(m.name for m in self.metrics),
            "name": self.name,
        }
        return hash_json(parts)

    async def run(self, *, concurrency: int = 4) -> EvalReport:
        """Evaluate the agent on the dataset, capturing every trace."""
        if not self.agent._built:
            raise BuildError(
                "not_built",
                "call .build() on the agent before Experiment.run()",
                agent=type(self.agent).__name__,
            )
        observer = TraceObserver()
        registry.register(observer)
        try:
            report = await evaluate(
                self.agent,
                self.dataset,
                self.metrics,
                concurrency=concurrency,
            )
        finally:
            registry.unregister(observer)
        self.traces = sorted(observer.all(), key=lambda t: t.run_id)
        self.report = report
        return report

    def save(self, folder: str | Path) -> Path:
        """Write the experiment to ``folder`` as six artefacts + a traces dir.

        Layout::

            folder/manifest.json
            folder/graph.json
            folder/state.json
            folder/dataset.ndjson
            folder/report.json
            folder/traces/<run_id>.json

        ``state.json`` is written with ``config.api_key`` stripped,
        matching ``freeze``'s redaction policy.
        """
        if self.report is None:
            raise ValueError(
                "Experiment.save(): call run() before save() — no report"
            )
        p = Path(folder)
        p.mkdir(parents=True, exist_ok=True)
        (p / "traces").mkdir(exist_ok=True)

        state = _redact_state(self.agent.state())
        _write_json(p / "state.json", state.model_dump(mode="json"))

        graph_json: dict[str, Any] = {}
        if self.agent._graph is not None:
            graph_json = _graph_to_json(self.agent._graph)
        _write_json(p / "graph.json", graph_json)

        self.dataset.save(p / "dataset.ndjson")

        _write_json(p / "report.json", self.report.model_dump(mode="json"))

        run_ids = sorted(t.run_id for t in self.traces)
        by_id = {t.run_id: t for t in self.traces}
        for rid in run_ids:
            by_id[rid].save(p / "traces" / f"{rid}.json")

        manifest = {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "agent_class": _qualified_class_name(type(self.agent)),
            "agent_hash_content": self.agent.hash_content,
            "dataset_name": self.dataset.name,
            "dataset_version": self.dataset.version,
            "dataset_hash": self.dataset.hash_dataset,
            "metrics": sorted(m.name for m in self.metrics),
            "created_at": time.time(),
            "trace_run_ids": run_ids,
        }
        _write_json(p / "manifest.json", manifest)
        return p

    @classmethod
    def load(cls, folder: str | Path) -> "Experiment":
        """Reconstitute an Experiment from a folder written by ``save``.

        The returned experiment has ``metrics=[]`` — metric
        implementations do not round-trip through JSON; re-supply them
        on the returned object if you want to re-run.
        """
        p = Path(folder)
        manifest = json.loads((p / "manifest.json").read_text(encoding="utf-8"))

        agent_cls = _resolve_class(manifest["agent_class"])
        state = AgentState.model_validate_json(
            (p / "state.json").read_text(encoding="utf-8")
        )
        class_input = getattr(agent_cls, "input", None)
        class_output = getattr(agent_cls, "output", None)
        if class_input is None or class_output is None:
            raise BuildError(
                "not_built",
                f"cannot load Experiment: {manifest['agent_class']} has no "
                f"class-level input/output types",
            )
        agent = _new_agent(agent_cls, state, (class_input, class_output))

        dataset = Dataset.load(
            p / "dataset.ndjson",
            in_cls=class_input,
            out_cls=class_output,
            name=manifest.get("dataset_name", ""),
            version=manifest.get("dataset_version", ""),
        )

        exp = cls(
            agent=agent,
            dataset=dataset,
            metrics=[],
            name=manifest.get("name", ""),
        )
        exp.report = EvalReport.model_validate_json(
            (p / "report.json").read_text(encoding="utf-8")
        )
        trace_files = sorted(
            (p / "traces").glob("*.json"), key=lambda x: x.stem
        )
        exp.traces = [Trace.load(f) for f in trace_files]
        return exp


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, sort_keys=True, indent=2), encoding="utf-8"
    )


__all__ = ["Experiment"]
