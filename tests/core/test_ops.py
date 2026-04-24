"""Tests for the mutation op starter set in `operad.utils.ops`."""

from __future__ import annotations

import pytest

from operad import Agent, Example
from operad.utils.ops import (
    AppendExample,
    AppendRule,
    CompoundOp,
    DropExample,
    DropRule,
    EditTask,
    ReplaceRule,
    SetBackend,
    SetModel,
    SetTemperature,
    TweakRole,
)

from ..conftest import A, B, FakeLeaf


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
    assert a.leaf.config.sampling.temperature == 0.9


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


# ---------------------------------------------------------------------------
# Op.undo() round-trip tests
# ---------------------------------------------------------------------------


def _undo_roundtrip(agent, op) -> None:
    before = agent.leaf.state()
    op.apply(agent)
    after_apply = agent.leaf.state()
    assert after_apply != before, f"{type(op).__name__}.apply did not change state"
    op.undo(agent)
    assert agent.leaf.state() == before, (
        f"{type(op).__name__}.undo did not restore state"
    )


def test_append_rule_undo(cfg) -> None:
    _undo_roundtrip(_Composite(cfg), AppendRule(path="leaf", rule="l2"))


def test_replace_rule_undo(cfg) -> None:
    _undo_roundtrip(_Composite(cfg), ReplaceRule(path="leaf", index=0, rule="new"))


def test_drop_rule_undo(cfg) -> None:
    _undo_roundtrip(_Composite(cfg), DropRule(path="leaf", index=0))


def test_edit_task_undo(cfg) -> None:
    _undo_roundtrip(_Composite(cfg), EditTask(path="leaf", task="new-task"))


def test_tweak_role_undo(cfg) -> None:
    _undo_roundtrip(_Composite(cfg), TweakRole(path="leaf", role="new-role"))


def test_drop_example_undo(cfg) -> None:
    _undo_roundtrip(_Composite(cfg), DropExample(path="leaf", index=0))


def test_append_example_undo(cfg) -> None:
    ex = Example(input=A(text="q"), output=B(value=2))
    _undo_roundtrip(_Composite(cfg), AppendExample(path="leaf", example=ex))


def test_set_temperature_undo(cfg) -> None:
    _undo_roundtrip(_Composite(cfg), SetTemperature(path="leaf", temperature=0.9))


def test_set_model_undo(cfg) -> None:
    _undo_roundtrip(_Composite(cfg), SetModel(path="leaf", model="gpt-99"))


def test_set_backend_undo(cfg) -> None:
    _undo_roundtrip(
        _Composite(cfg),
        SetBackend(path="leaf", backend="ollama", host="127.0.0.1:0"),
    )


def test_compound_op_undo_reverses_all(cfg) -> None:
    a = _Composite(cfg)
    before = a.leaf.state()
    op = CompoundOp(
        ops=[
            AppendRule(path="leaf", rule="x"),
            EditTask(path="leaf", task="done"),
        ]
    )
    op.apply(a)
    assert a.leaf.rules == ["l0", "l1", "x"]
    assert a.leaf.task == "done"
    op.undo(a)
    assert a.leaf.state() == before


def test_undo_before_apply_raises(cfg) -> None:
    a = _Composite(cfg)
    for op in [
        AppendRule(path="leaf", rule="x"),
        ReplaceRule(path="leaf", index=0, rule="x"),
        DropRule(path="leaf", index=0),
        EditTask(path="leaf", task="x"),
        TweakRole(path="leaf", role="x"),
        DropExample(path="leaf", index=0),
        AppendExample(
            path="leaf", example=Example(input=A(text="q"), output=B(value=2))
        ),
        SetTemperature(path="leaf", temperature=0.1),
        SetModel(path="leaf", model="m"),
        SetBackend(path="leaf", backend="ollama"),
        CompoundOp(ops=[AppendRule(path="leaf", rule="y")]),
    ]:
        with pytest.raises(RuntimeError, match="undo"):
            op.undo(a)
