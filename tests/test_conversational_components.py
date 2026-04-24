"""Tests for the leaf agents under `operad.agents.conversational.components`."""

from __future__ import annotations

import pytest

from operad.agents import (
    Persona,
    Safeguard,
    SafeguardVerdict,
    StyledUtterance,
    TurnChoice,
    TurnTaker,
    Utterance,
)


LEAF_SPECS = [
    (Safeguard, Utterance, SafeguardVerdict),
    (TurnTaker, Utterance, TurnChoice),
    (Persona, Utterance, StyledUtterance),
]


@pytest.mark.parametrize("cls,in_cls,out_cls", LEAF_SPECS)
def test_leaf_contract_is_fixed(cfg, cls, in_cls, out_cls) -> None:
    leaf = cls(config=cfg)
    assert leaf.input is in_cls
    assert leaf.output is out_cls


@pytest.mark.parametrize("cls,_,__", LEAF_SPECS)
def test_leaf_defaults_are_populated(cfg, cls, _, __) -> None:
    leaf = cls(config=cfg)
    assert leaf.role, f"{cls.__name__}.role is empty"
    assert leaf.task, f"{cls.__name__}.task is empty"
    assert leaf.rules, f"{cls.__name__}.rules is empty"
    assert leaf.examples, f"{cls.__name__}.examples is empty"


@pytest.mark.parametrize("cls,_,__", LEAF_SPECS)
def test_leaf_task_override_wins(cfg, cls, _, __) -> None:
    leaf = cls(config=cfg, task="custom-task")
    assert leaf.task == "custom-task"


def test_persona_role_is_generic(cfg) -> None:
    """Users subclass (or override) for specific voices; ship a neutral default."""
    leaf = Persona(config=cfg)
    assert "helpful" in leaf.role.lower()


def test_safeguard_example_is_allow(cfg) -> None:
    leaf = Safeguard(config=cfg)
    example = leaf.examples[0]
    assert isinstance(example.input, Utterance)
    assert isinstance(example.output, SafeguardVerdict)
    assert example.output.label == "allow"
