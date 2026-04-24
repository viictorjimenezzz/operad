"""Tests for `trace_diff`."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from operad import Trace
from operad.runtime.trace import TraceStep
from operad.runtime.trace_diff import TraceDiff, trace_diff
from operad.core.output import OperadOutput


class _Resp(BaseModel):
    value: str = ""


def _step(
    path: str,
    *,
    hash_prompt: str = "",
    hash_input: str = "",
    hash_graph: str = "g0",
    latency_ms: float = 10.0,
    value: str = "v",
    error: str | None = None,
) -> TraceStep:
    output = OperadOutput[Any].model_construct(
        response=_Resp(value=value),
        hash_prompt=hash_prompt,
        hash_input=hash_input,
        hash_graph=hash_graph,
        latency_ms=latency_ms,
        agent_path=path,
    )
    return TraceStep(agent_path=path, output=output, error=error)


def _trace(run_id: str, steps: list[TraceStep]) -> Trace:
    return Trace.model_construct(run_id=run_id, steps=steps)


def test_identical_traces_all_unchanged() -> None:
    steps = [
        _step("Root.a", hash_prompt="p1", hash_input="i1"),
        _step("Root.b", hash_prompt="p2", hash_input="i2"),
    ]
    t1 = _trace("r1", steps)
    t2 = _trace("r2", [_step(s.agent_path,
                             hash_prompt=s.output.hash_prompt,
                             hash_input=s.output.hash_input,
                             latency_ms=s.output.latency_ms)
                       for s in steps])
    d = trace_diff(t1, t2)
    assert d.graphs_match is True
    assert [s.status for s in d.steps] == ["unchanged", "unchanged"]
    assert bool(d) is False


def test_changed_prompt_hash() -> None:
    t1 = _trace("r1", [_step("Root.a", hash_prompt="p1", hash_input="i1")])
    t2 = _trace("r2", [_step("Root.a", hash_prompt="p2", hash_input="i1")])
    d = trace_diff(t1, t2)
    assert len(d.steps) == 1
    s = d.steps[0]
    assert s.status == "changed"
    assert s.prev_hash_prompt == "p1"
    assert s.next_hash_prompt == "p2"
    assert "prompt hash diff" in s.reasons
    assert bool(d) is True


def test_removed_step() -> None:
    t1 = _trace("r1", [_step("Root.a"), _step("Root.b", hash_prompt="px")])
    t2 = _trace("r2", [_step("Root.a")])
    d = trace_diff(t1, t2)
    removed = [s for s in d.steps if s.status == "removed"]
    assert len(removed) == 1
    assert removed[0].agent_path == "Root.b"
    assert removed[0].prev_hash_prompt == "px"
    assert removed[0].next_hash_prompt == ""


def test_added_step() -> None:
    t1 = _trace("r1", [_step("Root.a")])
    t2 = _trace("r2", [_step("Root.a"), _step("Root.c", hash_prompt="pc")])
    d = trace_diff(t1, t2)
    added = [s for s in d.steps if s.status == "added"]
    assert len(added) == 1
    assert added[0].agent_path == "Root.c"
    assert added[0].next_hash_prompt == "pc"
    assert added[0].prev_hash_prompt == ""


def test_graph_hash_mismatch() -> None:
    t1 = _trace("r1", [_step("Root.a", hash_graph="g1")])
    t2 = _trace("r2", [_step("Root.a", hash_graph="g2")])
    d = trace_diff(t1, t2)
    assert d.graphs_match is False
    assert d.prev_hash_graph == "g1"
    assert d.next_hash_graph == "g2"


def test_error_step_skips_hash_compare() -> None:
    t1 = _trace("r1", [_step("Root.a", hash_prompt="p1")])
    t2 = _trace("r2", [_step("Root.a", hash_prompt="p2", error="Boom: x")])
    d = trace_diff(t1, t2)
    s = d.steps[0]
    assert s.status == "changed"
    assert s.next_error == "Boom: x"
    assert "prompt hash diff" not in s.reasons
    assert "error differs" in s.reasons


def test_latency_tolerance() -> None:
    t1 = _trace("r1", [_step("Root.a", hash_prompt="p", hash_input="i",
                              latency_ms=10.0)])
    t2 = _trace("r2", [_step("Root.a", hash_prompt="p", hash_input="i",
                              latency_ms=14.0)])
    d = trace_diff(t1, t2)
    assert d.steps[0].status == "changed"
    d2 = trace_diff(t1, t2, latency_tolerance_ms=10.0)
    assert d2.steps[0].status == "unchanged"


def test_str_render_is_legible() -> None:
    t1 = _trace("abcdef1234", [_step("Root.a", hash_prompt="p1")])
    t2 = _trace("ghijkl5678", [_step("Root.a", hash_prompt="p2")])
    text = str(trace_diff(t1, t2))
    assert "trace_diff" in text
    assert "Root.a" in text
    assert "changed" in text


def test_repr_html_has_table() -> None:
    t1 = _trace("r1", [_step("Root.a", hash_prompt="p1")])
    t2 = _trace("r2", [_step("Root.a", hash_prompt="p2")])
    html = trace_diff(t1, t2)._repr_html_()
    assert "<table>" in html
    assert "Root.a" in html


def test_type_is_tracediff() -> None:
    t1 = _trace("r1", [])
    t2 = _trace("r2", [])
    d = trace_diff(t1, t2)
    assert isinstance(d, TraceDiff)
