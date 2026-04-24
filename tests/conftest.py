"""Shared pytest fixtures and helpers for the operad test suite.

Helpers (``FakeLeaf``, ``BrokenOutputLeaf``, shared schemas,
``assert_no_network``) live in :mod:`tests._helpers.fake_leaf`; this
module re-exports them for backward compatibility and wires the
``cfg`` / ``cassette`` fixtures.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest

from operad import Configuration
from operad.core.config import Sampling

from ._helpers.fake_leaf import (  # noqa: F401
    A,
    B,
    BrokenOutputLeaf,
    C,
    D,
    FakeLeaf,
    assert_no_network,
)


@pytest.fixture
def cfg() -> Configuration:
    """A default, offline-safe Configuration for tests.

    Points at a llama.cpp-shaped endpoint but is never actually contacted
    because every test-only agent overrides `forward` (see `FakeLeaf`).
    """
    return Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        sampling=Sampling(temperature=0.0, max_tokens=16),
    )


@pytest.fixture
def cassette(request: pytest.FixtureRequest) -> Iterator[None]:
    """Record/replay LLM calls for this test via a JSONL cassette.

    Default mode is ``replay`` (missing keys raise ``CassetteMiss``).
    Set ``OPERAD_CASSETTE=record`` against a real backend to refresh the
    file at ``<testfile_dir>/cassettes/<test_name>.jsonl``.
    """
    from operad.utils.cassette import cassette_context

    mode = os.environ.get("OPERAD_CASSETTE", "replay")
    if mode not in ("record", "replay"):
        raise ValueError(
            f"OPERAD_CASSETTE must be 'record' or 'replay', got {mode!r}"
        )
    path = (
        Path(request.fspath).parent / "cassettes" / f"{request.node.name}.jsonl"
    )
    with cassette_context(path, mode=mode):  # type: ignore[arg-type]
        yield
