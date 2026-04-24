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


def test_example_not_in_agent_module() -> None:
    from operad.core import agent as agent_mod
    from operad.core import example as example_mod

    assert "Example" not in vars(agent_mod) or vars(agent_mod)["Example"] is example_mod.Example
    assert example_mod.Example is operad.Example
