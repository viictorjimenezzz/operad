"""ReAct: Reason → Act → Observe → Evaluate, as a typed Agent pipeline.

A one-pass ReAct composition over four leaf agents, all pulled from
``operad.agents.reasoning.components``:

* **Reasoner**  (``Task -> Thought``) — deliberate on the task.
* **Actor**     (``Thought -> Action``) — decide a concrete next step.
* **Extractor** (``Action -> Observation``) — synthesize what the action
  produces. In a tool-using setting this would parse tool output; here
  the LLM simulates the outcome.
* **Evaluator** (``Observation -> Answer``) — commit to a final answer.

Each sub-component has its own typed input and output so every edge is
checked at ``build()`` time. ReAct itself is an ``Agent[Task, Answer]``
so it nests inside any higher-level composition exactly like any other
leaf.

This is *single-pass* ReAct — no iteration, no tool execution. The
iterative looping variant is an algorithm (future ``VerifierLoop``)
because the loop is metric-driven, not purely structural.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ...core.agent import Agent, _TRACER
from ...core.config import Configuration
from ...core.flow import Loop, Sequential
from .components import Actor, Evaluator, Extractor, Reasoner
from .schemas import Action, Answer, Observation, Task, Thought


# --- composition -------------------------------------------------------------


class _ReActState(BaseModel):
    task: Task | None = None
    thought: Thought | None = None
    action: Action | None = None
    observation: Observation | None = None
    answer: Answer | None = None


class _InitState(Agent[Task, _ReActState]):
    input = Task
    output = _ReActState

    async def forward(self, x: Task) -> _ReActState:  # type: ignore[override]
        return _ReActState(task=x)


class _TakeAnswer(Agent[_ReActState, Answer]):
    input = _ReActState
    output = Answer

    async def forward(self, x: _ReActState) -> Answer:  # type: ignore[override]
        if _TRACER.get() is not None:
            return Answer.model_construct()
        return x.answer or Answer.model_construct()


class _ReasonStage(Agent[_ReActState, _ReActState]):
    input = _ReActState
    output = _ReActState

    def __init__(self, child: Agent[Any, Any]) -> None:
        super().__init__(config=None, input=_ReActState, output=_ReActState)
        self.child = child

    async def forward(self, x: _ReActState) -> _ReActState:  # type: ignore[override]
        tracing = _TRACER.get() is not None
        task = Task.model_construct() if tracing else (x.task or Task.model_construct())
        thought = (await self.child(task)).response
        if tracing:
            return _ReActState(task=task, thought=thought)
        return _ReActState(
            task=task,
            thought=thought,
            action=x.action,
            observation=x.observation,
            answer=x.answer,
        )


class _ActionStage(Agent[_ReActState, _ReActState]):
    input = _ReActState
    output = _ReActState

    def __init__(self, child: Agent[Any, Any]) -> None:
        super().__init__(config=None, input=_ReActState, output=_ReActState)
        self.child = child

    async def forward(self, x: _ReActState) -> _ReActState:  # type: ignore[override]
        tracing = _TRACER.get() is not None
        thought = (
            Thought.model_construct()
            if tracing
            else (x.thought or Thought.model_construct())
        )
        action = (await self.child(thought)).response
        if tracing:
            return _ReActState(thought=thought, action=action)
        return _ReActState(
            task=x.task,
            thought=thought,
            action=action,
            observation=x.observation,
            answer=x.answer,
        )


class _ObserveStage(Agent[_ReActState, _ReActState]):
    input = _ReActState
    output = _ReActState

    def __init__(self, child: Agent[Any, Any]) -> None:
        super().__init__(config=None, input=_ReActState, output=_ReActState)
        self.child = child

    async def forward(self, x: _ReActState) -> _ReActState:  # type: ignore[override]
        tracing = _TRACER.get() is not None
        action = (
            Action.model_construct()
            if tracing
            else (x.action or Action.model_construct())
        )
        observation = (await self.child(action)).response
        if tracing:
            return _ReActState(action=action, observation=observation)
        return _ReActState(
            task=x.task,
            thought=x.thought,
            action=action,
            observation=observation,
            answer=x.answer,
        )


class _EvaluateStage(Agent[_ReActState, _ReActState]):
    input = _ReActState
    output = _ReActState

    def __init__(self, child: Agent[Any, Any]) -> None:
        super().__init__(config=None, input=_ReActState, output=_ReActState)
        self.child = child

    async def forward(self, x: _ReActState) -> _ReActState:  # type: ignore[override]
        tracing = _TRACER.get() is not None
        observation = (
            Observation.model_construct()
            if tracing
            else (x.observation or Observation.model_construct())
        )
        answer = (await self.child(observation)).response
        if tracing:
            return _ReActState(observation=observation, answer=answer)
        return _ReActState(
            task=x.task,
            thought=x.thought,
            action=x.action,
            observation=observation,
            answer=answer,
        )


class ReAct(Agent[Task, Answer]):
    """One-pass ReAct: Reason → Act → Observe → Evaluate.

    Constructs four sub-agents (one each of Reasoner, Actor, Extractor,
    Evaluator) wired with typed ``Task -> Thought -> Action ->
    Observation -> Answer`` edges. Each sub-agent carries its own
    component-level ``role``/``task`` defaults; override any of them
    post-construction (``react.actor.task = ...``) or by subclassing.

    The single structural child is ``pipeline``. The ``reasoner`` /
    ``actor`` / ``extractor`` / ``evaluator`` (and the ``_*_stage`` /
    ``_loop``) attributes are property views into that pipeline — both
    reads and assignments stay in sync with the structural tree.
    """

    input = Task
    output = Answer

    def __init__(
        self,
        *,
        config: Configuration,
        context: str | None = None,
        n_loops: int = 1,
    ) -> None:
        if n_loops < 1:
            raise ValueError("ReAct requires n_loops >= 1")
        super().__init__(config=None, input=Task, output=Answer, context=context)
        self.n_loops = n_loops

        self.pipeline = Sequential(
            _InitState(),
            Loop(
                _ReasonStage(
                    Reasoner(config=config, input=Task, output=Thought, context=context)
                ),
                _ActionStage(
                    Actor(config=config, input=Thought, output=Action, context=context)
                ),
                _ObserveStage(
                    Extractor(
                        config=config, input=Action, output=Observation, context=context
                    )
                ),
                _EvaluateStage(
                    Evaluator(
                        config=config, input=Observation, output=Answer, context=context
                    )
                ),
                input=_ReActState,
                output=_ReActState,
                n_loops=n_loops,
            ),
            _TakeAnswer(),
            input=Task,
            output=Answer,
        )

    @property
    def _loop(self) -> Loop[_ReActState]:
        return self.pipeline._stages[1]  # type: ignore[return-value]

    @property
    def _reason_stage(self) -> _ReasonStage:
        return self._loop._stages[0]  # type: ignore[return-value]

    @property
    def _action_stage(self) -> _ActionStage:
        return self._loop._stages[1]  # type: ignore[return-value]

    @property
    def _observe_stage(self) -> _ObserveStage:
        return self._loop._stages[2]  # type: ignore[return-value]

    @property
    def _evaluate_stage(self) -> _EvaluateStage:
        return self._loop._stages[3]  # type: ignore[return-value]

    @property
    def reasoner(self) -> Agent[Task, Thought]:
        return self._reason_stage.child  # type: ignore[return-value]

    @reasoner.setter
    def reasoner(self, value: Agent[Any, Any]) -> None:
        self._reason_stage.child = value

    @property
    def actor(self) -> Agent[Thought, Action]:
        return self._action_stage.child  # type: ignore[return-value]

    @actor.setter
    def actor(self, value: Agent[Any, Any]) -> None:
        self._action_stage.child = value

    @property
    def extractor(self) -> Agent[Action, Observation]:
        return self._observe_stage.child  # type: ignore[return-value]

    @extractor.setter
    def extractor(self, value: Agent[Any, Any]) -> None:
        self._observe_stage.child = value

    @property
    def evaluator(self) -> Agent[Observation, Answer]:
        return self._evaluate_stage.child  # type: ignore[return-value]

    @evaluator.setter
    def evaluator(self, value: Agent[Any, Any]) -> None:
        self._evaluate_stage.child = value

    async def forward(self, x: Task) -> Answer:  # type: ignore[override]
        return (await self.pipeline(x)).response
