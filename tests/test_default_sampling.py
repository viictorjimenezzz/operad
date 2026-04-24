"""Tests for `Agent.default_sampling` class attribute + `__init__` merge.

A leaf declares an opinionated sampling default (e.g. ``Classifier`` →
``temperature=0.0``). At construction, those defaults fill in only
fields the caller did NOT set explicitly on their `Configuration`;
user-explicit values always win.
"""

from __future__ import annotations

from typing import Any

from operad import Agent, Configuration
from operad.core.config import Sampling
from operad.agents.reasoning.components.classifier import Classifier
from operad.agents.reasoning.components.critic import Critic
from operad.agents.reasoning.components.reasoner import Reasoner
from operad.agents.reasoning.components.router import Router

from .conftest import A, B, FakeLeaf


def _bare_cfg(**sampling_overrides: Any) -> Configuration:
    """A Configuration with no sampling fields set unless overridden."""
    if sampling_overrides:
        return Configuration(
            backend="openai",
            model="gpt-4o-mini",
            sampling=Sampling(**sampling_overrides),
        )
    return Configuration(backend="openai", model="gpt-4o-mini")


def test_default_sampling_fills_unset_fields() -> None:
    leaf = Classifier(config=_bare_cfg(), input=A, output=B)
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.0
    assert leaf.config.sampling.max_tokens == 128


def test_user_value_wins_over_default() -> None:
    leaf = Classifier(
        config=_bare_cfg(temperature=0.9), input=A, output=B
    )
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.9
    assert leaf.config.sampling.max_tokens == 128


def test_user_max_tokens_wins_over_default() -> None:
    leaf = Classifier(
        config=_bare_cfg(max_tokens=999), input=A, output=B
    )
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.0
    assert leaf.config.sampling.max_tokens == 999


def test_config_none_is_passthrough() -> None:
    class Composite(Agent):
        input = A
        output = B

    node = Composite()
    assert node.config is None


def test_base_agent_has_empty_default_sampling() -> None:
    assert Agent.default_sampling == {}


def test_fakeleaf_inherits_empty_default_sampling() -> None:
    cfg = _bare_cfg(temperature=0.42, max_tokens=7)
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.42
    assert leaf.config.sampling.max_tokens == 7


def test_callers_config_is_not_mutated_in_place() -> None:
    cfg = _bare_cfg()
    original_temp = cfg.sampling.temperature
    original_max = cfg.sampling.max_tokens
    leaf = Classifier(config=cfg, input=A, output=B)
    assert cfg.sampling.temperature == original_temp
    assert cfg.sampling.max_tokens == original_max
    assert leaf.config is not cfg


def test_reasoner_default_temperature() -> None:
    leaf = Reasoner(config=_bare_cfg(), input=A, output=B)
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.7


def test_critic_defaults() -> None:
    leaf = Critic(config=_bare_cfg())
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.0
    assert leaf.config.sampling.max_tokens == 512


def test_router_defaults() -> None:
    leaf = Router(config=_bare_cfg())
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.0
    assert leaf.config.sampling.max_tokens == 64
