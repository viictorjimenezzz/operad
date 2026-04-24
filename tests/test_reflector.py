"""Tests for ``Reflector``: default-forward leaf with canned stub."""

from __future__ import annotations

from typing import Any

import pytest

from operad import Agent
from operad.agents import Reflection, ReflectionInput, Reflector


pytestmark = pytest.mark.asyncio


class _StubReflector(Reflector):
    """Skip the real model call by overriding forward with canned output."""

    def __init__(self, *, canned: Reflection) -> None:
        super().__init__(config=None, input=ReflectionInput, output=Reflection)
        self._canned = canned

    async def forward(self, x: Any) -> Any:
        return self._canned


async def test_reflector_class_level_defaults_are_preserved() -> None:
    canned = Reflection(needs_revision=False, deficiencies=[], suggested_revision="")
    r = _StubReflector(canned=canned)
    assert r.role == Reflector.role
    assert r.task == Reflector.task
    assert tuple(r.rules) == tuple(Reflector.rules)
    assert len(r.examples) == 1


async def test_reflector_stub_produces_typed_reflection() -> None:
    canned = Reflection(
        needs_revision=True,
        deficiencies=["off-by-one"],
        suggested_revision="Use < instead of <=.",
    )
    r = await _StubReflector(canned=canned).abuild()
    out = await r(ReflectionInput(original_request="q", candidate_answer="a"))
    assert isinstance(out.response, Reflection)
    assert out.response.needs_revision is True
    assert out.response.deficiencies == ["off-by-one"]


async def test_reflector_is_registered_as_a_leaf_agent() -> None:
    r = _StubReflector(canned=Reflection(needs_revision=False))
    assert isinstance(r, Agent)
    assert not r._children
