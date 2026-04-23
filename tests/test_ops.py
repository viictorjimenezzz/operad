"""Tests for the mutation op starter set in `operad.utils.ops`."""

from __future__ import annotations

import pytest

from operad import (
    Agent,
    AppendExample,
    AppendRule,
    CompoundOp,
    DropExample,
    DropRule,
    EditTask,
    Example,
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

    def __init__(self, cfg) -> None:
        super().__init__(config=None, input=A, output=B, rules=("r0",))
        self.leaf = FakeLeaf(
            config=cfg,
            input=A,
            output=B,
            task="t",
        )
        self.leaf.rules = ["l0", "l1"]
        self.leaf.role = "orig-role"
        self.leaf.examples = [
            Example(input=A(text="in"), output=B(value=1)),
        ]

    async def forward(self, x: A) -> B:  # type: ignore[override]
        return await self.leaf(x)


def test_append_rule_appends(cfg) -> None:
    a = _Composite(cfg)
    AppendRule(path="leaf", rule="l2").apply(a)
    assert a.leaf.rules == ["l0", "l1", "l2"]


def test_replace_rule_replaces(cfg) -> None:
    a = _Composite(cfg)
    ReplaceRule(path="leaf", index=0, rule="new").apply(a)
    assert a.leaf.rules == ["new", "l1"]


def test_replace_rule_out_of_range_raises(cfg) -> None:
    a = _Composite(cfg)
    with pytest.raises(ValueError, match="out of range"):
        ReplaceRule(path="leaf", index=99, rule="x").apply(a)


def test_drop_rule_drops(cfg) -> None:
    a = _Composite(cfg)
    DropRule(path="leaf", index=0).apply(a)
    assert a.leaf.rules == ["l1"]


def test_edit_task_sets_task(cfg) -> None:
    a = _Composite(cfg)
    EditTask(path="leaf", task="new-task").apply(a)
    assert a.leaf.task == "new-task"


def test_tweak_role_sets_role(cfg) -> None:
    a = _Composite(cfg)
    TweakRole(path="leaf", role="new-role").apply(a)
    assert a.leaf.role == "new-role"


def test_drop_example(cfg) -> None:
    a = _Composite(cfg)
    DropExample(path="leaf", index=0).apply(a)
    assert a.leaf.examples == []


def test_append_example(cfg) -> None:
    a = _Composite(cfg)
    ex = Example(input=A(text="q"), output=B(value=2))
    AppendExample(path="leaf", example=ex).apply(a)
    assert len(a.leaf.examples) == 2


def test_append_example_rejects_non_example(cfg) -> None:
    a = _Composite(cfg)
    with pytest.raises(ValueError, match="must be an Example"):
        AppendExample(path="leaf", example="not an example").apply(a)


def test_set_temperature_updates_config(cfg) -> None:
    a = _Composite(cfg)
    SetTemperature(path="leaf", temperature=0.9).apply(a)
    assert a.leaf.config.temperature == 0.9


def test_set_temperature_on_composite_raises(cfg) -> None:
    a = _Composite(cfg)
    with pytest.raises(ValueError, match="no config"):
        SetTemperature(path="", temperature=0.5).apply(a)


def test_set_model_updates_config(cfg) -> None:
    a = _Composite(cfg)
    SetModel(path="leaf", model="gpt-99").apply(a)
    assert a.leaf.config.model == "gpt-99"


def test_set_backend_updates_config(cfg) -> None:
    a = _Composite(cfg)
    SetBackend(path="leaf", backend="ollama", host="127.0.0.1:0").apply(a)
    assert a.leaf.config.backend == "ollama"
    assert a.leaf.config.host == "127.0.0.1:0"


def test_compound_op_applies_in_order(cfg) -> None:
    a = _Composite(cfg)
    CompoundOp(
        ops=[
            AppendRule(path="leaf", rule="x"),
            EditTask(path="leaf", task="done"),
        ]
    ).apply(a)
    assert a.leaf.rules == ["l0", "l1", "x"]
    assert a.leaf.task == "done"


def test_op_missing_path_raises_build_error(cfg) -> None:
    from operad import BuildError

    a = _Composite(cfg)
    with pytest.raises(BuildError):
        AppendRule(path="nope", rule="r").apply(a)
