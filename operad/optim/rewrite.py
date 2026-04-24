"""Rewrite agents — the "apply" half of every textual-gradient step.

An `Optimizer` turns a `(Parameter, TextualGradient)` pair into a new
parameter value by calling a kind-specialized `RewriteAgent`. Each
rewriter is a first-class `Agent[RewriteRequest, RewriteResponse]`, so
it inherits the full hashing / cassette / observer stack; the value-type
adaptation (JSON list for rules, numeric string for temperature, ...)
happens in `apply_rewrite`, which is the one entry point an optimizer
needs.

The brief for this module is `.conductor/optim/2-3-rewrite-agents.md`.
Downstream consumer is slot 3-2 (`Optimizer.step()`).
"""

from __future__ import annotations

import json
from inspect import cleandoc
from typing import Any

from pydantic import BaseModel, Field

from operad.core.agent import Agent
from operad.core.example import Example
from operad.optim.parameter import (
    ListConstraint,
    NumericConstraint,
    Parameter,
    ParameterConstraint,
    ParameterKind,
    TextConstraint,
    TextualGradient,
    VocabConstraint,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RewriteRequest(BaseModel):
    """Input to a `RewriteAgent`: old value + gradient + constraints."""

    old_value: str = Field(
        description=(
            "The current parameter value, serialized as text. Free-form "
            "string for `role`/`task`/`rule_i`; a JSON-encoded list for "
            "`rules` and `examples`; a stringified number for "
            "`temperature`/`top_p`/`top_k`; a vocab token for "
            "`model`/`backend`/`renderer`."
        )
    )
    gradient: str = Field(
        description=(
            "Natural-language critique of the current value — the "
            "`TextualGradient.message`. Describes how the value should "
            "change."
        )
    )
    gradient_by_field: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optional per-field breakdown of the critique. Keys are field "
            "names inside `old_value` when it is structured; values are "
            "the critique specific to that field."
        ),
    )
    severity: float = Field(
        description=(
            "Magnitude of the critique on [0, 1]. `0.0` means no update "
            "is needed — return the old value unchanged."
        )
    )
    lr: float = Field(
        description=(
            "Learning-rate knob on [0, 1]. High values (>= 0.9) authorize "
            "a full rewrite driven by the gradient; low values (<= 0.2) "
            "require the smallest possible edit; values in between "
            "interpolate the edit magnitude."
        )
    )
    constraint_hint: str = Field(
        description=(
            "Plain-English description of the constraint the new value "
            "must satisfy (length limits, forbidden substrings, numeric "
            "bounds, allowed vocabulary, schema shape). Any violation "
            "must be treated as a hard error."
        )
    )
    parameter_kind: str = Field(
        description=(
            "One of the `ParameterKind` string values (`role`, `task`, "
            "`rules`, `examples`, `temperature`, ...). Lets the rewriter "
            "disambiguate the expected output shape."
        )
    )


class RewriteResponse(BaseModel):
    """Output of a `RewriteAgent`: the new value and optional rationale."""

    new_value: str = Field(
        description=(
            "The rewritten parameter value, in the same serialization as "
            "`RewriteRequest.old_value`. Plain string for text kinds, JSON "
            "list for list kinds, stringified number for numeric kinds, "
            "vocabulary token for categorical kinds."
        )
    )
    rationale: str = Field(
        default="",
        description=(
            "Short explanation of why this rewrite addresses the "
            "gradient. Kept separate from `new_value` so it is never "
            "confused with the value itself."
        ),
    )


# ---------------------------------------------------------------------------
# Base RewriteAgent
# ---------------------------------------------------------------------------


_BASE_RULES = (
    "Address the critique in `gradient` (and `gradient_by_field` when "
    "present); do not silently ignore it.",
    "The new value must satisfy `constraint_hint` exactly — no "
    "exceptions, no commentary substituting for the value.",
    "Scale the magnitude of your edit with `lr`: `lr >= 0.9` rewrites "
    "from scratch using the gradient as the primary guide; `lr <= 0.2` "
    "makes the smallest possible edit that resolves the gradient; "
    "intermediate values interpolate.",
)


class RewriteAgent(Agent[RewriteRequest, RewriteResponse]):
    """Base class for every kind-specialized rewriter.

    Subclasses override `role`, `task`, `rules`, `examples`, and
    `default_sampling` to match the value type they target. The rewriter
    itself never inspects the Python value — `apply_rewrite` handles
    serialization on the way in and parsing on the way out.
    """

    input = RewriteRequest
    output = RewriteResponse

    role = "You are a disciplined rewriter of agent-parameter values."
    task = cleandoc("""
        Produce a `new_value` that addresses the `gradient`, respects
        `constraint_hint`, and whose edit magnitude matches `lr`.
    """)
    rules = _BASE_RULES
    examples = (
        Example[RewriteRequest, RewriteResponse](
            input=RewriteRequest(
                old_value="You are a helpful assistant.",
                gradient="Be more concise and less generic.",
                severity=0.8,
                lr=0.7,
                constraint_hint="String value. Maximum length 120 characters.",
                parameter_kind="role",
            ),
            output=RewriteResponse(
                new_value="You are a concise, specific assistant.",
                rationale="Removed the generic 'helpful' framing to match the critique.",
            ),
        ),
    )
    default_sampling = {"temperature": 0.5}


class TextRewriter(RewriteAgent):
    """Rewriter for plain-string parameters (`role`, `task`, `rule_i`, `extra`).

    The LR mapping is documented on `RewriteAgent`: high `lr` fully
    rewrites the string, low `lr` performs a minimal surgical edit.
    """

    role = "You are a focused prompt engineer rewriting a single string field."
    task = cleandoc("""
        Produce a new string in `new_value` that resolves the
        `gradient` while respecting `constraint_hint`.
    """)
    rules = _BASE_RULES + (
        "Return a single string in `new_value` — no surrounding quotes, "
        "no JSON, no bullet points.",
    )
    examples = (
        Example[RewriteRequest, RewriteResponse](
            input=RewriteRequest(
                old_value="Score the candidate.",
                gradient="Task is ambiguous — say on what scale.",
                severity=0.9,
                lr=0.6,
                constraint_hint="String value. Maximum length 200 characters.",
                parameter_kind="task",
            ),
            output=RewriteResponse(
                new_value="Score the candidate on a 0.0–1.0 scale.",
                rationale="Added explicit scale per the critique.",
            ),
        ),
    )
    default_sampling = {"temperature": 0.7}


class RuleListRewriter(RewriteAgent):
    """Rewriter for the `rules` list parameter.

    `old_value` and `new_value` are both JSON-encoded `list[str]`.
    The prompt stresses orthogonal, short rules.
    """

    role = "You are a careful editor of prompt rule lists."
    task = cleandoc("""
        Produce a revised JSON-encoded list of rules in `new_value`
        that addresses the `gradient`.
    """)
    rules = _BASE_RULES + (
        "`new_value` must be valid JSON — a JSON array of strings.",
        "Each rule must be short, imperative, and orthogonal to the "
        "others; remove overlapping or contradictory rules.",
    )
    examples = (
        Example[RewriteRequest, RewriteResponse](
            input=RewriteRequest(
                old_value=json.dumps(
                    [
                        "Show your reasoning.",
                        "Always think step by step.",
                        "Answer concisely.",
                    ]
                ),
                gradient="First two rules overlap; drop the redundancy.",
                severity=0.8,
                lr=0.5,
                constraint_hint="List value. Maximum length 5 items. Each item: String value. Maximum length 140 characters.",
                parameter_kind="rules",
            ),
            output=RewriteResponse(
                new_value=json.dumps(
                    ["Show your reasoning.", "Answer concisely."]
                ),
                rationale="Removed the duplicative 'step by step' rule.",
            ),
        ),
    )
    default_sampling = {"temperature": 0.7}


class ExampleListRewriter(RewriteAgent):
    """Rewriter for the `examples` list parameter.

    `old_value` / `new_value` are JSON-encoded lists of
    `Example[In, Out]` dicts (`{"input": {...}, "output": {...}}`). The
    caller adds the Pydantic `In` and `Out` JSON schemas to
    `constraint_hint` so the model can emit items that validate.
    """

    role = "You are a careful editor of few-shot example sets."
    task = cleandoc("""
        Produce a revised JSON-encoded list of `{input, output}`
        example pairs in `new_value`. Each example's `input` must
        validate against the Input schema in `constraint_hint`; each
        `output` against the Output schema.
    """)
    rules = _BASE_RULES + (
        "`new_value` must be a JSON array of `{\"input\": ..., "
        "\"output\": ...}` objects.",
        "Every `input` and `output` must conform exactly to the "
        "schemas declared in `constraint_hint`; do not invent fields.",
    )
    examples = ()
    default_sampling = {"temperature": 0.5}


class FloatRewriter(RewriteAgent):
    """Rewriter for numeric sampling knobs (`temperature`, `top_p`, `top_k`).

    `old_value` is a stringified number; `new_value` must parse as a
    single float literal (no units, no prose).
    """

    role = "You are a precise tuner of numeric sampling knobs."
    task = cleandoc("""
        Produce a new numeric value — as a bare number in `new_value`
        — that resolves the `gradient` within the numeric bounds
        defined in `constraint_hint`.
    """)
    rules = _BASE_RULES + (
        "`new_value` must be a single base-10 number (e.g. `0.7`), "
        "with no units, no prefix, and no trailing text.",
    )
    examples = (
        Example[RewriteRequest, RewriteResponse](
            input=RewriteRequest(
                old_value="0.9",
                gradient="Outputs are too random; lower the temperature.",
                severity=0.7,
                lr=0.5,
                constraint_hint="Numeric value. Minimum: 0.0. Maximum: 2.0.",
                parameter_kind="temperature",
            ),
            output=RewriteResponse(
                new_value="0.4",
                rationale="Halved toward the lower end to reduce variance.",
            ),
        ),
    )
    default_sampling = {"temperature": 0.0, "max_tokens": 32}


class CategoricalRewriter(RewriteAgent):
    """Rewriter for vocabulary-bounded strings (`model`, `backend`, `renderer`).

    The response must be exactly one of the allowed tokens listed in
    `constraint_hint`; anything else is a constraint violation.
    """

    role = "You are a decisive picker of a single vocabulary token."
    task = cleandoc("""
        Pick a replacement token in `new_value` from the allowed
        vocabulary enumerated in `constraint_hint`, responding to the
        `gradient`.
    """)
    rules = _BASE_RULES + (
        "`new_value` must be exactly one of the allowed tokens — no "
        "punctuation, no paraphrase, no explanation.",
    )
    examples = (
        Example[RewriteRequest, RewriteResponse](
            input=RewriteRequest(
                old_value="llamacpp",
                gradient="Switch to the provider with better JSON support.",
                severity=0.6,
                lr=0.8,
                constraint_hint="Must be exactly one of: 'llamacpp', 'ollama', 'openai'.",
                parameter_kind="backend",
            ),
            output=RewriteResponse(
                new_value="openai",
                rationale="openai has native structured-output support.",
            ),
        ),
    )
    default_sampling = {"temperature": 0.0, "max_tokens": 64}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


REWRITE_AGENTS: dict[ParameterKind, type[RewriteAgent]] = {
    "role": TextRewriter,
    "task": TextRewriter,
    "rule_i": TextRewriter,
    "extra": TextRewriter,
    "rules": RuleListRewriter,
    "examples": ExampleListRewriter,
    "example_i": ExampleListRewriter,
    "temperature": FloatRewriter,
    "top_p": FloatRewriter,
    "top_k": FloatRewriter,
    "model": CategoricalRewriter,
    "backend": CategoricalRewriter,
    "renderer": CategoricalRewriter,
}


def rewriter_for(kind: ParameterKind) -> type[RewriteAgent]:
    """Return the `RewriteAgent` subclass appropriate for `kind`."""
    try:
        return REWRITE_AGENTS[kind]
    except KeyError as e:
        raise KeyError(f"no rewriter registered for ParameterKind {kind!r}") from e


# ---------------------------------------------------------------------------
# Constraint-hint rendering
# ---------------------------------------------------------------------------


def _describe_constraint(c: ParameterConstraint | None) -> str:
    if c is None:
        return "No explicit constraint — any valid value of the expected type."
    if isinstance(c, TextConstraint):
        parts = ["String value."]
        if c.max_length is not None:
            parts.append(f"Maximum length {c.max_length} characters.")
        if c.forbidden:
            forbid = ", ".join(repr(s) for s in c.forbidden)
            parts.append(f"Must not contain any of: {forbid}.")
        return " ".join(parts)
    if isinstance(c, NumericConstraint):
        parts = ["Numeric value."]
        if c.min is not None:
            parts.append(f"Minimum: {c.min}.")
        if c.max is not None:
            parts.append(f"Maximum: {c.max}.")
        if c.step is not None:
            parts.append(f"Step: {c.step}.")
        return " ".join(parts)
    if isinstance(c, VocabConstraint):
        allowed = ", ".join(repr(v) for v in c.allowed)
        return f"Must be exactly one of: {allowed}."
    if isinstance(c, ListConstraint):
        parts = ["List value."]
        if c.max_count is not None:
            parts.append(f"Maximum length {c.max_count} items.")
        if c.item is not None:
            parts.append(f"Each item: {_describe_constraint(c.item)}")
        return " ".join(parts)
    return "No explicit constraint — any valid value of the expected type."


# ---------------------------------------------------------------------------
# Value (de)serialization
# ---------------------------------------------------------------------------


def _serialize(param: Parameter[Any]) -> str:
    kind = param.kind
    value = param.value
    if kind in ("rules",):
        return json.dumps(list(value))
    if kind == "examples":
        return json.dumps([e.model_dump(mode="json") for e in value])
    if kind == "example_i":
        return json.dumps([value.model_dump(mode="json")])
    if kind in ("temperature", "top_p", "top_k"):
        return repr(float(value))
    return str(value)


def _parse(raw: str, param: Parameter[Any]) -> Any:
    kind = param.kind
    if kind == "rules":
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or not all(isinstance(s, str) for s in parsed):
            raise ValueError(f"expected JSON array of strings, got {raw!r}")
        return parsed
    if kind == "examples":
        items = json.loads(raw)
        owner = param._agent()
        return [
            Example(
                input=owner.input.model_validate(d["input"]),
                output=owner.output.model_validate(d["output"]),
            )
            for d in items
        ]
    if kind == "example_i":
        items = json.loads(raw)
        if not items:
            raise ValueError("expected a single-element JSON array, got empty")
        d = items[0]
        owner = param._agent()
        return Example(
            input=owner.input.model_validate(d["input"]),
            output=owner.output.model_validate(d["output"]),
        )
    if kind in ("temperature", "top_p", "top_k"):
        return float(raw.strip())
    return raw.strip() if kind in ("model", "backend", "renderer") else raw


def _enrich_hint_for_examples(hint: str, param: Parameter[Any]) -> str:
    owner = param._agent()
    in_schema = json.dumps(owner.input.model_json_schema())
    out_schema = json.dumps(owner.output.model_json_schema())
    return (
        f"{hint}\n"
        f"Input schema: {in_schema}\n"
        f"Output schema: {out_schema}"
    )


# ---------------------------------------------------------------------------
# apply_rewrite
# ---------------------------------------------------------------------------


async def apply_rewrite(
    param: Parameter[Any],
    grad: TextualGradient,
    rewriter: RewriteAgent,
    *,
    lr: float,
) -> None:
    """Invoke `rewriter` on `(param, grad, lr)` and write the result back.

    Dispatches value (de)serialization by `param.kind`, validates the
    parsed value against `param.constraint`, and retries once with a
    tightened prompt if the first attempt violates the constraint
    (either by raising inside `validate` or by being coerced to a
    different value). A second violation raises a descriptive error
    identifying the parameter path.
    """
    hint = _describe_constraint(param.constraint)
    if param.kind in ("examples", "example_i"):
        hint = _enrich_hint_for_examples(hint, param)

    def _build_request(extra: str = "") -> RewriteRequest:
        return RewriteRequest(
            old_value=_serialize(param),
            gradient=grad.message,
            gradient_by_field=dict(grad.by_field),
            severity=grad.severity,
            lr=lr,
            constraint_hint=hint + extra,
            parameter_kind=param.kind,
        )

    async def _invoke(req: RewriteRequest) -> RewriteResponse:
        envelope = await rewriter(req)
        return envelope.response

    def _check(new_value: Any) -> Any:
        if param.constraint is None:
            return new_value
        coerced = param.constraint.validate(new_value)
        if coerced != new_value:
            raise ValueError(
                f"value would be coerced by constraint: "
                f"{new_value!r} -> {coerced!r}"
            )
        return coerced

    try:
        resp = await _invoke(_build_request())
        new_value = _parse(resp.new_value, param)
        validated = _check(new_value)
    except Exception as first_err:
        tightened = (
            f"\nSTRICT: the previous attempt violated the constraint — "
            f"{first_err}. Return a value that strictly satisfies every "
            f"bullet above."
        )
        try:
            resp = await _invoke(_build_request(tightened))
            new_value = _parse(resp.new_value, param)
            validated = _check(new_value)
        except Exception as second_err:
            raise RuntimeError(
                f"rewrite for parameter {param.path!r} "
                f"({param.kind}) still violates its constraint after "
                f"one retry: {second_err}"
            ) from second_err

    param.write(validated)


__all__ = [
    "CategoricalRewriter",
    "ExampleListRewriter",
    "FloatRewriter",
    "REWRITE_AGENTS",
    "RewriteAgent",
    "RewriteRequest",
    "RewriteResponse",
    "RuleListRewriter",
    "TextRewriter",
    "apply_rewrite",
    "rewriter_for",
]
