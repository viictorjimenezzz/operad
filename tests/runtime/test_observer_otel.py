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

from operad import Agent, Sequential
from operad.runtime.observers import AgentEvent, OtelObserver
from operad.runtime.observers import registry as obs_registry
from operad.runtime.observers.base import _RUN_ID

from ..conftest import A, B, C, FakeLeaf


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
    pipe = await Sequential(first, second, input=A, output=C).abuild()

    obs_registry.register(OtelObserver())
    await pipe(A(text="hi"))

    spans = exporter.get_finished_spans()
    names = sorted(s.name for s in spans)
    # Sequential root + two stages (stage_0, stage_1).
    assert "Sequential" in names
    assert any(n.startswith("Sequential.stage_") for n in names)
    assert sum(1 for n in names if n.startswith("Sequential.stage_")) == 2


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
    span = obs._spans[("r1", "X", "")]
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


async def test_concurrent_same_run_and_path_do_not_collide(cfg, exporter) -> None:
    class SlowLeaf(Agent[A, B]):
        input = A
        output = B

        async def forward(self, x: A) -> B:  # type: ignore[override]
            await asyncio.sleep(0.01)
            return B(value=1)

    leaf = await SlowLeaf(config=cfg, input=A, output=B).abuild()
    obs_registry.register(OtelObserver())

    tok = _RUN_ID.set("d" * 32)
    try:
        await asyncio.gather(leaf(A(text="x")), leaf(A(text="y")))
    finally:
        _RUN_ID.reset(tok)

    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    run_ids = {_attrs(s)["operad.run_id"] for s in spans}
    assert run_ids == {"d" * 32}


async def test_root_span_trace_id_matches_run_id(cfg, exporter) -> None:
    """The root span's OTel trace_id must equal int(run_id, 16) so that
    Langfuse / OTel-backend deep-links of the form
    ``{backend}/trace/{run_id}`` resolve without any external mapping."""
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 1}
    ).abuild()

    obs_registry.register(OtelObserver())
    out = await leaf(A())

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    # OTel trace_id is a 128-bit int; render it as 32-hex to compare.
    rendered_trace_id = format(span.context.trace_id, "032x")
    assert rendered_trace_id == out.run_id


async def test_nested_spans_share_trace_id(cfg, exporter) -> None:
    first = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    second = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "ok"})
    pipe = await Sequential(first, second, input=A, output=C).abuild()

    obs_registry.register(OtelObserver())
    out = await pipe(A(text="hi"))

    spans = exporter.get_finished_spans()
    # Every span produced inside one root invocation must share the
    # root's trace_id, which itself must equal the run_id.
    trace_ids = {format(s.context.trace_id, "032x") for s in spans}
    assert trace_ids == {out.run_id}


async def test_gen_ai_attributes_on_leaf(cfg, exporter) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 7}
    ).abuild()

    obs_registry.register(OtelObserver())
    await leaf(A(text="hello"))

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    a = _attrs(spans[0])
    # `cfg` in tests is a llamacpp Configuration with a non-empty model;
    # gen_ai.* attributes are populated from the OperadOutput envelope.
    assert a.get("gen_ai.system")
    assert a.get("gen_ai.request.model")


async def test_tool_span_attributes(exporter) -> None:
    """ToolUser spans carry gen_ai.tool.* attributes."""
    from pydantic import BaseModel as PBM

    from operad.agents.reasoning.components.tool_user import ToolUser
    from operad.agents.reasoning.schemas import ToolCall, ToolResult

    class AddArgs(PBM):
        a: int
        b: int

    class AddResult(PBM):
        sum: int

    class AddTool:
        name = "add"
        args_schema = AddArgs
        result_schema = AddResult

        async def call(self, args: AddArgs) -> AddResult:
            return AddResult(sum=args.a + args.b)

    user = await ToolUser(tools={"add": AddTool()}).abuild()
    obs_registry.register(OtelObserver())
    await user(ToolCall(tool_name="add", args=AddArgs(a=3, b=4)))

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    a = _attrs(spans[0])

    assert a["gen_ai.tool.name"] == "add"
    assert a["gen_ai.tool.call.id"]
    assert '"a":3' in a["gen_ai.tool.arguments"]
    assert '"b":4' in a["gen_ai.tool.arguments"]
    assert '"sum":7' in a["gen_ai.tool.result"]
    assert '"ok":true' in a["gen_ai.tool.result"]


async def test_tool_span_argument_truncation(exporter) -> None:
    """gen_ai.tool.arguments is truncated to max_attr_length."""
    from pydantic import BaseModel as PBM

    from operad.agents.reasoning.components.tool_user import ToolUser
    from operad.agents.reasoning.schemas import ToolCall

    class BigArgs(PBM):
        data: str

    class BigResult(PBM):
        ok: bool = True

    class EchoTool:
        name = "echo"
        args_schema = BigArgs
        result_schema = BigResult

        async def call(self, args: BigArgs) -> BigResult:
            return BigResult()

    max_len = 32
    user = await ToolUser(tools={"echo": EchoTool()}).abuild()
    obs_registry.register(OtelObserver(max_attr_length=max_len))
    await user(ToolCall(tool_name="echo", args=BigArgs(data="x" * 200)))

    spans = exporter.get_finished_spans()
    a = _attrs(spans[0])
    assert len(a["gen_ai.tool.arguments"]) == max_len


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
