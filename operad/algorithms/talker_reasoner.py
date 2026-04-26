"""TalkerReasoner: scenario-tree-driven conversational guidance.

Two-agent loop. The **Reasoner** owns navigation: at every turn it reads the
current `ScenarioNode`, the user's message, and the conversation history,
and emits a typed `NavigationDecision` (move advance/branch/stay/finish).
The **Talker** owns the user-facing surface: given the decision and the
target node, it produces the next assistant message.

The algorithm is deliberately **not** an `Agent` — its natural API is
``await tr.step(message) -> str``, ``await tr.run(messages) -> Transcript``,
not ``__call__(x: In) -> Out``. Following the project convention,
components are class-level defaults so callers typically supply only the
algorithm's own knobs (`tree`, `start_node_id`, `max_turns`); subclass to
swap in differently-configured components.

Use cases
---------
- guided intake forms (career counselling, clinical triage, customer onboarding)
- branching tutorial walkthroughs
- structured interviews where the next question depends on the prior answer
"""

from __future__ import annotations

import time
from inspect import cleandoc
from typing import ClassVar, Literal, Any

from pydantic import BaseModel, ConfigDict, Field

from ..core.agent import Agent
from ..core.example import Example
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


# ---------------------------------------------------------------------------
# Scenario tree — the structure the algorithm walks.
# ---------------------------------------------------------------------------


class ScenarioNode(BaseModel):
    """One node in the scenario tree.

    A node represents one step of the guided process: a question to ask,
    a piece of information to convey, or a decision point. ``children``
    are dispatched to via the reasoner's `branch_to` field, keyed by the
    child's `id`. ``terminal=True`` ends the conversation when reached.
    """

    id: str = Field(description="Stable, globally-unique node id.")
    title: str = Field(description="Short label for traces / dashboards.")
    prompt: str = Field(
        description=(
            "What the assistant should accomplish at this node — phrased "
            "as guidance to the Talker, not as a literal user-facing line."
        ),
    )
    instructions: str = Field(
        default="",
        description="Per-node guidance read by the navigation Reasoner.",
    )
    children: list["ScenarioNode"] = Field(
        default_factory=list,
        description="Child nodes; the reasoner picks one by id when branching.",
    )
    terminal: bool = Field(
        default=False,
        description="True iff reaching this node ends the conversation.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


ScenarioNode.model_rebuild()


class ScenarioTree(BaseModel):
    """The full guided process — a labelled scenario forest."""

    name: str = Field(description="Human-readable process name.")
    purpose: str = Field(description="One-sentence purpose statement.")
    root: ScenarioNode = Field(description="Entry point of the process.")

    def find(self, node_id: str) -> ScenarioNode | None:
        """Depth-first lookup by id. Returns ``None`` if not found."""

        def walk(n: ScenarioNode) -> ScenarioNode | None:
            if n.id == node_id:
                return n
            for c in n.children:
                hit = walk(c)
                if hit is not None:
                    return hit
            return None

        return walk(self.root)


# ---------------------------------------------------------------------------
# Typed I/O for the two internal agents.
# ---------------------------------------------------------------------------


NavigationKind = Literal["stay", "advance", "branch", "finish"]


class NavigationInput(BaseModel):
    """Inputs the Reasoner receives at every turn."""

    process_name: str = Field(description="Name of the guided process.")
    process_purpose: str = Field(description="Why this process exists.")
    history: str = Field(
        default="",
        description="Flat string of prior user/assistant turns.",
    )
    current_node_id: str = Field(description="Id of the current scenario node.")
    current_node_title: str = Field(description="Title of the current node.")
    current_node_prompt: str = Field(
        description="What the assistant aims to accomplish here.",
    )
    current_node_instructions: str = Field(
        default="",
        description="Author-supplied navigation rules for this node.",
    )
    available_children: str = Field(
        default="",
        description=(
            "JSON-shaped list of `{id, title}` for children the reasoner "
            "may branch to. Empty when the node is a leaf."
        ),
    )
    user_message: str = Field(description="The user's latest message.")


class NavigationDecision(BaseModel):
    """The Reasoner's typed decision."""

    kind: NavigationKind = Field(
        default="stay",
        description=(
            "stay = remain on this node (clarify); "
            "advance = move to the single next node (when the current node "
            "has exactly one child); "
            "branch = pick one of `available_children` by id; "
            "finish = end the conversation."
        ),
    )
    branch_to: str = Field(
        default="",
        description="Child node id when kind=='branch'; empty otherwise.",
    )
    rationale: str = Field(
        default="",
        description="Short explanation of why this decision was made.",
    )
    next_message_brief: str = Field(
        default="",
        description=(
            "Compact instruction to the Talker on what the next assistant "
            "message should accomplish (one or two sentences)."
        ),
    )


class TalkerInput(BaseModel):
    """Inputs the Talker receives after a decision is made."""

    process_name: str = Field(description="Name of the guided process.")
    history: str = Field(default="", description="Flat conversation history.")
    target_node_id: str = Field(description="Node we will be on after this turn.")
    target_node_title: str = Field(description="Title of the target node.")
    target_node_prompt: str = Field(description="Goal at the target node.")
    decision_kind: NavigationKind = Field(description="What the reasoner decided.")
    next_message_brief: str = Field(
        description="The reasoner's brief on what to write.",
    )
    user_message: str = Field(description="The user's latest message.")
    is_terminal: bool = Field(
        default=False,
        description="True iff this turn closes the conversation.",
    )


class AssistantMessage(BaseModel):
    """The Talker's user-facing reply."""

    text: str = Field(description="The assistant's next message.")


# ---------------------------------------------------------------------------
# Navigator / Talker prompts and private agent classes.
# ---------------------------------------------------------------------------


class _Navigator(Agent[NavigationInput, NavigationDecision]):
    input = NavigationInput
    output = NavigationDecision
    role = cleandoc("""
        You are the navigator of a guided conversational process. You see
        the current scenario node, the available children (if any), the
        conversation history, and the user's latest message. You decide
        whether to stay on this node, advance, branch to a specific child,
        or finish the conversation.
    """)
    task = cleandoc("""
        Read every input and produce a typed NavigationDecision:

        - kind = "stay" when the user needs more clarification at this step.
        - kind = "advance" when the current node has exactly one child and the
          user has supplied what was needed to move on.
        - kind = "branch" when there are multiple children and the user's
          message clearly maps to one of them — set branch_to to its id.
        - kind = "finish" when the process is complete or the user opted out.
    """)
    rules = (
        "Use the current_node_instructions to break ties; they are author-supplied.",
        "If branching, branch_to MUST appear in available_children; otherwise stay.",
        "Never invent a node id; never guess across rounds.",
        "Be conservative: prefer stay/clarify when the user's message is ambiguous.",
        "Write rationale in one sentence — it is read by maintainers, not the user.",
    )
    examples = (
        Example(
            input=NavigationInput(
                process_name="Career intake",
                process_purpose="Identify the right service tier for the candidate.",
                history="",
                current_node_id="start",
                current_node_title="Welcome",
                current_node_prompt=(
                    "Greet the candidate and ask whether they are looking "
                    "for a job or career advice."
                ),
                current_node_instructions="",
                available_children=(
                    '[{"id": "job_search", "title": "Job search"}, '
                    '{"id": "career_advice", "title": "Career advice"}]'
                ),
                user_message="I'm looking for a new job.",
            ),
            output=NavigationDecision(
                kind="branch",
                branch_to="job_search",
                rationale="User explicitly stated they are looking for a new job.",
                next_message_brief=(
                    "Acknowledge the job-search goal and ask about the "
                    "candidate's target role and preferred location."
                ),
            ),
        ),
    )


class _Voice(Agent[TalkerInput, AssistantMessage]):
    input = TalkerInput
    output = AssistantMessage
    role = cleandoc("""
        You are the user-facing voice of a guided conversational process.
        Another component has already decided which scenario node we are
        on next; your job is to produce the actual message the user will
        read. Stay warm, concise, and on-process.
    """)
    task = cleandoc("""
        Write the next assistant message. Combine three signals:

        - the target node's prompt — what the assistant should accomplish;
        - the reasoner's next_message_brief — exactly what to convey now;
        - the conversation history — to maintain continuity and avoid repetition.

        On terminal turns, acknowledge completion and offer one concrete
        next step outside the process (e.g. an artefact, a recap, a hand-off).
    """)
    rules = (
        "Two to five sentences is the default; expand only when explicitly asked.",
        "Never restate the user's words verbatim; reflect understanding instead.",
        "Do NOT mention scenario node ids, branches, or routing decisions.",
        "Keep the same language the user used.",
        "End every non-terminal turn with one concrete prompt or question.",
    )
    examples = (
        Example(
            input=TalkerInput(
                process_name="Career intake",
                history="user: I'm looking for a new job.",
                target_node_id="job_search",
                target_node_title="Job search",
                target_node_prompt=(
                    "Collect the candidate's target role and preferred location."
                ),
                decision_kind="branch",
                next_message_brief=(
                    "Acknowledge the job-search goal and ask about the "
                    "candidate's target role and preferred location."
                ),
                user_message="I'm looking for a new job.",
                is_terminal=False,
            ),
            output=AssistantMessage(
                text=(
                    "Great, let's get your job search started! What role are "
                    "you targeting, and do you have a preferred location or are "
                    "you open to remote opportunities?"
                ),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Transcript types — the algorithm's run-level outputs.
# ---------------------------------------------------------------------------


class Turn(BaseModel):
    """One full turn: user input, decision, assistant output, resulting node."""

    turn_index: int = Field(description="Zero-based turn index.")
    user_message: str = Field(description="The user's message this turn.")
    from_node_id: str = Field(description="Node before the decision was applied.")
    decision: NavigationDecision = Field(description="The reasoner's typed decision.")
    to_node_id: str = Field(description="Node after the decision was applied.")
    assistant_message: str = Field(description="The user-facing reply.")
    is_terminal: bool = Field(
        default=False,
        description="True iff this turn ended the conversation.",
    )


class Transcript(BaseModel):
    """The full conversation produced by `TalkerReasoner.run`."""

    process_name: str = Field(description="Name of the guided process.")
    turns: list[Turn] = Field(default_factory=list, description="All turns in order.")
    final_node_id: str = Field(description="Where the conversation ended.")
    finished: bool = Field(
        default=False,
        description="True iff a terminal node was reached.",
    )


# ---------------------------------------------------------------------------
# The algorithm.
# ---------------------------------------------------------------------------


class TalkerReasoner:
    """Walk a `ScenarioTree` with a navigator and a voice agent.

    Single-pass per turn: the navigator emits a typed decision, the
    algorithm applies it, the voice agent produces the user-facing reply.
    Transcript is accumulated across turns. Components are class-level
    defaults so callers usually only need to supply ``tree`` and
    algorithm knobs (`max_turns`); swap components via a subclass.

    Example::

        tr = TalkerReasoner(tree=intake_tree, max_turns=10)
        await tr.abuild()                   # symbolic trace + type-check
        reply = await tr.step("Hi!")        # one turn at a time
        ...
        transcript = await tr.run([...])    # or run a whole script
    """

    reasoner: ClassVar[Agent] = _Navigator()
    talker: ClassVar[Agent] = _Voice()

    def __init__(
        self,
        tree: ScenarioTree,
        *,
        start_node_id: str | None = None,
        max_turns: int = 12,
        context: str = "",
        config: Any | None = None,
    ) -> None:
        if max_turns < 1:
            raise ValueError(f"max_turns must be >= 1, got {max_turns}")
        if start_node_id is not None and tree.find(start_node_id) is None:
            raise ValueError(
                f"start_node_id={start_node_id!r} not in tree {tree.name!r}"
            )

        cls = type(self)
        # Distinct clones so concurrent invocation in tests doesn't share
        # strands history. `config` (when provided) wins over the class-
        # level default so callers can use the algorithm's stock prompts
        # against any backend without subclassing.
        self.reasoner = cls.reasoner.clone(context=context)
        self.talker = cls.talker.clone(context=context)
        if config is not None:
            self.reasoner.config = config
            self.talker.config = config

        self.tree = tree
        self.context = context
        self.max_turns = max_turns
        self._current_id = start_node_id or tree.root.id
        self._history: list[Turn] = []
        self._finished = False

    @property
    def current_node(self) -> ScenarioNode:
        node = self.tree.find(self._current_id)
        if node is None:  # pragma: no cover — only constructible via valid ids
            raise RuntimeError(f"current node {self._current_id!r} not in tree")
        return node

    @property
    def finished(self) -> bool:
        return self._finished

    async def abuild(self) -> "TalkerReasoner":
        """Type-check both child agents up front; mirrors `Agent.abuild`."""
        await self.reasoner.abuild()
        await self.talker.abuild()
        return self

    def reset(self, *, start_node_id: str | None = None) -> None:
        """Clear transcript and rewind to the given node (or root)."""
        target = start_node_id or self.tree.root.id
        if self.tree.find(target) is None:
            raise ValueError(f"start_node_id={target!r} not in tree {self.tree.name!r}")
        self._current_id = target
        self._history.clear()
        self._finished = False

    async def step(self, user_message: str) -> Turn:
        """One Reasoner→Talker round; updates internal state, returns the Turn."""
        if self._finished:
            raise RuntimeError("conversation has finished; call reset() first")
        if len(self._history) >= self.max_turns:
            raise RuntimeError(
                f"max_turns={self.max_turns} reached; call reset() to start over"
            )
        return await self._one_turn(user_message)

    async def run(self, user_messages: list[str]) -> Transcript:
        """Replay a scripted conversation; halts on `finish` or end of script."""
        path = type(self).__name__
        started = time.time()
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=path,
                payload={
                    "process": self.tree.name,
                    "start_node_id": self._current_id,
                    "max_turns": self.max_turns,
                    "scripted_messages": len(user_messages),
                },
                started_at=started,
            )
            try:
                for message in user_messages:
                    if self._finished:
                        break
                    if len(self._history) >= self.max_turns:
                        break
                    await self._one_turn(message)
                transcript = Transcript(
                    process_name=self.tree.name,
                    turns=list(self._history),
                    final_node_id=self._current_id,
                    finished=self._finished,
                )
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={
                        "turns": len(transcript.turns),
                        "finished": transcript.finished,
                        "final_node_id": transcript.final_node_id,
                    },
                    started_at=started,
                    finished_at=time.time(),
                )
                return transcript
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise

    # --- internals ---------------------------------------------------------

    async def _one_turn(self, user_message: str) -> Turn:
        path = type(self).__name__
        node = self.current_node
        history_str = self._render_history()
        children_repr = self._render_children(node)

        await emit_algorithm_event(
            "iteration",
            algorithm_path=path,
            payload={
                "iter_index": len(self._history),
                "phase": "navigate",
                "current_node_id": node.id,
            },
        )

        nav = await self.reasoner(
            NavigationInput(
                process_name=self.tree.name,
                process_purpose=self.tree.purpose,
                history=history_str,
                current_node_id=node.id,
                current_node_title=node.title,
                current_node_prompt=node.prompt,
                current_node_instructions=node.instructions,
                available_children=children_repr,
                user_message=user_message,
            )
        )
        decision: NavigationDecision = nav.response
        target_id, became_terminal = self._apply(decision, node)
        target = self.tree.find(target_id) or node

        await emit_algorithm_event(
            "iteration",
            algorithm_path=path,
            payload={
                "iter_index": len(self._history),
                "phase": "speak",
                "decision_kind": decision.kind,
                "from_node_id": node.id,
                "to_node_id": target_id,
            },
        )

        msg = await self.talker(
            TalkerInput(
                process_name=self.tree.name,
                history=history_str,
                target_node_id=target.id,
                target_node_title=target.title,
                target_node_prompt=target.prompt,
                decision_kind=decision.kind,
                next_message_brief=decision.next_message_brief,
                user_message=user_message,
                is_terminal=became_terminal,
            )
        )

        turn = Turn(
            turn_index=len(self._history),
            user_message=user_message,
            from_node_id=node.id,
            decision=decision,
            to_node_id=target_id,
            assistant_message=msg.response.text,
            is_terminal=became_terminal,
        )
        self._history.append(turn)
        self._current_id = target_id
        if became_terminal:
            self._finished = True
        return turn

    def _apply(
        self, decision: NavigationDecision, node: ScenarioNode
    ) -> tuple[str, bool]:
        """Resolve the decision against the tree; return (next_id, terminal)."""
        if decision.kind == "finish":
            return node.id, True
        if decision.kind == "stay":
            return node.id, node.terminal
        if decision.kind == "advance":
            if len(node.children) == 1:
                child = node.children[0]
                return child.id, child.terminal
            # Ambiguous: advance with multi/zero children falls back to stay.
            return node.id, node.terminal
        if decision.kind == "branch":
            for c in node.children:
                if c.id == decision.branch_to:
                    return c.id, c.terminal
            # Hallucinated id: stay.
            return node.id, node.terminal
        return node.id, node.terminal  # exhaustive over Literal

    def _render_history(self) -> str:
        if not self._history:
            return ""
        lines: list[str] = []
        for t in self._history:
            lines.append(f"user: {t.user_message}")
            lines.append(f"assistant: {t.assistant_message}")
        return "\n".join(lines)

    def _render_children(self, node: ScenarioNode) -> str:
        if not node.children:
            return ""
        return ", ".join(f"{{id={c.id!r}, title={c.title!r}}}" for c in node.children)


__all__ = [
    "AssistantMessage",
    "NavigationDecision",
    "NavigationInput",
    "NavigationKind",
    "ScenarioNode",
    "ScenarioTree",
    "TalkerInput",
    "TalkerReasoner",
    "Transcript",
    "Turn",
]
