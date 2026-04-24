"""OpenTelemetry observer tests.

Skips cleanly when the `[otel]` extra isn't installed.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

pytest.importorskip("opentelemetry")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from operad import Agent, Pipeline
from operad.runtime.observers import AgentEvent, OtelObserver
from operad.runtime.observers import registry as obs_registry

from .conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_registry():
    obs_registry.clear()
    yield
    obs_registry.clear()


@pytest.fixture
def exporter():
    """Install a fresh TracerProvider with an in-memory exporter per test."""
    provider = TracerProvider()
    exp = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exp))
    # Replace global; OTel's set_tracer_provider logs a warning on double-set
    # but still honors the override — acceptable for tests.
    trace._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    trace.set_tracer_provider(provider)
    yield exp
    exp.clear()


def _attrs(span) -> dict[str, Any]:
    return dict(span.attributes or {})


async def test_span_per_leaf(cfg, exporter) -> None:
    first = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    second = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "ok"})
    pipe = await Pipeline(first, second, input=A, output=C).abuild()

    obs_registry.register(OtelObserver())
    await pipe(A(text="hi"))

    spans = exporter.get_finished_spans()
    names = sorted(s.name for s in spans)
    # Pipeline root + two stages (stage_0, stage_1).
    assert "Pipeline" in names
    assert any(n.startswith("Pipeline.stage_") for n in names)
    assert sum(1 for n in names if n.startswith("Pipeline.stage_")) == 2


async def test_span_attributes_on_leaf(cfg, exporter) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 7}
    ).abuild()

    obs_registry.register(OtelObserver())
    await leaf(A(text="hello"))

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    a = _attrs(spans[0])

    assert a["operad.agent_path"] == "FakeLeaf"
    assert a["operad.run_id"]
    # Start-time attributes.
    assert "operad.hash_input" in a
    # End-time envelope attributes (populated from OperadOutput).
    assert a["operad.hash_prompt"]
    assert a["operad.hash_model"]
    assert a["operad.hash_output_schema"]
    assert a["operad.hash_graph"]
    assert a["operad.hash_operad_version"]
    assert a["operad.hash_python_version"]
    assert a["operad.latency_ms"] >= 0.0
    assert a["operad.chunks"] == 0


async def test_error_path_sets_error_status(cfg, exporter) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()

    async def boom(x: A) -> B:
        raise ValueError("kaboom")

    leaf.forward = boom  # type: ignore[method-assign]

    obs_registry.register(OtelObserver())
    with pytest.raises(ValueError):
        await leaf(A())

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == StatusCode.ERROR
    exc_events = [e for e in span.events if e.name == "exception"]
    assert len(exc_events) == 1
    assert exc_events[0].attributes.get("exception.type", "").endswith("ValueError")


async def test_no_payload_leakage(cfg, exporter) -> None:
    marker = "SECRET_PAYLOAD_MARKER_9f8e7"
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 42}
    ).abuild()

    obs_registry.register(OtelObserver())
    await leaf(A(text=marker))

    spans = exporter.get_finished_spans()
    for span in spans:
        for _, v in (span.attributes or {}).items():
            if isinstance(v, str):
                assert marker not in v


async def test_chunk_counter_direct() -> None:
    obs = OtelObserver()
    key_event_start = AgentEvent(
        run_id="r1",
        agent_path="X",
        kind="start",
        input=None,
        output=None,
        error=None,
        started_at=time.monotonic(),
        finished_at=None,
        metadata={},
    )
    await obs.on_event(key_event_start)
    for _ in range(3):
        await obs.on_event(
            AgentEvent(
                run_id="r1",
                agent_path="X",
                kind="chunk",
                input=None,
                output=None,
                error=None,
                started_at=time.monotonic(),
                finished_at=None,
                metadata={"text": "x"},
            )
        )
    # The span is live; we can read its recorded attribute set after end.
    span = obs._spans[("r1", "X")]
    await obs.on_event(
        AgentEvent(
            run_id="r1",
            agent_path="X",
            kind="end",
            input=None,
            output=None,
            error=None,
            started_at=0.0,
            finished_at=time.monotonic(),
            metadata={},
        )
    )
    assert dict(span.attributes)["operad.chunks"] == 3


async def test_concurrent_runs_keyed_by_run_id(cfg, exporter) -> None:
    leaf1 = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 1}
    ).abuild()
    leaf2 = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 2}
    ).abuild()

    obs_registry.register(OtelObserver())
    await asyncio.gather(leaf1(A()), leaf2(A()))

    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    run_ids = {_attrs(s)["operad.run_id"] for s in spans}
    assert len(run_ids) == 2


async def test_missing_opentelemetry_raises(monkeypatch) -> None:
    import builtins
    import sys

    # Ensure a fresh import attempt happens inside __init__.
    for name in list(sys.modules):
        if name == "opentelemetry" or name.startswith("opentelemetry."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    real_import = builtins.__import__

    def _deny(name, *args, **kwargs):
        if name == "opentelemetry" or name.startswith("opentelemetry."):
            raise ImportError(f"blocked: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _deny)

    with pytest.raises(RuntimeError, match=r"\[otel\]"):
        OtelObserver()
