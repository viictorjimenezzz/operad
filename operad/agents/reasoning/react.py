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

from ...core.agent import Agent
from ...core.config import Configuration
from .components import Actor, Evaluator, Extractor, Reasoner
from .schemas import Action, Answer, Observation, Task, Thought


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

    def __init__(self, *, config: Configuration, context: str | None = None) -> None:
        super().__init__(config=None, input=Task, output=Answer, context=context)

        self.reasoner: Reasoner[Task, Thought] = Reasoner(
            config=config, input=Task, output=Thought, context=context
        )
        self.actor: Actor[Thought, Action] = Actor(
            config=config, input=Thought, output=Action, context=context
        )
        self.extractor: Extractor[Action, Observation] = Extractor(
            config=config, input=Action, output=Observation, context=context
        )
        self.evaluator: Evaluator[Observation, Answer] = Evaluator(
            config=config, input=Observation, output=Answer, context=context
        )

    async def forward(self, x: Task) -> Answer:  # type: ignore[override]
        thought = (await self.reasoner(x)).response
        action = (await self.actor(thought)).response
        observation = (await self.extractor(action)).response
        return (await self.evaluator(observation)).response
