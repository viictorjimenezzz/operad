"""Tests for the leaf agents under `operad.agents.reasoning.components`."""

from __future__ import annotations
from typing import Literal
import pytest
from pydantic import BaseModel, Field
from operad.agents import Action, Actor, Answer, Classifier, Critic, Evaluator, Extractor, Observation, Planner, Reasoner, Thought
from operad.algorithms import Candidate, Score
from operad import Example
from operad.agents import Critic
from typing import Any
from operad import Agent
from operad.agents import Action, Actor, Answer, Evaluator, Extractor, Observation, ReAct, Reasoner, Task, Thought
from operad.agents import Reflection, ReflectionInput, Reflector
from operad.agents import Hit, Hits, Query, Retriever
from typing import Any, Literal
from operad.agents import Choice, RouteInput, Router


# --- from test_reasoning_components.py ---
class _Question(BaseModel):
    text: str = Field(default="", description="The user's question.")


class _Reasoning(BaseModel):
    reasoning: str = Field(default="")
    answer: str = Field(default="")


class _Review(BaseModel):
    text: str = Field(default="")


class _Sentiment(BaseModel):
    label: Literal["positive", "negative", "neutral"] = "neutral"


class _Goal(BaseModel):
    goal: str = Field(default="")


class _Plan(BaseModel):
    steps: list[str] = Field(default_factory=list)


class _Doc(BaseModel):
    text: str = Field(default="")


class _Facts(BaseModel):
    facts: list[str] = Field(default_factory=list)


LEAF_SPECS = [
    (Reasoner, _Question, _Reasoning),
    (Extractor, _Doc, _Facts),
    (Classifier, _Review, _Sentiment),
    (Planner, _Goal, _Plan),
    (Actor, Thought, Action),
    (Evaluator, Observation, Answer),
]


@pytest.mark.parametrize("cls,in_cls,out_cls", LEAF_SPECS)
def test_leaf_defaults_are_populated(cfg, cls, in_cls, out_cls) -> None:
    leaf = cls(config=cfg, input=in_cls, output=out_cls)
    assert leaf.role, f"{cls.__name__}.role is empty"
    assert leaf.task, f"{cls.__name__}.task is empty"
    assert leaf.rules, f"{cls.__name__}.rules is empty"
    assert leaf.input is in_cls
    assert leaf.output is out_cls


@pytest.mark.parametrize("cls,in_cls,out_cls", LEAF_SPECS)
def test_leaf_task_override_wins(cfg, cls, in_cls, out_cls) -> None:
    leaf = cls(config=cfg, input=in_cls, output=out_cls, task="custom-task")
    assert leaf.task == "custom-task"


def test_subclass_can_specialize_class_attrs(cfg) -> None:
    class SentimentClassifier(Classifier):
        input = _Review
        output = _Sentiment
        task = "Classify the review's overall sentiment."

    leaf = SentimentClassifier(config=cfg)
    assert leaf.input is _Review
    assert leaf.output is _Sentiment
    assert leaf.task == "Classify the review's overall sentiment."
    assert leaf.role == Classifier.role  # inherited default


def test_critic_input_output_are_fixed(cfg) -> None:
    critic = Critic(config=cfg)
    assert critic.input is Candidate
    assert critic.output is Score
    assert critic.role and critic.task and critic.rules

# --- from test_reasoning_examples.py ---
def test_critic_examples_are_typed_pairs() -> None:
    assert len(Critic.examples) >= 1
    for ex in Critic.examples:
        assert isinstance(ex, Example)
        assert isinstance(ex.input, Candidate)
        assert isinstance(ex.output, Score)
        assert 0.0 <= ex.output.score <= 1.0


def test_generic_leaves_ship_empty_class_examples() -> None:
    from operad.agents import (
        Actor,
        Classifier,
        Evaluator,
        Extractor,
        Planner,
        Reasoner,
    )

    for leaf in (Reasoner, Actor, Extractor, Evaluator, Classifier, Planner):
        assert leaf.examples == ()

# --- from test_react.py ---
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

# --- from test_reflector.py ---
pytestmark = pytest.mark.asyncio


class _StubReflector(Reflector):
    """Skip the real model call by overriding forward with canned output."""

    def __init__(self, *, canned: Reflection) -> None:
        super().__init__(config=None, input=ReflectionInput, output=Reflection)
        self._canned = canned

    async def forward(self, x: Any) -> Any:
        return self._canned


async def test_reflector_class_level_defaults_are_preserved() -> None:
    canned = Reflection(needs_revision=False, deficiencies=[], suggested_revision="")
    r = _StubReflector(canned=canned)
    assert r.role == Reflector.role
    assert r.task == Reflector.task
    assert tuple(r.rules) == tuple(Reflector.rules)
    assert len(r.examples) == 1


async def test_reflector_stub_produces_typed_reflection() -> None:
    canned = Reflection(
        needs_revision=True,
        deficiencies=["off-by-one"],
        suggested_revision="Use < instead of <=.",
    )
    r = await _StubReflector(canned=canned).abuild()
    out = await r(ReflectionInput(original_request="q", candidate_answer="a"))
    assert isinstance(out.response, Reflection)
    assert out.response.needs_revision is True
    assert out.response.deficiencies == ["off-by-one"]


async def test_reflector_is_registered_as_a_leaf_agent() -> None:
    r = _StubReflector(canned=Reflection(needs_revision=False))
    assert isinstance(r, Agent)
    assert not r._children

# --- from test_retriever.py ---
pytestmark = pytest.mark.asyncio


async def test_retriever_builds_without_config_and_returns_typed_hits() -> None:
    canned = [
        Hit(text="one", score=0.9, source="a"),
        Hit(text="two", score=0.4, source="b"),
    ]

    async def lookup(q: Query) -> list[Hit]:
        assert isinstance(q, Query)
        return canned

    r = Retriever(lookup=lookup)
    assert r.config is None
    await r.abuild()

    out = await r(Query(text="hello", k=2))
    assert isinstance(out.response, Hits)
    assert [h.text for h in out.response.items] == ["one", "two"]
    assert out.response.items[0].score == 0.9


async def test_retriever_passes_query_through() -> None:
    seen: list[Query] = []

    async def lookup(q: Query) -> list[Hit]:
        seen.append(q)
        return []

    r = await Retriever(lookup=lookup).abuild()
    seen.clear()  # discard the trace-time sentinel call
    await r(Query(text="foo", k=3))
    assert len(seen) == 1
    assert seen[0].text == "foo"
    assert seen[0].k == 3

# --- from test_router.py ---
pytestmark = pytest.mark.asyncio


class Mode(Choice[Literal["search", "compute"]]):
    pass


class _StubRouter(Router):
    def __init__(self, *, label: str) -> None:
        super().__init__(config=None, input=RouteInput, output=Mode)
        self._label = label

    async def forward(self, x: Any) -> Any:
        return Mode(label=self._label, reasoning="stub")  # type: ignore[arg-type]


async def test_router_emits_typed_choice() -> None:
    r = await _StubRouter(label="search").abuild()
    out = await r(RouteInput(query="find Paris"))
    assert isinstance(out.response, Mode)
    assert out.response.label == "search"
    assert out.response.reasoning == "stub"


async def test_router_default_output_is_choice_str_alias() -> None:
    # The bare class-level default uses Choice[str]. Instances typically
    # narrow via a subclass at construction.
    assert Router.output is not None
