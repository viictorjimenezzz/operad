"""Offline tests for the streaming path (E-8)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
import strands

from operad import Agent, Configuration, OperadOutput
from operad.runtime.streaming import ChunkEvent
from operad.runtime.observers import base as _obs
from operad.utils.errors import BuildError

from ..conftest import A, B, FakeLeaf


class StreamLeaf(Agent[A, B]):
    """Default-forward leaf; streaming path engages when config.stream=True."""

    input = A
    output = B
    role = "test"
    task = "test"


def _make_fake_stream_async(events: list[dict[str, Any]]):
    async def _fake_stream_async(self: Any, *a: Any, **kw: Any):
        for ev in events:
            yield ev
    return _fake_stream_async


async def _build_leaf(cfg: Configuration) -> StreamLeaf:
    leaf = StreamLeaf(config=cfg)
    await leaf.abuild()
    return leaf


@pytest.mark.asyncio
async def test_stream_off_single_envelope(cfg: Configuration) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 7})
    await leaf.abuild()
    collected = [item async for item in leaf.stream(A(text="hi"))]
    assert len(collected) == 1
    assert isinstance(collected[0], OperadOutput)
    assert collected[0].response.value == 7

    invoked = await leaf(A(text="hi"))
    assert collected[0].response.value == invoked.response.value


@pytest.mark.asyncio
async def test_stream_on_three_chunks(
    cfg: Configuration, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_stream = cfg.model_copy(
        update={"io": cfg.io.model_copy(update={"stream": True})}
    )
    events = [
        {"data": "foo"},
        {"data": "bar"},
        {"data": "baz"},
        {"result": SimpleNamespace(structured_output=B(value=42))},
    ]
    monkeypatch.setattr(
        strands.Agent, "stream_async", _make_fake_stream_async(events)
    )

    leaf = await _build_leaf(cfg_stream)
    collected = [item async for item in leaf.stream(A(text="hi"))]

    chunks = [c for c in collected if isinstance(c, ChunkEvent)]
    envelopes = [c for c in collected if isinstance(c, OperadOutput)]
    assert [c.text for c in chunks] == ["foo", "bar", "baz"]
    assert [c.index for c in chunks] == [0, 1, 2]
    assert len(envelopes) == 1
    assert envelopes[0].response.value == 42
    assert collected[-1] is envelopes[0]


@pytest.mark.asyncio
async def test_stream_observers_receive_chunk_events(
    cfg: Configuration, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_stream = cfg.model_copy(
        update={"io": cfg.io.model_copy(update={"stream": True})}
    )
    events = [
        {"data": "a"},
        {"data": "b"},
        {"data": "c"},
        {"result": SimpleNamespace(structured_output=B(value=1))},
    ]
    monkeypatch.setattr(
        strands.Agent, "stream_async", _make_fake_stream_async(events)
    )

    recorded: list[_obs.AgentEvent] = []

    class MemObs:
        async def on_event(self, event: _obs.AgentEvent) -> None:
            recorded.append(event)

    obs = MemObs()
    _obs.registry.register(obs)
    try:
        leaf = await _build_leaf(cfg_stream)
        _ = [item async for item in leaf.stream(A(text="hi"))]
    finally:
        _obs.registry.unregister(obs)

    kinds = [e.kind for e in recorded]
    assert kinds == ["start", "chunk", "chunk", "chunk", "end"]
    chunks = [e for e in recorded if e.kind == "chunk"]
    assert [e.metadata["chunk_index"] for e in chunks] == [0, 1, 2]
    assert [e.metadata["text"] for e in chunks] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_stream_structured_parsing_from_text(
    cfg: Configuration, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_stream = cfg.model_copy(
        update={"io": cfg.io.model_copy(update={"stream": True})}
    )
    payload = json.dumps({"value": 99})
    events = [{"data": payload[:4]}, {"data": payload[4:]}]
    monkeypatch.setattr(
        strands.Agent, "stream_async", _make_fake_stream_async(events)
    )

    leaf = await _build_leaf(cfg_stream)
    collected = [item async for item in leaf.stream(A(text="hi"))]
    envelopes = [c for c in collected if isinstance(c, OperadOutput)]
    assert envelopes[0].response.value == 99


@pytest.mark.asyncio
async def test_stream_invoke_still_returns_envelope(
    cfg: Configuration, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_stream = cfg.model_copy(
        update={"io": cfg.io.model_copy(update={"stream": True})}
    )
    events = [
        {"data": "x"},
        {"result": SimpleNamespace(structured_output=B(value=3))},
    ]
    monkeypatch.setattr(
        strands.Agent, "stream_async", _make_fake_stream_async(events)
    )

    leaf = await _build_leaf(cfg_stream)
    out = await leaf(A(text="hi"))
    assert isinstance(out, OperadOutput)
    assert out.response.value == 3


@pytest.mark.asyncio
async def test_stream_parse_failure_raises_output_mismatch(
    cfg: Configuration, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_stream = cfg.model_copy(
        update={"io": cfg.io.model_copy(update={"stream": True})}
    )
    events = [{"data": "not json at all"}]
    monkeypatch.setattr(
        strands.Agent, "stream_async", _make_fake_stream_async(events)
    )

    leaf = await _build_leaf(cfg_stream)
    with pytest.raises(BuildError) as ei:
        _ = [item async for item in leaf.stream(A(text="hi"))]
    assert ei.value.reason == "output_mismatch"
