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

from pydantic import BaseModel, Field

from ...core.agent import Agent
from ...core.config import Configuration
from .components import Actor, Evaluator, Extractor, Reasoner


# --- typed edges -------------------------------------------------------------


class Task(BaseModel):
    """What the ReAct agent should accomplish."""

    goal: str = Field(description="The objective to solve.")
    context: str = Field(default="", description="Optional background information.")


class Thought(BaseModel):
    """The Reasoner's deliberation about the task."""

    reasoning: str = Field(description="Step-by-step thought about the task.")
    next_action: str = Field(
        description="Short description of the concrete next action to take."
    )


class Action(BaseModel):
    """The Actor's chosen next step, ready to be executed or simulated."""

    name: str = Field(description="The action's short name (e.g. 'search', 'compute').")
    details: str = Field(description="What this action does, with arguments.")


class Observation(BaseModel):
    """The outcome of the action, synthesized into textual form."""

    result: str = Field(description="What the action produced.")
    success: bool = Field(
        default=True, description="Whether the action appears to have succeeded."
    )


class Answer(BaseModel):
    """The Evaluator's final answer to the original task."""

    reasoning: str = Field(description="How the observation leads to the answer.")
    answer: str = Field(description="Final, concise answer to the task.")


# --- composition -------------------------------------------------------------


class ReAct(Agent[Task, Answer]):
    """One-pass ReAct: Reason → Act → Observe → Evaluate.

    Constructs four sub-agents (one each of Reasoner, Actor, Extractor,
    Evaluator) wired with typed ``Task -> Thought -> Action ->
    Observation -> Answer`` edges. Each sub-agent carries its own
    component-level ``role``/``task`` defaults; override any of them
    post-construction (``react.actor.task = ...``) or by subclassing.
    """

    input = Task
    output = Answer

    def __init__(self, *, config: Configuration) -> None:
        super().__init__(config=None, input=Task, output=Answer)

        self.reasoner: Reasoner[Task, Thought] = Reasoner(
            config=config, input=Task, output=Thought
        )
        self.actor: Actor[Thought, Action] = Actor(
            config=config, input=Thought, output=Action
        )
        self.extractor: Extractor[Action, Observation] = Extractor(
            config=config, input=Action, output=Observation
        )
        self.evaluator: Evaluator[Observation, Answer] = Evaluator(
            config=config, input=Observation, output=Answer
        )

    async def forward(self, x: Task) -> Answer:  # type: ignore[override]
        thought = (await self.reasoner(x)).response
        action = (await self.actor(thought)).response
        observation = (await self.extractor(action)).response
        return (await self.evaluator(observation)).response
