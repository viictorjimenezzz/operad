"""Tests for Agent.__init__ side-effect elimination (stream 2-3).

Covers:
- Config identity preserved after construction (no model_copy in __init__)
- default_sampling priority: explicit user value > default > backend default
- freeze/thaw round-trip after deferred merge
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from pydantic import BaseModel

from operad import Agent, Configuration
from operad.core.config import Sampling
from operad.agents.reasoning.components.classifier import Classifier

from ..conftest import A, B, FakeLeaf


class _FakeWithDefault(FakeLeaf):
    """FakeLeaf subclass with a non-trivial default_sampling for offline tests."""
    default_sampling: ClassVar[dict] = {"temperature": 0.33}


def _cfg(**sampling_overrides: Any) -> Configuration:
    if sampling_overrides:
        return Configuration(
            backend="llamacpp", host="127.0.0.1:0", model="test",
            sampling=Sampling(**sampling_overrides),
        )
    return Configuration(backend="llamacpp", host="127.0.0.1:0", model="test")


# --- identity preservation ---------------------------------------------------

def test_identity_preserved_after_construction() -> None:
    cfg = _cfg()
    leaf = Classifier(config=cfg, input=A, output=B)
    assert leaf.config is cfg


def test_identity_preserved_when_default_sampling_would_fill() -> None:
    cfg = _cfg()
    leaf = Classifier(config=cfg, input=A, output=B)
    # Classifier has default_sampling; __init__ must not copy the config
    assert leaf.config is cfg


def test_identity_preserved_with_explicit_sampling() -> None:
    cfg = _cfg(temperature=0.5)
    leaf = Classifier(config=cfg, input=A, output=B)
    assert leaf.config is cfg


# --- _apply_default_sampling priority ----------------------------------------

def test_default_fills_unset_after_apply() -> None:
    cfg = _cfg()
    leaf = Classifier(config=cfg, input=A, output=B)
    leaf._apply_default_sampling()
    assert leaf.config.sampling.temperature == 0.0
    assert leaf.config.sampling.max_tokens == 128


def test_user_value_wins_temperature() -> None:
    cfg = _cfg(temperature=0.9)
    leaf = Classifier(config=cfg, input=A, output=B)
    leaf._apply_default_sampling()
    assert leaf.config.sampling.temperature == 0.9
    assert leaf.config.sampling.max_tokens == 128


def test_user_value_wins_max_tokens() -> None:
    cfg = _cfg(max_tokens=999)
    leaf = Classifier(config=cfg, input=A, output=B)
    leaf._apply_default_sampling()
    assert leaf.config.sampling.temperature == 0.0
    assert leaf.config.sampling.max_tokens == 999


def test_empty_default_sampling_leaves_config_unchanged() -> None:
    cfg = _cfg(temperature=0.5)
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    assert Agent.default_sampling == {}
    leaf._apply_default_sampling()
    assert leaf.config is cfg  # no copy made


def test_config_none_skips_apply() -> None:
    class Composite(Agent[A, B]):  # type: ignore[type-arg]
        input = A
        output = B

    node = Composite()
    node._apply_default_sampling()  # must not raise
    assert node.config is None


# --- tree walker -------------------------------------------------------------

class _FakeWithTemp11(FakeLeaf):
    default_sampling: ClassVar[dict] = {"temperature": 0.11}


def test_tree_applies_to_all_leaves() -> None:
    cfg_a = _cfg()
    cfg_b = _cfg()
    leaf_a = _FakeWithTemp11(config=cfg_a, input=A, output=B)
    leaf_b = _FakeWithTemp11(config=cfg_b, input=A, output=B)

    class Root(Agent[A, B]):  # type: ignore[type-arg]
        input = A
        output = B

    root = Root()
    root.a = leaf_a  # type: ignore[attr-defined]
    root.b = leaf_b  # type: ignore[attr-defined]

    root._apply_default_sampling_tree()
    assert leaf_a.config.sampling.temperature == 0.11
    assert leaf_b.config.sampling.temperature == 0.11


# --- freeze / thaw round-trip ------------------------------------------------

async def test_freeze_thaw_preserves_merged_sampling(tmp_path) -> None:
    leaf = _FakeWithDefault(config=_cfg(), input=A, output=B)
    built = await leaf.abuild()

    path = tmp_path / "leaf.json"
    built.freeze(str(path))

    restored = _FakeWithDefault.thaw(str(path))
    assert restored.config is not None
    assert restored.config.sampling.temperature == 0.33
