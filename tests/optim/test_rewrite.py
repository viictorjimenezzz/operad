"""Offline tests for `operad.optim.rewrite`.

Every test stubs the rewriter's `forward` so no real model is contacted.
Covers: constructor deferral, one happy path per rewriter kind, the
retry-then-raise semantics of `apply_rewrite` under a constraint
violation, vocab rejection, and full `REWRITE_AGENTS` registry coverage.
"""

from __future__ import annotations

import json
from typing import get_args

import pytest

from operad.core.example import Example
from operad.optim import (
    CategoricalParameter,
    CategoricalRewriter,
    ExampleListParameter,
    ExampleListRewriter,
    FloatParameter,
    FloatRewriter,
    NumericConstraint,
    ParameterKind,
    REWRITE_AGENTS,
    RewriteAgent,
    RewriteRequest,
    RewriteResponse,
    RuleListParameter,
    RuleListRewriter,
    TextConstraint,
    TextParameter,
    TextRewriter,
    TextualGradient,
    VocabConstraint,
    apply_rewrite,
    rewriter_for,
)
from tests._helpers.fake_leaf import A, B, FakeLeaf


# ---------------------------------------------------------------------------
# Stubs — every rewriter-specific test subclasses the real rewriter and
# overrides `forward` so no strands / provider code path is ever exercised.
# ---------------------------------------------------------------------------


class StubTextRewriter(TextRewriter):
    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        # During `build()` the tracer hands us a `model_construct`ed
        # sentinel whose required fields are unset — access defensively.
        old = getattr(x, "old_value", "")
        return RewriteResponse(new_value=old + " [revised]")


class StubRuleListRewriter(RuleListRewriter):
    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        return RewriteResponse(new_value=json.dumps(["rewritten-a", "rewritten-b"]))


class StubExampleListRewriter(ExampleListRewriter):
    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        items = [
            {"input": {"text": "x"}, "output": {"value": 10}},
            {"input": {"text": "y"}, "output": {"value": 11}},
        ]
        return RewriteResponse(new_value=json.dumps(items))


class StubFloatRewriter(FloatRewriter):
    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        return RewriteResponse(new_value="0.42")


class StubCategoricalRewriter(CategoricalRewriter):
    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        return RewriteResponse(new_value="ollama")


class BadLengthRewriter(TextRewriter):
    """Always returns a 20-char string — exceeds TextConstraint(max_length=5)."""

    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        return RewriteResponse(new_value="x" * 20)


class BadVocabRewriter(CategoricalRewriter):
    """Always returns a token outside the allowed vocabulary."""

    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        return RewriteResponse(new_value="not-in-vocab")


# ---------------------------------------------------------------------------
# Constructor defers build
# ---------------------------------------------------------------------------


def test_rewriters_construct_with_config_none():
    TextRewriter(config=None)
    RuleListRewriter(config=None)
    ExampleListRewriter(config=None)
    FloatRewriter(config=None)
    CategoricalRewriter(config=None)


def test_rewriter_subclasses_carry_kind_specific_sampling():
    assert FloatRewriter.default_sampling["temperature"] == 0.0
    assert CategoricalRewriter.default_sampling["temperature"] == 0.0
    assert TextRewriter.default_sampling["temperature"] == 0.7


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_apply_rewrite_text_role(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.role = "initial role"
    p = TextParameter.from_agent(leaf, "role", "role")
    grad = TextualGradient(message="be more specific", severity=0.7)

    rewriter = await StubTextRewriter(config=cfg).abuild()
    await apply_rewrite(p, grad, rewriter, lr=0.5)

    assert leaf.role == "initial role [revised]"
    assert p.read() == "initial role [revised]"


async def test_apply_rewrite_rules_list(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.rules = ["r0", "r1"]
    p = RuleListParameter.from_agent(leaf, "rules", "rules")
    grad = TextualGradient(message="rewrite the rule set", severity=1.0)

    rewriter = await StubRuleListRewriter(config=cfg).abuild()
    await apply_rewrite(p, grad, rewriter, lr=0.9)

    assert leaf.rules == ["rewritten-a", "rewritten-b"]


async def test_apply_rewrite_examples_list(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.examples = [Example(input=A(text="hi"), output=B(value=1))]
    p = ExampleListParameter.from_agent(leaf, "examples", "examples")
    grad = TextualGradient(message="replace the examples", severity=0.8)

    rewriter = await StubExampleListRewriter(config=cfg).abuild()
    await apply_rewrite(p, grad, rewriter, lr=0.7)

    assert len(leaf.examples) == 2
    assert leaf.examples[0].input.text == "x"
    assert leaf.examples[0].output.value == 10
    assert leaf.examples[1].input.text == "y"
    assert leaf.examples[1].output.value == 11


async def test_apply_rewrite_float_temperature(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    p = FloatParameter.from_agent(
        leaf,
        "config.sampling.temperature",
        "temperature",
        constraint=NumericConstraint(min=0.0, max=2.0),
    )
    grad = TextualGradient(message="lower temperature", severity=0.6)

    rewriter = await StubFloatRewriter(config=cfg).abuild()
    await apply_rewrite(p, grad, rewriter, lr=0.5)

    assert leaf.config.sampling.temperature == 0.42
    assert p.read() == 0.42


async def test_apply_rewrite_categorical_backend(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    p = CategoricalParameter.from_agent(
        leaf,
        "config.backend",
        "backend",
        constraint=VocabConstraint(allowed=["llamacpp", "ollama", "openai"]),
    )
    grad = TextualGradient(message="switch backend", severity=0.5)

    rewriter = await StubCategoricalRewriter(config=cfg).abuild()
    await apply_rewrite(p, grad, rewriter, lr=0.8)

    assert leaf.config.backend == "ollama"


# ---------------------------------------------------------------------------
# Constraint violation — retry once, then raise
# ---------------------------------------------------------------------------


async def test_apply_rewrite_raises_when_max_length_violated_twice(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.role = "ok"
    p = TextParameter.from_agent(
        leaf, "role", "role", constraint=TextConstraint(max_length=5)
    )
    grad = TextualGradient(message="fix it", severity=1.0)

    rewriter = await BadLengthRewriter(config=cfg).abuild()

    with pytest.raises(RuntimeError, match="still violates its constraint"):
        await apply_rewrite(p, grad, rewriter, lr=0.5)

    # Underlying value is untouched after the failed rewrite.
    assert leaf.role == "ok"


async def test_apply_rewrite_raises_on_vocab_violation(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    p = CategoricalParameter.from_agent(
        leaf,
        "config.backend",
        "backend",
        constraint=VocabConstraint(allowed=["llamacpp", "ollama"]),
    )
    grad = TextualGradient(message="swap backend", severity=1.0)

    rewriter = await BadVocabRewriter(config=cfg).abuild()

    with pytest.raises(RuntimeError, match="still violates its constraint"):
        await apply_rewrite(p, grad, rewriter, lr=0.5)

    assert leaf.config.backend == "llamacpp"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_covers_every_parameter_kind():
    for kind in get_args(ParameterKind):
        assert kind in REWRITE_AGENTS, f"missing rewriter for kind {kind!r}"
        cls = rewriter_for(kind)
        assert issubclass(cls, RewriteAgent)


def test_rewriter_for_unknown_kind_raises():
    with pytest.raises(KeyError, match="no rewriter registered"):
        rewriter_for("not-a-kind")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Schema-aware retry: ValidationError details injected into second prompt
# ---------------------------------------------------------------------------


class ValidationErrorRewriter(ExampleListRewriter):
    """Returns bad JSON on first real call, valid JSON on second; records requests."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls: list[RewriteRequest] = []

    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        # Tracer hands a sentinel with no old_value; skip it.
        if not getattr(x, "old_value", ""):
            return RewriteResponse(new_value="[]")
        self.calls.append(x)
        if len(self.calls) == 1:
            # value is a string, not an int — will raise ValidationError
            bad = [{"input": {"text": "q"}, "output": {"value": "not-an-int"}}]
            return RewriteResponse(new_value=json.dumps(bad))
        good = [{"input": {"text": "q"}, "output": {"value": 42}}]
        return RewriteResponse(new_value=json.dumps(good))


async def test_retry_prompt_contains_validation_error_details(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.examples = [Example(input=A(text="hi"), output=B(value=1))]
    p = ExampleListParameter.from_agent(leaf, "examples", "examples")
    grad = TextualGradient(message="improve examples", severity=0.8)

    rewriter = await ValidationErrorRewriter(config=cfg).abuild()
    await apply_rewrite(p, grad, rewriter, lr=0.7)

    # Two real calls were made: first (bad) and second (good).
    assert len(rewriter.calls) == 2

    second_hint = rewriter.calls[1].constraint_hint
    assert "Schema validation" in second_hint
    # The field path from the ValidationError should appear in the hint.
    assert "value" in second_hint
