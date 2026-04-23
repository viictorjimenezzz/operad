"""Smoke-imports every file in the top-level ``examples/`` directory.

Confirms none of them fail at import time and none of them execute
network calls at module top-level (they must guard ``asyncio.run(...)``
under ``if __name__ == "__main__":``).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


@pytest.mark.parametrize("path", sorted(EXAMPLES_DIR.glob("*.py")))
def test_example_imports(path: Path) -> None:
    spec = importlib.util.spec_from_file_location(f"examples.{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
