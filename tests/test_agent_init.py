"""Tests for the class-attribute `Agent.__init__` path.

Component-style instantiation (`Leaf(config=cfg)`) reads class-level
defaults. Constructor kwargs override them.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from operad import Agent, BuildError, Configuration, Example

from .conftest import A, B


def test_class_attrs_supply_defaults(cfg: Configuration) -> None:
    class Leaf(Agent):
        input = A
        output = B
        role = "persona"
        task = "objective"
        rules = ("r1", "r2")

    leaf = Leaf(config=cfg)
    assert leaf.role == "persona"
    assert leaf.task == "objective"
    assert leaf.rules == ["r1", "r2"]
    assert leaf.input is A
    assert leaf.output is B
    assert leaf.config is cfg


def test_explicit_kwargs_override_class_attrs(cfg: Configuration) -> None:
    class Leaf(Agent):
        input = A
        output = B
        role = "default"
        task = "default"
        rules = ("default",)

    leaf = Leaf(
        config=cfg,
        role="custom",
        task="custom-task",
        rules=["custom-rule"],
    )
    assert leaf.role == "custom"
    assert leaf.task == "custom-task"
    assert leaf.rules == ["custom-rule"]


def test_kwarg_input_output_override_class_attrs(cfg: Configuration) -> None:
    class Leaf(Agent):
        input = A
        output = A  # wrong on purpose; kwarg overrides

    leaf = Leaf(config=cfg, output=B)
    assert leaf.input is A
    assert leaf.output is B


def test_missing_input_output_raises_prompt_incomplete(cfg: Configuration) -> None:
    class Leaf(Agent):
        pass  # no input/output class attrs

    with pytest.raises(BuildError) as exc:
        Leaf(config=cfg)
    assert exc.value.reason == "prompt_incomplete"


def test_class_attrs_dont_leak_between_subclasses(cfg: Configuration) -> None:
    class LeafOne(Agent):
        input = A
        output = B
        role = "one"

    class LeafTwo(Agent):
        input = A
        output = B
        role = "two"

    assert LeafOne(config=cfg).role == "one"
    assert LeafTwo(config=cfg).role == "two"


def test_rules_tuple_is_copied_into_list(cfg: Configuration) -> None:
    class Leaf(Agent):
        input = A
        output = B
        rules = ("r1",)

    leaf = Leaf(config=cfg)
    assert leaf.rules == ["r1"]
    leaf.rules.append("r2")  # per-instance mutation must not leak to class
    assert Leaf.rules == ("r1",)


def test_examples_accepts_typed_pairs(cfg: Configuration) -> None:
    class Leaf(Agent):
        input = A
        output = B

    ex = Example[A, B](input=A(text="q"), output=B(value=1))
    leaf = Leaf(config=cfg, examples=[ex])
    assert len(leaf.examples) == 1
    assert leaf.examples[0].input.text == "q"


def test_example_roundtrips_typed_pair() -> None:
    e: Example[A, B] = Example[A, B](input=A(text="hi"), output=B(value=42))
    assert isinstance(e.input, A)
    assert isinstance(e.output, B)
    assert e.model_dump() == {"input": {"text": "hi"}, "output": {"value": 42}}


def test_example_rejects_non_basemodel_values() -> None:
    with pytest.raises(ValidationError):
        Example[A, B](input=42, output=B(value=1))  # type: ignore[arg-type]


def test_missing_config_for_default_leaf_fails_build(cfg: Configuration) -> None:
    """Default-forward leaves must have a config; build catches it."""
    import asyncio

    class Leaf(Agent):
        input = A
        output = B

    async def go() -> None:
        leaf = Leaf(config=None)
        await leaf.abuild()

    with pytest.raises(BuildError) as exc:
        asyncio.run(go())
    assert exc.value.reason == "prompt_incomplete"
