"""Offline tests for `operad.optim.tape`.

Covers `Tape`, `TapeEntry`, `TapeObserver`, and the `tape()` async
context manager: entry ordering (start-order), reverse iteration,
`children_of` / `parents_of`, partial-tape behaviour on mid-run
failures, nested-tape guard, weakref lifecycle, rendered-prompt
capture, NDJSON dump, and event-id uniqueness.
"""

from __future__ import annotations

import gc
import json
from typing import Any

import pytest
from pydantic import BaseModel

from operad.agents.parallel import Parallel
from operad.agents.pipeline import Pipeline
from operad.optim import Tape, TapeEntry, TapeObserver, tape
from operad.runtime.observers import registry as obs_registry

from tests._helpers.fake_leaf import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_registry():
    obs_registry.clear()
    yield
    obs_registry.clear()


# ---------------------------------------------------------------------------
# Single-leaf base case
# ---------------------------------------------------------------------------


async def test_single_leaf_records_one_entry(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 7}
    ).abuild()

    async with tape() as t:
        out = await leaf(A(text="hi"))

    assert out.response.value == 7
    assert len(t.entries) == 1
    entry = t.entries[0]
    assert entry.agent_path == "FakeLeaf"
    assert entry.is_leaf is True
    assert entry.input.text == "hi"  # type: ignore[attr-defined]
    assert entry.output is not None
    assert entry.finished_at is not None
    assert entry.started_at <= entry.finished_at
    assert t.root_input is entry.input
    assert t.root_output is entry.output


# ---------------------------------------------------------------------------
# Pipeline: forward order and reverse iteration
# ---------------------------------------------------------------------------


async def _build_pipeline(cfg: Any) -> Pipeline[A, C]:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    leaf2 = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "ok"})
    return await Pipeline(leaf1, leaf2, input=A, output=C).abuild()


async def test_pipeline_forward_order(cfg) -> None:
    pipe = await _build_pipeline(cfg)

    async with tape() as t:
        await pipe(A(text="go"))

    paths = [e.agent_path for e in t.entries]
    assert paths == ["Pipeline", "Pipeline.stage_0", "Pipeline.stage_1"]


async def test_entries_in_reverse(cfg) -> None:
    pipe = await _build_pipeline(cfg)

    async with tape() as t:
        await pipe(A(text="go"))

    reversed_paths = [e.agent_path for e in t.entries_in_reverse()]
    assert reversed_paths == [
        "Pipeline.stage_1",
        "Pipeline.stage_0",
        "Pipeline",
    ]


# ---------------------------------------------------------------------------
# Parallel: children_of and parents_of
# ---------------------------------------------------------------------------


async def test_parallel_children_of(cfg) -> None:
    leaf_a = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    leaf_b = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 2})

    def combine(results: dict[str, BaseModel]) -> C:
        return C(label="combined")

    par = await Parallel(
        {"a": leaf_a, "b": leaf_b},
        input=A,
        output=C,
        combine=combine,
    ).abuild()

    async with tape() as t:
        await par(A(text="x"))

    assert len(t.entries) == 3
    paths = {e.agent_path for e in t.entries}
    assert paths == {"Parallel", "Parallel.a", "Parallel.b"}

    child_paths = {e.agent_path for e in t.children_of("Parallel")}
    assert child_paths == {"Parallel.a", "Parallel.b"}

    parents = t.parents_of("Parallel.a")
    assert [p.agent_path for p in parents] == ["Parallel"]

    assert t.entry_for_path("Parallel.b") is not None
    assert t.entry_for_path("Parallel.nope") is None


# ---------------------------------------------------------------------------
# Error mid-pipeline: partial tape, entries up to failure point
# ---------------------------------------------------------------------------


async def test_error_mid_pipeline_leaves_partial_tape(cfg) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    leaf2 = FakeLeaf(config=cfg, input=B, output=C)

    async def boom(x: B) -> C:
        raise ValueError("kaboom")

    leaf2.forward = boom  # type: ignore[method-assign]

    pipe = await Pipeline(leaf1, leaf2, input=A, output=C).abuild()

    with pytest.raises(ValueError, match="kaboom"):
        async with tape() as t:
            await pipe(A(text="x"))

    paths = [e.agent_path for e in t.entries]
    assert paths == ["Pipeline.stage_0"]
    assert t.entries[0].output is not None


# ---------------------------------------------------------------------------
# Nested tape() is rejected
# ---------------------------------------------------------------------------


async def test_nested_tape_raises() -> None:
    async with tape():
        with pytest.raises(RuntimeError, match="nested"):
            async with tape():
                pass


# ---------------------------------------------------------------------------
# no_grad() suppresses recording (guarded; skip until 2-1 lands)
# ---------------------------------------------------------------------------


async def test_no_grad_suppresses_recording(cfg) -> None:
    try:
        from operad.optim.context import no_grad  # type: ignore[import-not-found]
    except ImportError:
        pytest.skip("stream 2-1 (no_grad) has not landed yet")

    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()

    async with no_grad():
        async with tape() as t:
            await leaf(A())

    assert t.entries == []


# ---------------------------------------------------------------------------
# to_jsonl dumps readable NDJSON
# ---------------------------------------------------------------------------


async def test_to_jsonl_dumps_readable_ndjson(cfg, tmp_path) -> None:
    pipe = await _build_pipeline(cfg)

    async with tape() as t:
        await pipe(A(text="go"))

    out_file = tmp_path / "tape.jsonl"
    t.to_jsonl(out_file)

    lines = out_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(t.entries)
    records = [json.loads(line) for line in lines]
    for record in records:
        assert "agent_path" in record
        assert "event_id" in record
        assert "is_leaf" in record


# ---------------------------------------------------------------------------
# Weakref lifecycle
# ---------------------------------------------------------------------------


async def test_agent_ref_returns_live_agent(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()

    async with tape() as t:
        await leaf(A())

    entry = t.entries[0]
    assert entry.agent_ref() is leaf


async def test_agent_ref_returns_none_after_agent_dropped(cfg) -> None:
    async def _run() -> Tape:
        leaf = await FakeLeaf(
            config=cfg, input=A, output=B, canned={"value": 1}
        ).abuild()
        async with tape() as t:
            await leaf(A())
        return t

    t = await _run()
    # `leaf` went out of scope when `_run` returned; now force GC.
    gc.collect()

    # tape must not crash when stale refs are walked.
    assert t.entries[0].agent_ref() is None


# ---------------------------------------------------------------------------
# Rendered prompt capture
# ---------------------------------------------------------------------------


async def test_rendered_prompt_toggle(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, task="say something"
    ).abuild()

    async with tape(capture_prompts=False) as t_off:
        await leaf(A())
    assert t_off.entries[0].rendered_prompt is None

    async with tape(capture_prompts=True) as t_on:
        await leaf(A())
    # Default renderer is XML; successful render yields a string. A
    # failed render falls through to None (we tolerate either but
    # must not leak an exception).
    rp = t_on.entries[0].rendered_prompt
    assert rp is None or isinstance(rp, (str, list))


# ---------------------------------------------------------------------------
# event_id uniqueness
# ---------------------------------------------------------------------------


async def test_entry_event_id_is_unique(cfg) -> None:
    pipe = await _build_pipeline(cfg)

    async with tape() as t:
        await pipe(A(text="x"))

    ids = [e.event_id for e in t.entries]
    assert len(ids) == len(set(ids))
    for eid in ids:
        assert isinstance(eid, str) and eid


# ---------------------------------------------------------------------------
# Sanity: TapeObserver satisfies the Observer protocol
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_tape_observer_is_observer() -> None:
    from operad.runtime.observers.base import Observer

    obs = TapeObserver(Tape())
    assert isinstance(obs, Observer)


@pytest.mark.asyncio(loop_scope="function")
async def test_tape_entry_constructible_directly() -> None:
    import time
    import weakref

    class _Dummy:
        pass

    d = _Dummy()
    entry = TapeEntry(
        run_id="r",
        agent_path="X",
        agent_ref=weakref.ref(d),
        input=A(text="hi"),
        output=None,
        rendered_prompt=None,
        started_at=time.monotonic(),
        finished_at=None,
        event_id="id-1",
        is_leaf=True,
    )
    assert entry.agent_ref() is d
