"""Offline tests for `operad.optim.parameter`.

Covers round-trip read/write against a `FakeLeaf`-style agent, sub-
indexed list paths (`rules[i]`, `examples[i]`), constraint validation,
null-gradient semantics, `zero_grad`, weakref lifecycle, `state()` /
`load_state()` identity, and JSON round-trip through the discriminated
constraint union.
"""

from __future__ import annotations

import gc

import pytest

from operad.core.example import Example
from operad.optim import (
    CategoricalParameter,
    ExampleListParameter,
    FloatParameter,
    ListConstraint,
    NumericConstraint,
    Parameter,
    RuleListParameter,
    TextConstraint,
    TextParameter,
    TextualGradient,
    VocabConstraint,
)
from tests._helpers.fake_leaf import A, B, FakeLeaf


# ---------------------------------------------------------------------------
# Parameter round-trip read/write
# ---------------------------------------------------------------------------


def test_text_parameter_round_trip(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.role = "initial role"

    p = TextParameter.from_agent(leaf, "role", "role")
    assert p.value == "initial role"

    p.write("new role")
    assert leaf.role == "new role"
    assert p.read() == "new role"


def test_text_parameter_task_field(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B, task="original")

    p = TextParameter.from_agent(leaf, "task", "task")
    assert p.value == "original"

    p.write("updated")
    assert leaf.task == "updated"


def test_rule_list_round_trip(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.rules = ["r0", "r1"]

    p = RuleListParameter.from_agent(leaf, "rules", "rules")
    assert p.value == ["r0", "r1"]

    p.write(["a", "b", "c"])
    assert leaf.rules == ["a", "b", "c"]
    assert p.read() == ["a", "b", "c"]


def test_example_list_round_trip(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.examples = [Example(input=A(text="hi"), output=B(value=1))]

    p = ExampleListParameter.from_agent(leaf, "examples", "examples")
    assert len(p.value) == 1
    assert p.value[0].input.text == "hi"

    new = [
        Example(input=A(text="x"), output=B(value=2)),
        Example(input=A(text="y"), output=B(value=3)),
    ]
    p.write(new)
    assert leaf.examples == new


def test_float_parameter_config_path(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)

    p = FloatParameter.from_agent(
        leaf, "config.sampling.temperature", "temperature"
    )
    assert p.value == cfg.sampling.temperature

    p.write(0.42)
    assert leaf.config.sampling.temperature == 0.42


def test_categorical_parameter_backend(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)

    p = CategoricalParameter.from_agent(leaf, "config.backend", "backend")
    assert p.value == "llamacpp"

    p.write("ollama")
    assert leaf.config.backend == "ollama"


# ---------------------------------------------------------------------------
# Sub-indexed list paths
# ---------------------------------------------------------------------------


def test_rule_i_sub_indexed(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.rules = ["r0", "r1", "r2"]

    p = TextParameter.from_agent(leaf, "rules[1]", "rule_i")
    assert p.value == "r1"

    p.write("R1")
    assert leaf.rules == ["r0", "R1", "r2"]
    assert p.read() == "R1"


def test_example_i_sub_indexed(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.examples = [
        Example(input=A(text="a"), output=B(value=1)),
        Example(input=A(text="b"), output=B(value=2)),
    ]

    p = Parameter.from_agent(leaf, "examples[0]", "example_i")
    assert p.value.input.text == "a"

    replacement = Example(input=A(text="z"), output=B(value=99))
    p.write(replacement)
    assert leaf.examples[0] is replacement


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------


def test_numeric_constraint_clips_above_max():
    c = NumericConstraint(min=0.0, max=1.0)
    assert c.validate(1.5) == 1.0


def test_numeric_constraint_clips_below_min():
    c = NumericConstraint(min=0.0, max=1.0)
    assert c.validate(-0.5) == 0.0


def test_numeric_constraint_passthrough_in_range():
    c = NumericConstraint(min=0.0, max=1.0)
    assert c.validate(0.5) == 0.5


def test_vocab_constraint_rejects_unknown():
    c = VocabConstraint(allowed=["a", "b"])
    with pytest.raises(ValueError, match="not in vocab"):
        c.validate("c")


def test_vocab_constraint_accepts_known():
    c = VocabConstraint(allowed=["a", "b"])
    assert c.validate("a") == "a"


def test_text_constraint_truncates():
    c = TextConstraint(max_length=5)
    assert c.validate("abcdefgh") == "abcde"


def test_text_constraint_forbidden_raises():
    c = TextConstraint(forbidden=["bad"])
    with pytest.raises(ValueError, match="forbidden substring"):
        c.validate("this is bad text")


def test_list_constraint_truncates():
    c = ListConstraint(max_count=2)
    assert c.validate([1, 2, 3]) == [1, 2]


def test_list_constraint_applies_item_constraint():
    c = ListConstraint(item=NumericConstraint(min=0.0, max=1.0))
    assert c.validate([0.5, 2.0, -1.0]) == [0.5, 1.0, 0.0]


# ---------------------------------------------------------------------------
# TextualGradient
# ---------------------------------------------------------------------------


def test_null_gradient_has_zero_severity():
    g = TextualGradient.null_gradient()
    assert g.severity == 0.0
    assert g.message == ""


def test_textual_gradient_defaults():
    g = TextualGradient(message="fix this")
    assert g.severity == 1.0
    assert g.by_field == {}
    assert g.target_paths == []


# ---------------------------------------------------------------------------
# Parameter lifecycle
# ---------------------------------------------------------------------------


def test_zero_grad_clears_grad(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    p = TextParameter.from_agent(leaf, "role", "role")

    p.grad = TextualGradient(message="hmm", severity=0.7)
    assert p.grad is not None

    p.zero_grad()
    assert p.grad is None


def test_weakref_does_not_pin_agent(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.role = "temp"

    p = TextParameter.from_agent(leaf, "role", "role")
    assert p.read() == "temp"

    del leaf
    gc.collect()

    with pytest.raises(RuntimeError, match="dead agent"):
        p.read()


def test_unattached_parameter_raises_on_read():
    p = TextParameter(path="role", kind="role", value="x")
    with pytest.raises(RuntimeError, match="no attached agent"):
        p.read()


def test_state_identity_cycle(cfg):
    leaf1 = FakeLeaf(config=cfg, input=A, output=B)
    leaf1.role = "original"

    p = TextParameter.from_agent(leaf1, "role", "role")
    p.write("rewritten")
    state = leaf1.state()

    leaf2 = FakeLeaf(config=cfg, input=A, output=B)
    leaf2.load_state(state)

    p2 = TextParameter.from_agent(leaf2, "role", "role")
    assert p2.value == "rewritten"


# ---------------------------------------------------------------------------
# Discriminated-union serialization
# ---------------------------------------------------------------------------


def test_discriminated_union_round_trip(cfg):
    leaf = FakeLeaf(config=cfg, input=A, output=B)

    p = FloatParameter.from_agent(
        leaf,
        "config.sampling.temperature",
        "temperature",
        constraint=NumericConstraint(min=0.0, max=2.0),
    )

    dumped = p.model_dump()
    assert dumped["constraint"]["kind"] == "numeric"

    reloaded = FloatParameter.model_validate(dumped)
    assert isinstance(reloaded.constraint, NumericConstraint)
    assert reloaded.constraint.max == 2.0


def test_constraint_variants_discriminate():
    variants = [
        TextConstraint(max_length=10),
        NumericConstraint(min=0.0, max=1.0),
        VocabConstraint(allowed=["a", "b"]),
        ListConstraint(max_count=3),
    ]
    for c in variants:
        dumped = c.model_dump()
        assert dumped["kind"] == c.kind
