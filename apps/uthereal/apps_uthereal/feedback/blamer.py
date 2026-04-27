from __future__ import annotations

"""Blame-localization agent for human feedback.

Owner: 2-3-blamer.
"""

import json
from inspect import cleandoc
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from operad import Agent, Configuration, Example

from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.tiers import tier_to_config
from apps_uthereal.workflow.trace import WorkflowTrace


KNOWN_LEAF_PATHS: tuple[str, ...] = (
    "context_safeguard",
    "safeguard_talker",
    "reasoner",
    "conv_talker",
    "rule_classifier",
    "retrieval_orchestrator",
    "evidence_planner",
    "fact_filter",
    "rag_talker",
)
SPECIAL_TARGETS: tuple[str, ...] = ("control_flow", "data", "no_fault")
TRACE_FIELD_CHAR_LIMIT = 600
LEAF_PREVIEW_CHAR_LIMIT = 600

TargetPath = Literal[
    "context_safeguard",
    "safeguard_talker",
    "reasoner",
    "conv_talker",
    "rule_classifier",
    "retrieval_orchestrator",
    "evidence_planner",
    "fact_filter",
    "rag_talker",
    "control_flow",
    "data",
    "no_fault",
]


class LeafSummary(BaseModel):
    """Compact description of a leaf for the Blamer's prompt."""

    step_name: str
    role: str
    task: str
    fired_in_trace: bool
    input_preview: str = ""
    output_preview: str = ""

    model_config = ConfigDict(frozen=True)


class BlamerInput(BaseModel):
    """The full context the Blamer needs to make a decision."""

    final_answer: str
    user_critique: str
    desired_behavior: str = ""
    trace_summary: str
    leaves: list[LeafSummary]

    model_config = ConfigDict(frozen=True)


class BlamerOutput(BaseModel):
    """One blame target and the critique to pass to the optimizer."""

    target_path: TargetPath
    rationale: str
    leaf_targeted_critique: str
    severity: float = Field(ge=0.0, le=1.0, default=1.0)

    model_config = ConfigDict(frozen=True)


def _example_leaves(fired_outputs: dict[str, str]) -> list[LeafSummary]:
    return [
        LeafSummary(
            step_name=step_name,
            role=f"{step_name} role",
            task=f"{step_name} task",
            fired_in_trace=step_name in fired_outputs,
            input_preview="{\"message\":\"fixture\"}" if step_name in fired_outputs else "",
            output_preview=fired_outputs.get(step_name, ""),
        )
        for step_name in KNOWN_LEAF_PATHS
    ]


class Blamer(Agent[BlamerInput, BlamerOutput]):
    """Reasons over a WorkflowTrace and human critique to localize blame.

    Heuristic: prefer the earliest leaf whose output already contains the
    defect. Distinguish wrong route from wrong final wording, and use special
    targets when no single leaf rewrite is the right fix.
    """

    input = BlamerInput
    output = BlamerOutput
    role = cleandoc(
        """
        You are a debugging agent for a multi-leaf prompt pipeline. You inspect
        a typed workflow trace, the final answer, and a human critique, then
        choose the single component most responsible for the defect.
        """
    )
    task = cleandoc(
        """
        Return exactly one blame target. The target must be one known leaf path
        or one special target: control_flow when workflow orchestration is the
        problem, data when the dataset or retrieved evidence is wrong, and
        no_fault when the critique does not identify an actionable defect.

        Also rewrite the human critique so it is targeted at the selected leaf's
        prompt. This targeted critique will be used as a textual gradient for a
        one-leaf prompt rewrite.
        """
    )
    rules = (
        "Prefer the earliest fired leaf whose output already contains the defect.",
        "If the route is wrong, blame reasoner; if the route is right but the "
        "answer wording or style is wrong, blame the talker that wrote the answer.",
        "If the safeguard wrongly blocked or passed the request, blame context_safeguard.",
        "If the safeguard category was correct but the refusal text was poor, "
        "blame safeguard_talker.",
        "If retrieval plans and filtered evidence look plausible but the final "
        "answer has broken citations or unsupported wording, blame rag_talker.",
        "If the selected rules are wrong, blame rule_classifier; if the retrieval "
        "query/spec is wrong, blame retrieval_orchestrator.",
        "If relevant retrieved facts were dropped or bad facts were kept before "
        "answer composition, blame fact_filter.",
        "Use control_flow only for orchestration, latency, cancellation, or "
        "branching defects that no leaf prompt rewrite can fix.",
        "Use data only when the dataset entry, source documents, or retrieved "
        "records are wrong rather than the leaf behavior.",
        "Use no_fault when the critique is preference-only, already satisfied, or "
        "too vague to act on.",
        "Set severity near 1.0 for complete failures, around 0.5 for style or "
        "partial failures, and lower for small nudges.",
    )
    examples = (
        Example[BlamerInput, BlamerOutput](
            input=BlamerInput(
                final_answer="I searched the workspace and found no relevant policy.",
                user_critique=(
                    "This was just a greeting. It should not have searched documents."
                ),
                desired_behavior="Answer directly with a short greeting.",
                trace_summary=(
                    "reasoner output route=RAG_NEEDED for a greeting; rag_talker "
                    "wrote a search-based answer."
                ),
                leaves=_example_leaves(
                    {
                        "reasoner": "{\"intent\":\"RAG_NEEDED\"}",
                        "rag_talker": "{\"answer\":\"I searched the workspace...\"}",
                    }
                ),
            ),
            output=BlamerOutput(
                target_path="reasoner",
                rationale="The first defect is the route: the reasoner sent a greeting to RAG.",
                leaf_targeted_critique=(
                    "Route simple greetings and acknowledgments to DIRECT_ANSWER "
                    "instead of RAG_NEEDED."
                ),
                severity=0.9,
            ),
        ),
        Example[BlamerInput, BlamerOutput](
            input=BlamerInput(
                final_answer="I can't help with that topic.",
                user_critique=(
                    "The question was about implant placement, which is in scope. "
                    "The refusal is wrong."
                ),
                desired_behavior="Treat implant protocol questions as in scope.",
                trace_summary=(
                    "context_safeguard output continue_field=no "
                    "category=separate_domain; safeguard_talker refused."
                ),
                leaves=_example_leaves(
                    {
                        "context_safeguard": (
                            "{\"continue_field\":\"no\","
                            "\"category\":\"separate_domain\"}"
                        ),
                        "safeguard_talker": "{\"answer\":\"I can't help with that topic.\"}",
                    }
                ),
            ),
            output=BlamerOutput(
                target_path="context_safeguard",
                rationale="The refusal text followed an incorrect safeguard decision.",
                leaf_targeted_critique=(
                    "Classify implant placement protocol questions as in-scope "
                    "unless they ask for unsafe or unrelated content."
                ),
                severity=1.0,
            ),
        ),
        Example[BlamerInput, BlamerOutput](
            input=BlamerInput(
                final_answer="Great question! Let me unpack this in detail...",
                user_critique=(
                    "The route was right, but the direct answer is too chatty and "
                    "starts with flattery."
                ),
                desired_behavior="Use a concise, professional direct-answer tone.",
                trace_summary=(
                    "reasoner output route=DIRECT_ANSWER; conv_talker output "
                    "contains flattery and excess preamble."
                ),
                leaves=_example_leaves(
                    {
                        "reasoner": "{\"intent\":\"DIRECT_ANSWER\"}",
                        "conv_talker": "{\"answer\":\"Great question! Let me unpack...\"}",
                    }
                ),
            ),
            output=BlamerOutput(
                target_path="conv_talker",
                rationale=(
                    "The route was correct; the final direct-answer talker "
                    "introduced the style defect."
                ),
                leaf_targeted_critique=(
                    "Avoid flattery, preambles, and overlong setup in direct "
                    "answers; answer in the user's register."
                ),
                severity=0.6,
            ),
        ),
        Example[BlamerInput, BlamerOutput](
            input=BlamerInput(
                final_answer="Use the documented sterilization cycle. [ref:missing]",
                user_critique="The citation marker does not resolve in the reference panel.",
                desired_behavior="Use only citations that resolve to emitted references.",
                trace_summary=(
                    "evidence_planner produced relevant evidence; rag_talker "
                    "output cited ref:missing."
                ),
                leaves=_example_leaves(
                    {
                        "evidence_planner": "{\"claims\":[\"sterilization cycle\"]}",
                        "rag_talker": (
                            "{\"answer\":\"Use the documented sterilization "
                            "cycle. [ref:missing]\"}"
                        ),
                    }
                ),
            ),
            output=BlamerOutput(
                target_path="rag_talker",
                rationale=(
                    "The evidence exists, but the final answer introduced an "
                    "unresolved citation."
                ),
                leaf_targeted_critique=(
                    "Only emit citation markers backed by the provided references, "
                    "and omit unsupported markers."
                ),
                severity=0.8,
            ),
        ),
        Example[BlamerInput, BlamerOutput](
            input=BlamerInput(
                final_answer="The answer is correct but arrived after a slow retrieval step.",
                user_critique="The retrieval was too slow.",
                desired_behavior="Make retrieval faster.",
                trace_summary=(
                    "retrieval_orchestrator and downstream leaves produced correct "
                    "outputs; latency is the complaint."
                ),
                leaves=_example_leaves(
                    {
                        "retrieval_orchestrator": "{\"specs\":[{\"intent\":\"lookup\"}]}",
                        "rag_talker": "{\"answer\":\"The answer is correct...\"}",
                    }
                ),
            ),
            output=BlamerOutput(
                target_path="control_flow",
                rationale=(
                    "The complaint is about runtime behavior, not a prompt-local "
                    "output defect."
                ),
                leaf_targeted_critique="No leaf prompt should be rewritten for retrieval latency.",
                severity=0.2,
            ),
        ),
        Example[BlamerInput, BlamerOutput](
            input=BlamerInput(
                final_answer="Hi. I can help with questions covered by this workspace.",
                user_critique="I prefer a different font in the chat UI.",
                desired_behavior="Use a larger font.",
                trace_summary=(
                    "context_safeguard passed; reasoner routed DIRECT_ANSWER; "
                    "conv_talker gave an appropriate greeting."
                ),
                leaves=_example_leaves(
                    {
                        "context_safeguard": "{\"continue_field\":\"yes\"}",
                        "reasoner": "{\"intent\":\"DIRECT_ANSWER\"}",
                        "conv_talker": "{\"answer\":\"Hi. I can help...\"}",
                    }
                ),
            ),
            output=BlamerOutput(
                target_path="no_fault",
                rationale=(
                    "The critique is about UI presentation and does not identify a "
                    "workflow answer defect."
                ),
                leaf_targeted_critique="No prompt rewrite is indicated by this critique.",
                severity=0.0,
            ),
        ),
    )

    def __init__(self, *, config: Configuration | None = None) -> None:
        super().__init__(
            config=config or default_blamer_config(),
            input=BlamerInput,
            output=BlamerOutput,
        )


def default_blamer_config() -> Configuration:
    """Return the default high-reasoning configuration for the Blamer.

    The Blamer uses ``tier_to_config("thinking_high")`` by default because
    blame localization is a meta-reasoning task. Override via
    ``Blamer(config=...)`` in tests.
    """

    return tier_to_config("thinking_high")


def render_blamer_input(
    *,
    trace: WorkflowTrace,
    feedback: HumanFeedback,
    leaf_directory: dict[str, Agent[Any, Any]],
) -> BlamerInput:
    """Build the BlamerInput from a sealed trace and feedback.

    ``leaf_directory`` maps step name to loaded leaf. It fills each
    ``LeafSummary`` role and task, including for leaves that did not fire.
    """

    frames_by_step = {frame.step_name: frame for frame in trace.frames}
    leaves: list[LeafSummary] = []
    for step_name in KNOWN_LEAF_PATHS:
        frame = frames_by_step.get(step_name)
        leaf = leaf_directory.get(step_name)
        if frame is not None:
            role = frame.leaf_role or _agent_attr(leaf, "role")
            task = frame.leaf_task or _agent_attr(leaf, "task")
        else:
            role = _agent_attr(leaf, "role")
            task = _agent_attr(leaf, "task")
        leaves.append(
            LeafSummary(
                step_name=step_name,
                role=role,
                task=task,
                fired_in_trace=frame is not None,
                input_preview=_preview(frame.input) if frame is not None else "",
                output_preview=_preview(frame.output) if frame is not None else "",
            )
        )

    trace_summary = trace.to_blamer_summary(
        max_field_chars=TRACE_FIELD_CHAR_LIMIT
    ) or "No leaf invocations were recorded."
    return BlamerInput(
        final_answer=trace.final_answer_text,
        user_critique=feedback.final_answer_critique,
        desired_behavior=feedback.desired_behavior or "",
        trace_summary=trace_summary,
        leaves=leaves,
    )


def _agent_attr(agent: Agent[Any, Any] | None, attr: str) -> str:
    if agent is None:
        return ""
    value = getattr(agent, attr, "")
    return "" if value is None else str(value)


def _preview(value: dict[str, Any]) -> str:
    return _truncate(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        LEAF_PREVIEW_CHAR_LIMIT,
    )


def _truncate(value: str, max_chars: int) -> str:
    cap = max(0, max_chars)
    if len(value) <= cap:
        return value
    return f"{value[:cap]}...[truncated, total={len(value)} chars]"


__all__ = [
    "KNOWN_LEAF_PATHS",
    "SPECIAL_TARGETS",
    "LeafSummary",
    "BlamerInput",
    "BlamerOutput",
    "Blamer",
    "default_blamer_config",
    "render_blamer_input",
]
