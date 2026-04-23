"""Tests for `operad.utils.ops`."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from operad import Agent, Configuration, Example
from operad.utils.ops import (
    AppendExample,
    AppendRule,
    CompoundOp,
    DropExample,
    DropRule,
    EditTask,
    Op,
    ReplaceRule,
    SetBackend,
    SetModel,
    SetTemperature,
    TweakRole,
)

from .conftest import A, B, FakeLeaf


class _Composite(Agent[A, B]):
    input = A
    output = B

    def __init__(self) -> None:
        super().__init__(config=None)

    async def forward(self, x: A) -> B:  # type: ignore[override]
        raise NotImplementedError


def _leaf(cfg: Configuration, *, rules: tuple[str, ...] = ()) -> FakeLeaf:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.rules = list(rules)
    return leaf


# --- rules ------------------------------------------------------------------


def test_append_rule_on_leaf(cfg: Configuration) -> None:
    leaf = _leaf(cfg, rules=("r1",))
    AppendRule(path="", rule="r2").apply(leaf)
    assert list(leaf.rules) == ["r1", "r2"]


def test_append_rule_is_not_a_set(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    AppendRule(path="", rule="r").apply(leaf)
    AppendRule(path="", rule="r").apply(leaf)
    assert list(leaf.rules) == ["r", "r"]


def test_append_rule_on_child(cfg: Configuration) -> None:
    composite = _Composite()
    composite.reasoner = _leaf(cfg, rules=("a",))
    AppendRule(path="reasoner", rule="b").apply(composite)
    assert list(composite.reasoner.rules) == ["a", "b"]


def test_replace_rule(cfg: Configuration) -> None:
    leaf = _leaf(cfg, rules=("a", "b", "c"))
    ReplaceRule(path="", index=1, rule="B").apply(leaf)
    assert list(leaf.rules) == ["a", "B", "c"]


def test_replace_rule_out_of_range(cfg: Configuration) -> None:
    leaf = _leaf(cfg, rules=("a",))
    with pytest.raises(IndexError, match="replace_rule index 5"):
        ReplaceRule(path="", index=5, rule="x").apply(leaf)


def test_drop_rule(cfg: Configuration) -> None:
    leaf = _leaf(cfg, rules=("a", "b", "c"))
    DropRule(path="", index=0).apply(leaf)
    assert list(leaf.rules) == ["b", "c"]


def test_drop_rule_out_of_range(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    with pytest.raises(IndexError, match="drop_rule index 0"):
        DropRule(path="", index=0).apply(leaf)


# --- task / role ------------------------------------------------------------


def test_edit_task(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.task = "old"
    EditTask(path="", task="new").apply(leaf)
    assert leaf.task == "new"


def test_tweak_role(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.role = "old"
    TweakRole(path="", role="new").apply(leaf)
    assert leaf.role == "new"


# --- examples ---------------------------------------------------------------


def test_append_example(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    ex = Example(input=A(text="hi"), output=B(value=1))
    AppendExample(path="", example=ex).apply(leaf)
    assert list(leaf.examples) == [ex]


def test_drop_example(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    ex1 = Example(input=A(text="1"), output=B(value=1))
    ex2 = Example(input=A(text="2"), output=B(value=2))
    leaf.examples = [ex1, ex2]
    DropExample(path="", index=0).apply(leaf)
    assert list(leaf.examples) == [ex2]


def test_drop_example_out_of_range(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    with pytest.raises(IndexError, match="drop_example index 0"):
        DropExample(path="", index=0).apply(leaf)


# --- config -----------------------------------------------------------------


def test_set_temperature_on_leaf(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    SetTemperature(path="", temperature=0.1).apply(leaf)
    assert leaf.config is not None
    assert leaf.config.temperature == 0.1
    # other knobs unchanged
    assert leaf.config.backend == cfg.backend
    assert leaf.config.model == cfg.model
    assert leaf.config.host == cfg.host
    assert leaf.config.max_tokens == cfg.max_tokens


def test_set_temperature_on_composite_raises() -> None:
    composite = _Composite()
    with pytest.raises(ValueError, match="set_temperature"):
        SetTemperature(path="", temperature=0.1).apply(composite)


def test_set_model(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    SetModel(path="", model="other").apply(leaf)
    assert leaf.config is not None
    assert leaf.config.model == "other"


def test_set_backend_to_remote_drops_host(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    SetBackend(path="", backend="openai", host=None).apply(leaf)
    assert leaf.config is not None
    assert leaf.config.backend == "openai"
    assert leaf.config.host is None


def test_set_backend_local_requires_host(cfg: Configuration) -> None:
    remote_cfg = Configuration(backend="openai", model="gpt")
    leaf = FakeLeaf(config=remote_cfg, input=A, output=B)
    with pytest.raises(ValidationError):
        SetBackend(path="", backend="llamacpp", host=None).apply(leaf)


def test_set_temperature_leaves_unrelated_fields_untouched(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.role = "R"
    leaf.task = "T"
    leaf.rules = ["x"]
    before = leaf.state()
    SetTemperature(path="", temperature=0.123).apply(leaf)
    after = leaf.state()
    assert before.role == after.role
    assert before.task == after.task
    assert list(before.rules) == list(after.rules)
    assert after.config is not None and after.config.temperature == 0.123


# --- compound ---------------------------------------------------------------


def test_compound_applies_in_order(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    compound = CompoundOp(
        ops=[
            AppendRule(path="", rule="r1"),
            AppendRule(path="", rule="r2"),
            EditTask(path="", task="T"),
        ]
    )
    compound.apply(leaf)
    assert list(leaf.rules) == ["r1", "r2"]
    assert leaf.task == "T"


# --- protocol & names -------------------------------------------------------


@pytest.mark.parametrize(
    "op,expected",
    [
        (AppendRule(path="", rule="r"), "append_rule"),
        (ReplaceRule(path="", index=0, rule="r"), "replace_rule"),
        (DropRule(path="", index=0), "drop_rule"),
        (EditTask(path="", task="t"), "edit_task"),
        (TweakRole(path="", role="r"), "tweak_role"),
        (DropExample(path="", index=0), "drop_example"),
        (SetTemperature(path="", temperature=0.0), "set_temperature"),
        (SetModel(path="", model="m"), "set_model"),
        (SetBackend(path="", backend="openai"), "set_backend"),
        (CompoundOp(ops=[]), "compound"),
    ],
)
def test_op_names_are_stable(op: Any, expected: str) -> None:
    assert op.name == expected
    assert isinstance(op, Op)
