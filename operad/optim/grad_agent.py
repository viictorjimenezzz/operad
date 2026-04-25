"""LLM-backed gradient agents for `operad.optim`.

`BackpropAgent` propagates a downstream critique through one node to
produce the critique on that node's output. `ParameterGradAgent` takes
the output critique plus a parameter and emits the critique on that
specific parameter. Both are `Agent[In, Out]` subclasses so they reuse
operad's cassette / hashing / observer / schema-validation stack.

Consumed by the `backward()` tape walk (slot 3-1); unrelated to
rewrite-agents (slot 2-3).
"""

from __future__ import annotations

from inspect import cleandoc
from typing import Any

from pydantic import BaseModel, Field

from operad.core.agent import Agent, Example
from operad.optim.parameter import Parameter, ParameterKind, TextualGradient


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PropagateInput(BaseModel):
    """Forward record plus downstream critique, input to `BackpropAgent`."""

    prompt: str = Field(
        description="The rendered system prompt of the node being back-propagated through.",
    )
    input_str: str = Field(
        description="JSON dump of the node's input at this tape entry.",
    )
    output_str: str = Field(
        description="JSON dump of the node's output at this tape entry.",
    )
    downstream_gradient: str = Field(
        description=(
            "Critique flowing back from the downstream layer — what the "
            "next layer wanted differently."
        ),
    )
    downstream_by_field: dict[str, str] = Field(
        default_factory=dict,
        description="Optional per-field breakdown of the downstream critique.",
    )


class PropagateOutput(BaseModel):
    """Critique of the node's output, emitted by `BackpropAgent`."""

    message: str = Field(
        description=(
            "Critique of this node's output — what this node should have "
            "emitted differently."
        ),
    )
    by_field: dict[str, str] = Field(
        default_factory=dict,
        description="Optional per-field breakdown of the critique.",
    )
    severity: float = Field(
        default=1.0,
        description="Magnitude of the critique; 0.0 means no update needed.",
    )


class ParameterGradInput(BaseModel):
    """Forward record plus output critique plus parameter handle."""

    parameter_kind: str = Field(
        description="Kind tag for this parameter (role, task, rules, temperature, ...).",
    )
    parameter_path: str = Field(
        description="Dotted path of the parameter on the owning agent.",
    )
    current_value: str = Field(
        description="JSON dump of the parameter's current value.",
    )
    prompt: str = Field(
        description="The rendered system prompt of the node this parameter lives on.",
    )
    input_str: str = Field(
        description="JSON dump of the node's input at this tape entry.",
    )
    output_str: str = Field(
        description="JSON dump of the node's output at this tape entry.",
    )
    output_gradient: str = Field(
        description="Critique of the node's output — what the output should have been.",
    )
    output_by_field: dict[str, str] = Field(
        default_factory=dict,
        description="Optional per-field breakdown of the output critique.",
    )


class ParameterGradOutput(BaseModel):
    """Critique of a specific parameter, emitted by `ParameterGradAgent`."""

    message: str = Field(
        description="Critique targeted at this parameter — how it should change.",
    )
    severity: float = Field(
        default=1.0,
        description="Magnitude of the critique; 0.0 means this parameter is not implicated.",
    )
    target_paths: list[str] = Field(
        default_factory=list,
        description="Optional blame-routing hints (e.g. specific rule indices).",
    )


# ---------------------------------------------------------------------------
# Base agent classes
# ---------------------------------------------------------------------------


class BackpropAgent(Agent[PropagateInput, PropagateOutput]):
    """Propagate a downstream critique through one node's forward record."""

    input = PropagateInput
    output = PropagateOutput

    role = "You are a rigorous error-attribution analyst for a chain of agents."
    task = cleandoc("""
        Produce the critique on THIS agent's output — what this node
        should have emitted differently — given its forward record and
        the downstream critique.
    """)
    rules = (
        "Do not fabricate facts about the node's input or output — work only from the strings provided.",
        "If the output is already correct with respect to the downstream gradient, return severity=0.0 and an empty message.",
        "Be specific. Name the fields or spans that should change; vague critiques produce bad rewrites.",
        "Do not propose fixes to the downstream layer — only to this node's output.",
    )
    examples = (
        Example[PropagateInput, PropagateOutput](
            input=PropagateInput(
                prompt="You summarize user questions. Respond in one sentence.",
                input_str='{"question": "Who wrote Hamlet?"}',
                output_str='{"summary": "The user asks about a play."}',
                downstream_gradient="Summary is too vague — the question is specifically about authorship.",
            ),
            output=PropagateOutput(
                message="The summary should identify authorship as the subject, e.g. 'The user asks who authored Hamlet.'",
                severity=0.7,
            ),
        ),
    )
    default_sampling = {"temperature": 0.3}


class ParameterGradAgent(Agent[ParameterGradInput, ParameterGradOutput]):
    """Attribute an output critique to one specific parameter."""

    input = ParameterGradInput
    output = ParameterGradOutput

    role = "You are a parameter-attribution analyst."
    task = cleandoc("""
        Identify how THIS specific parameter should change to close
        the gap indicated by the critique on the node's output.
    """)
    rules = (
        "Attribute only to this parameter; other parameters are critiqued in separate calls.",
        "If this parameter is not implicated by the output critique, return severity=0.0 with empty message.",
        "Be specific. Describe what the value should become or what property it lacks.",
        "Do not rewrite the parameter here — that is a separate rewrite step.",
    )
    examples = (
        Example[ParameterGradInput, ParameterGradOutput](
            input=ParameterGradInput(
                parameter_kind="role",
                parameter_path="role",
                current_value='"You help users."',
                prompt="You help users.",
                input_str="{}",
                output_str="{}",
                output_gradient="The agent's answers lack domain authority — they should sound like a specialist.",
            ),
            output=ParameterGradOutput(
                message=(
                    "The role is too generic; it should establish the agent "
                    "as a domain expert (e.g. name the specialty) so answers "
                    "carry authority."
                ),
                severity=0.8,
            ),
        ),
    )
    default_sampling = {"temperature": 0.3}


# ---------------------------------------------------------------------------
# Kind-specialized subclasses
# ---------------------------------------------------------------------------


class TextParameterGrad(ParameterGradAgent):
    """Gradient agent for free-text parameters (`role`, `task`, single rule)."""

    task = cleandoc("""
        Critique a free-text parameter (role, task, or single rule).
        Describe what the text should convey to produce a better
        output. Keep the critique concise, unambiguous, and
        model-agnostic.
    """)


class RuleListParameterGrad(ParameterGradAgent):
    """Gradient agent for the `rules` list."""

    task = cleandoc("""
        Critique a list of rules that constrain an agent. Identify
        which rules to add, remove, or rewrite. Prefer orthogonal
        rules and a short list over redundant or overlapping rules.
    """)


class ExampleListParameterGrad(ParameterGradAgent):
    """Gradient agent for the `examples` list (or a single example)."""

    task = cleandoc("""
        Critique a list of (input, output) examples that prime an
        agent. Identify examples to add, remove, or edit so the set
        better covers the observed failure modes without contradicting
        the types.
    """)


class FloatParameterGrad(ParameterGradAgent):
    """Gradient agent for numeric sampling knobs (`temperature`, `top_p`, `top_k`)."""

    task = cleandoc("""
        Critique a numeric sampling knob (temperature, top_p, top_k).
        Describe the direction (increase / decrease) and relative
        magnitude that would produce a better output, not a specific
        number.
    """)


class CategoricalParameterGrad(ParameterGradAgent):
    """Gradient agent for categorical choices (`model`, `backend`, `renderer`)."""

    task = cleandoc("""
        Critique a categorical choice (model, backend, renderer).
        Describe what property the current choice lacks; stay within
        the allowed vocabulary.
    """)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


PARAMETER_GRAD_AGENTS: dict[ParameterKind, type[ParameterGradAgent]] = {
    "role": TextParameterGrad,
    "task": TextParameterGrad,
    "style": TextParameterGrad,
    "rules": RuleListParameterGrad,
    "rule_i": TextParameterGrad,
    "examples": ExampleListParameterGrad,
    "example_i": ExampleListParameterGrad,
    "temperature": FloatParameterGrad,
    "top_p": FloatParameterGrad,
    "top_k": FloatParameterGrad,
    "model": CategoricalParameterGrad,
    "backend": CategoricalParameterGrad,
    "renderer": CategoricalParameterGrad,
}


def parameter_grad_for(kind: ParameterKind) -> type[ParameterGradAgent]:
    """Return the kind-specialized `ParameterGradAgent` subclass for `kind`."""
    try:
        return PARAMETER_GRAD_AGENTS[kind]
    except KeyError as e:
        raise NotImplementedError(
            f"No parameter-grad agent for kind {kind!r}; "
            "optimizers for it land in wave 4"
        ) from e


# ---------------------------------------------------------------------------
# Serialization + truncation helpers
# ---------------------------------------------------------------------------


def _dump(obj: Any) -> str:
    if isinstance(obj, BaseModel):
        return obj.model_dump_json(indent=2)
    return str(obj)


_TRUNCATE_MARKER = "\n…[truncated]"


def _truncate(s: str, max_chars: int) -> str:
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + _TRUNCATE_MARKER


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


async def propagate(
    node: Agent[Any, Any],
    rendered_prompt: str,
    input: Any,
    output: Any,
    downstream_grad: TextualGradient,
    propagator: BackpropAgent,
    *,
    max_prompt_chars: int = 8000,
) -> TextualGradient:
    """Propagate `downstream_grad` through `node` using `propagator`.

    Short-circuits to a null gradient (no LLM call) when the downstream
    gradient carries no signal. `node` is reserved for the `backward()`
    tape walk (3-1) and is not consumed here.
    """
    _ = node

    if downstream_grad.severity == 0.0 and not downstream_grad.message:
        return TextualGradient.null_gradient()

    payload = PropagateInput(
        prompt=_truncate(rendered_prompt, max_prompt_chars),
        input_str=_dump(input),
        output_str=_dump(output),
        downstream_gradient=downstream_grad.message,
        downstream_by_field=dict(downstream_grad.by_field),
    )
    resp = (await propagator(payload)).response
    return TextualGradient(
        message=resp.message,
        by_field=dict(resp.by_field),
        severity=resp.severity,
    )


async def parameter_grad(
    param: Parameter[Any],
    node: Agent[Any, Any],
    rendered_prompt: str,
    input: Any,
    output: Any,
    output_grad: TextualGradient,
    grad_agent: ParameterGradAgent,
    *,
    max_prompt_chars: int = 8000,
) -> TextualGradient:
    """Compute the per-parameter gradient for `param` given `output_grad`.

    Short-circuits to a null gradient (no LLM call) when the output
    gradient carries no signal.
    """
    _ = node

    if output_grad.severity == 0.0 and not output_grad.message:
        return TextualGradient.null_gradient()

    payload = ParameterGradInput(
        parameter_kind=param.kind,
        parameter_path=param.path,
        current_value=_dump(param.value),
        prompt=_truncate(rendered_prompt, max_prompt_chars),
        input_str=_dump(input),
        output_str=_dump(output),
        output_gradient=output_grad.message,
        output_by_field=dict(output_grad.by_field),
    )
    resp = (await grad_agent(payload)).response
    return TextualGradient(
        message=resp.message,
        severity=resp.severity,
        target_paths=list(resp.target_paths),
    )


__all__ = [
    "BackpropAgent",
    "CategoricalParameterGrad",
    "ExampleListParameterGrad",
    "FloatParameterGrad",
    "PARAMETER_GRAD_AGENTS",
    "ParameterGradAgent",
    "ParameterGradInput",
    "ParameterGradOutput",
    "PropagateInput",
    "PropagateOutput",
    "RuleListParameterGrad",
    "TextParameterGrad",
    "parameter_grad",
    "parameter_grad_for",
    "propagate",
]
