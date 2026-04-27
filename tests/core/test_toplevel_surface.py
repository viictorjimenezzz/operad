"""Guards for the stratified top-level surface (Wave 1-1).

The ``operad.testing`` package was merged into ``operad.utils`` and
removed; the top-level ``operad`` module re-exports only ~20 foundational
names. Everything else lives in its subpackage and must be imported from
there.
"""

from __future__ import annotations

import importlib

import pytest

import operad


def test_testing_namespace_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("operad.testing")


def test_all_is_trim() -> None:
    assert len(operad.__all__) <= 20


def test_moved_names_still_reachable() -> None:
    from operad.agents.reasoning import Reasoner  # noqa: F401
    from operad.algorithms import Beam  # noqa: F401
    from operad.core.models import resolve_model  # noqa: F401
    from operad.utils.ops import AppendExample  # noqa: F401
    from operad.utils.cassette import CassetteMiss  # noqa: F401
    from operad.utils.hashing import hash_config  # noqa: F401


def test_example_lives_in_agent_module() -> None:
    from operad.core import agent as agent_mod

    assert agent_mod.Example is operad.Example


def test_removed_core_modules_are_gone() -> None:
    for name in (
        "operad.core.example",
        "operad.core.fields",
        "operad.core.graph",
        "operad.core._strands_runner",
        "operad.core.render.markdown",
        "operad.core.render.xml",
        "operad.core.render.chat",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)
