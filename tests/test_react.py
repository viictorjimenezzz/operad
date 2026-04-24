"""Tests for `operad.ReAct`: a typed 4-stage composition."""

from __future__ import annotations

from typing import Any

import pytest

from operad import Agent
from operad.agents import (
    Action,
    Actor,
    Answer,
    Evaluator,
    Extractor,
    Observation,
    ReAct,
    Reasoner,
    Task,
    Thought,
)


pytestmark = pytest.mark.asyncio


class _CannedLeaf(Agent[Any, Any]):
    """Sub-agent stand-in that returns a canned typed output."""

    def __init__(self, *, input: type, output: type, canned: dict[str, Any]) -> None:
        super().__init__(config=None, input=input, output=output)
        self.canned = canned

    async def forward(self, x: Any) -> Any:
        return self.output.model_construct(**self.canned)


def _stub_react(cfg) -> ReAct:
    """ReAct instance with every sub-agent swapped for a no-LLM stand-in."""
    r = ReAct(config=cfg)
    r.reasoner = _CannedLeaf(  # type: ignore[assignment]
        input=Task, output=Thought,
        canned={"reasoning": "think", "next_action": "search"},
    )
    r.actor = _CannedLeaf(  # type: ignore[assignment]
        input=Thought, output=Action,
        canned={"name": "search", "details": "search for 'x'"},
    )
    r.extractor = _CannedLeaf(  # type: ignore[assignment]
        input=Action, output=Observation,
        canned={"result": "found 42", "success": True},
    )
    r.evaluator = _CannedLeaf(  # type: ignore[assignment]
        input=Observation, output=Answer,
        canned={"reasoning": "given 42", "answer": "42"},
    )
    return r


async def test_react_graph_captures_four_typed_edges(cfg) -> None:
    r = await _stub_react(cfg).abuild()
    callees = {e.callee: e for e in r._graph.edges}
    assert set(callees) == {
        "ReAct.reasoner",
        "ReAct.actor",
        "ReAct.extractor",
        "ReAct.evaluator",
    }
    assert callees["ReAct.reasoner"].input_type is Task
    assert callees["ReAct.reasoner"].output_type is Thought
    assert callees["ReAct.actor"].input_type is Thought
    assert callees["ReAct.actor"].output_type is Action
    assert callees["ReAct.extractor"].input_type is Action
    assert callees["ReAct.extractor"].output_type is Observation
    assert callees["ReAct.evaluator"].input_type is Observation
    assert callees["ReAct.evaluator"].output_type is Answer


async def test_react_end_to_end_routes_through_stub_pipeline(cfg) -> None:
    r = await _stub_react(cfg).abuild()
    out = await r(Task(goal="what is the answer?"))
    assert isinstance(out.response, Answer)
    assert out.response.answer == "42"


async def test_react_subagents_use_component_defaults(cfg) -> None:
    """Sub-agents pull their role/task/rules from the component classes
    directly — ReAct doesn't override them inline."""
    r = ReAct(config=cfg)
    assert isinstance(r.reasoner, Reasoner) and r.reasoner.task == Reasoner.task
    assert isinstance(r.actor, Actor) and r.actor.task == Actor.task
    assert isinstance(r.extractor, Extractor) and r.extractor.task == Extractor.task
    assert isinstance(r.evaluator, Evaluator) and r.evaluator.task == Evaluator.task

    # Each sub-agent carries `cfg`; the composite itself is config-less.
    assert r.reasoner.config is cfg
    assert r.actor.config is cfg
    assert r.extractor.config is cfg
    assert r.evaluator.config is cfg
    assert r.config is None
