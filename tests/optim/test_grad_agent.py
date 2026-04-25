"""Offline tests for `operad.optim.grad_agent`.

Covers construction, class contract, factory helpers (`propagate`,
`parameter_grad`), null-gradient short-circuit, registry coverage,
and serialization / truncation helpers. Every LLM call is stubbed
out by overriding `forward` on a local subclass.
"""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import BaseModel

from operad.optim import (
    PARAMETER_GRAD_AGENTS,
    BackpropAgent,
    CategoricalParameterGrad,
    ExampleListParameterGrad,
    FloatParameterGrad,
    ParameterGradAgent,
    ParameterGradInput,
    ParameterGradOutput,
    ParameterKind,
    PropagateInput,
    PropagateOutput,
    RuleListParameterGrad,
    TextParameter,
    TextParameterGrad,
    TextualGradient,
    parameter_grad,
    parameter_grad_for,
    propagate,
)
from operad.optim.grad_agent import _dump, _truncate
from tests._helpers.fake_leaf import A, B, FakeLeaf


# ---------------------------------------------------------------------------
# Test stubs
# ---------------------------------------------------------------------------


class _StubBackprop(BackpropAgent):
    """Records invocations and returns a canned PropagateOutput."""

    def __init__(self, *, canned: PropagateOutput, config=None) -> None:
        super().__init__(config=config)
        self._canned = canned
        self.call_count = 0
        self.last_input: PropagateInput | None = None

    async def forward(self, x: PropagateInput) -> PropagateOutput:
        self.call_count += 1
        self.last_input = x
        return self._canned

    def reset_counters(self) -> None:
        self.call_count = 0
        self.last_input = None


class _StubParamGrad(ParameterGradAgent):
    def __init__(self, *, canned: ParameterGradOutput, config=None) -> None:
        super().__init__(config=config)
        self._canned = canned
        self.call_count = 0
        self.last_input: ParameterGradInput | None = None

    async def forward(self, x: ParameterGradInput) -> ParameterGradOutput:
        self.call_count += 1
        self.last_input = x
        return self._canned

    def reset_counters(self) -> None:
        self.call_count = 0
        self.last_input = None


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_backprop_agent_constructs_without_config():
    BackpropAgent()


def test_backprop_agent_constructs_with_cfg(cfg):
    BackpropAgent(config=cfg)


@pytest.mark.parametrize(
    "cls",
    [
        TextParameterGrad,
        RuleListParameterGrad,
        ExampleListParameterGrad,
        FloatParameterGrad,
        CategoricalParameterGrad,
    ],
)
def test_parameter_grad_subclass_constructs_without_config(cls):
    cls()


@pytest.mark.parametrize(
    "cls",
    [
        TextParameterGrad,
        RuleListParameterGrad,
        ExampleListParameterGrad,
        FloatParameterGrad,
        CategoricalParameterGrad,
    ],
)
def test_parameter_grad_subclass_constructs_with_cfg(cls, cfg):
    cls(config=cfg)


# ---------------------------------------------------------------------------
# Class contract
# ---------------------------------------------------------------------------


def test_backprop_agent_class_contract():
    assert BackpropAgent.input is PropagateInput
    assert BackpropAgent.output is PropagateOutput
    assert BackpropAgent.role
    assert BackpropAgent.task
    assert len(BackpropAgent.rules) > 0
    assert BackpropAgent.default_sampling == {"temperature": 0.3}


def test_parameter_grad_agent_class_contract():
    assert ParameterGradAgent.input is ParameterGradInput
    assert ParameterGradAgent.output is ParameterGradOutput
    assert ParameterGradAgent.role
    assert ParameterGradAgent.task
    assert len(ParameterGradAgent.rules) > 0
    assert ParameterGradAgent.default_sampling == {"temperature": 0.3}


@pytest.mark.parametrize(
    "cls",
    [
        TextParameterGrad,
        RuleListParameterGrad,
        ExampleListParameterGrad,
        FloatParameterGrad,
        CategoricalParameterGrad,
    ],
)
def test_specialized_subclass_refines_task(cls):
    assert cls.task != ParameterGradAgent.task
    assert cls.input is ParameterGradInput
    assert cls.output is ParameterGradOutput


# ---------------------------------------------------------------------------
# propagate()
# ---------------------------------------------------------------------------


async def test_propagate_wraps_output_into_textual_gradient(cfg):
    node = FakeLeaf(config=cfg, input=A, output=B)
    stub = _StubBackprop(
        config=cfg,
        canned=PropagateOutput(
            message="node output should be terser",
            by_field={"text": "shorten"},
            severity=0.6,
        ),
    )
    await stub.abuild()
    stub.reset_counters()

    grad = await propagate(
        node,
        rendered_prompt="rendered system prompt of node",
        input=A(text="hello"),
        output=B(value=1),
        downstream_grad=TextualGradient(message="downstream wants brevity", severity=0.9),
        propagator=stub,
    )

    assert stub.call_count == 1
    assert isinstance(grad, TextualGradient)
    assert grad.message == "node output should be terser"
    assert grad.by_field == {"text": "shorten"}
    assert grad.severity == 0.6


async def test_propagate_passes_serialized_io_and_downstream_fields(cfg):
    node = FakeLeaf(config=cfg, input=A, output=B)
    stub = _StubBackprop(
        config=cfg,
        canned=PropagateOutput(message="ok", severity=0.0),
    )
    await stub.abuild()
    stub.reset_counters()

    await propagate(
        node,
        rendered_prompt="the prompt",
        input=A(text="hi"),
        output=B(value=42),
        downstream_grad=TextualGradient(
            message="please change X",
            by_field={"X": "do Y"},
            severity=1.0,
        ),
        propagator=stub,
    )

    assert stub.last_input is not None
    assert stub.last_input.prompt == "the prompt"
    assert '"text": "hi"' in stub.last_input.input_str
    assert '"value": 42' in stub.last_input.output_str
    assert stub.last_input.downstream_gradient == "please change X"
    assert stub.last_input.downstream_by_field == {"X": "do Y"}


async def test_propagate_null_gradient_short_circuits(cfg):
    node = FakeLeaf(config=cfg, input=A, output=B)
    stub = _StubBackprop(
        config=cfg,
        canned=PropagateOutput(message="should not appear", severity=1.0),
    )
    await stub.abuild()
    stub.reset_counters()

    grad = await propagate(
        node,
        rendered_prompt="irrelevant",
        input=A(),
        output=B(),
        downstream_grad=TextualGradient.null_gradient(),
        propagator=stub,
    )

    assert stub.call_count == 0
    assert grad.severity == 0.0
    assert grad.message == ""


async def test_propagate_truncates_long_rendered_prompt(cfg):
    node = FakeLeaf(config=cfg, input=A, output=B)
    stub = _StubBackprop(
        config=cfg,
        canned=PropagateOutput(message="ok", severity=0.0),
    )
    await stub.abuild()
    stub.reset_counters()

    long_prompt = "x" * 20_000
    await propagate(
        node,
        rendered_prompt=long_prompt,
        input=A(),
        output=B(),
        downstream_grad=TextualGradient(message="fix"),
        propagator=stub,
        max_prompt_chars=100,
    )

    assert stub.last_input is not None
    assert "[truncated]" in stub.last_input.prompt
    assert len(stub.last_input.prompt) < 200


# ---------------------------------------------------------------------------
# parameter_grad()
# ---------------------------------------------------------------------------


async def test_parameter_grad_wraps_output_into_textual_gradient(cfg):
    node = FakeLeaf(config=cfg, input=A, output=B)
    node.role = "current role text"
    param = TextParameter.from_agent(node, "role", "role")

    stub = _StubParamGrad(
        config=cfg,
        canned=ParameterGradOutput(
            message="role should be more authoritative",
            severity=0.8,
            target_paths=["role"],
        ),
    )
    await stub.abuild()
    stub.reset_counters()

    grad = await parameter_grad(
        param,
        node,
        rendered_prompt="prompt",
        input=A(),
        output=B(),
        output_grad=TextualGradient(message="outputs lack authority", severity=0.9),
        grad_agent=stub,
    )

    assert stub.call_count == 1
    assert grad.message == "role should be more authoritative"
    assert grad.severity == 0.8
    assert grad.target_paths == ["role"]


async def test_parameter_grad_passes_parameter_fields(cfg):
    node = FakeLeaf(config=cfg, input=A, output=B)
    node.role = "original role"
    param = TextParameter.from_agent(node, "role", "role")

    stub = _StubParamGrad(
        config=cfg,
        canned=ParameterGradOutput(message="ok", severity=0.0),
    )
    await stub.abuild()
    stub.reset_counters()

    await parameter_grad(
        param,
        node,
        rendered_prompt="p",
        input=A(),
        output=B(),
        output_grad=TextualGradient(message="change something", severity=1.0),
        grad_agent=stub,
    )

    assert stub.last_input is not None
    assert stub.last_input.parameter_kind == "role"
    assert stub.last_input.parameter_path == "role"
    assert "original role" in stub.last_input.current_value
    assert stub.last_input.output_gradient == "change something"


async def test_parameter_grad_null_gradient_short_circuits(cfg):
    node = FakeLeaf(config=cfg, input=A, output=B)
    node.role = "r"
    param = TextParameter.from_agent(node, "role", "role")

    stub = _StubParamGrad(
        config=cfg,
        canned=ParameterGradOutput(message="should not appear", severity=1.0),
    )
    await stub.abuild()
    stub.reset_counters()

    grad = await parameter_grad(
        param,
        node,
        rendered_prompt="p",
        input=A(),
        output=B(),
        output_grad=TextualGradient.null_gradient(),
        grad_agent=stub,
    )

    assert stub.call_count == 0
    assert grad.severity == 0.0
    assert grad.message == ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_EXPECTED_KINDS: set[ParameterKind] = {
    "role",
    "task",
    "style",
    "rules",
    "rule_i",
    "examples",
    "example_i",
    "temperature",
    "top_p",
    "top_k",
    "model",
    "backend",
    "renderer",
}


def test_registry_covers_all_trainable_kinds():
    for kind in _EXPECTED_KINDS:
        assert kind in PARAMETER_GRAD_AGENTS
        assert issubclass(PARAMETER_GRAD_AGENTS[kind], ParameterGradAgent)


def test_registry_maps_kinds_to_expected_classes():
    assert PARAMETER_GRAD_AGENTS["role"] is TextParameterGrad
    assert PARAMETER_GRAD_AGENTS["task"] is TextParameterGrad
    assert PARAMETER_GRAD_AGENTS["rule_i"] is TextParameterGrad
    assert PARAMETER_GRAD_AGENTS["rules"] is RuleListParameterGrad
    assert PARAMETER_GRAD_AGENTS["examples"] is ExampleListParameterGrad
    assert PARAMETER_GRAD_AGENTS["example_i"] is ExampleListParameterGrad
    assert PARAMETER_GRAD_AGENTS["temperature"] is FloatParameterGrad
    assert PARAMETER_GRAD_AGENTS["top_p"] is FloatParameterGrad
    assert PARAMETER_GRAD_AGENTS["top_k"] is FloatParameterGrad
    assert PARAMETER_GRAD_AGENTS["model"] is CategoricalParameterGrad
    assert PARAMETER_GRAD_AGENTS["backend"] is CategoricalParameterGrad
    assert PARAMETER_GRAD_AGENTS["renderer"] is CategoricalParameterGrad


def test_parameter_grad_for_returns_registered_class():
    assert parameter_grad_for("role") is TextParameterGrad
    assert parameter_grad_for("temperature") is FloatParameterGrad


def test_parameter_grad_for_raises_for_extra_kind():
    with pytest.raises(NotImplementedError, match="extra"):
        parameter_grad_for("extra")


def test_every_parameter_kind_accounted_for():
    all_kinds = set(get_args(ParameterKind))
    unmapped = all_kinds - _EXPECTED_KINDS
    assert unmapped == {"extra"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Thing(BaseModel):
    x: int = 1
    y: str = "hi"


def test_dump_serializes_basemodel_as_json():
    out = _dump(_Thing(x=7, y="hello"))
    assert '"x": 7' in out
    assert '"y": "hello"' in out


def test_dump_falls_back_to_str_for_non_basemodel():
    assert _dump(42) == "42"
    assert _dump(["a", "b"]) == "['a', 'b']"


def test_truncate_passthrough_under_limit():
    assert _truncate("short", 100) == "short"


def test_truncate_applies_marker_over_limit():
    out = _truncate("x" * 50, 10)
    assert out.startswith("x" * 10)
    assert "[truncated]" in out
