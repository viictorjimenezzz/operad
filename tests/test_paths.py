"""Tests for `operad.utils.paths.resolve`."""

from __future__ import annotations

from typing import Any

import pytest

from operad import Agent, Configuration
from operad.utils.paths import resolve

from .conftest import A, B, FakeLeaf


class _Composite(Agent[A, B]):
    input = A
    output = B

    def __init__(self) -> None:
        super().__init__(config=None)

    async def forward(self, x: A) -> B:  # type: ignore[override]
        raise NotImplementedError


def _leaf(cfg: Configuration) -> FakeLeaf:
    return FakeLeaf(config=cfg, input=A, output=B)


def test_resolve_empty_returns_root(cfg: Configuration) -> None:
    root = _leaf(cfg)
    assert resolve(root, "") is root
    assert resolve(root, "self") is root


def test_resolve_single_child(cfg: Configuration) -> None:
    composite = _Composite()
    composite.reasoner = _leaf(cfg)
    assert resolve(composite, "reasoner") is composite.reasoner


def test_resolve_nested(cfg: Configuration) -> None:
    outer = _Composite()
    inner = _Composite()
    leaf = _leaf(cfg)
    inner.reasoner = leaf
    outer.inner = inner
    assert resolve(outer, "inner.reasoner") is leaf


def test_resolve_unknown_segment_raises(cfg: Configuration) -> None:
    composite = _Composite()
    composite.reasoner = _leaf(cfg)
    with pytest.raises(KeyError) as exc:
        resolve(composite, "missing")
    msg = str(exc.value)
    assert "missing" in msg
    assert "reasoner" in msg


def test_resolve_unknown_nested_segment_reports_full_path(cfg: Configuration) -> None:
    outer = _Composite()
    outer.inner = _Composite()
    with pytest.raises(KeyError) as exc:
        resolve(outer, "inner.nope")
    msg = str(exc.value)
    assert "inner.nope" in msg
    assert "nope" in msg


def test_resolve_shared_child_under_multiple_names(cfg: Configuration) -> None:
    composite = _Composite()
    shared = _leaf(cfg)
    composite.a = shared
    composite.b = shared
    assert resolve(composite, "a") is shared
    assert resolve(composite, "b") is shared
