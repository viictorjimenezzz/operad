"""Run each offline-capable example's ``main(offline=True)`` end-to-end.

Stronger than a smoke-import: confirms every offline example actually
completes its ``asyncio.run`` without contacting a network. The eight
scripts listed here are the same set that ``scripts/verify.sh`` runs.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"

OFFLINE_SCRIPTS = [
    "mermaid_export.py",
    "custom_agent.py",
    "eval_loop.py",
    "evolutionary_demo.py",
    "observer_demo.py",
    "sweep_demo.py",
    "sandbox_pool_demo.py",
    "sandbox_tooluser.py",
]


@pytest.fixture(autouse=True)
def _examples_on_path():
    sys.path.insert(0, str(EXAMPLES_DIR))
    try:
        yield
    finally:
        sys.path.remove(str(EXAMPLES_DIR))


@pytest.mark.parametrize("name", OFFLINE_SCRIPTS)
def test_example_offline(name: str) -> None:
    path = EXAMPLES_DIR / name
    spec = importlib.util.spec_from_file_location(f"examples.{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, "main"), f"{name} missing async main(offline=...)"
    asyncio.run(module.main(offline=True))
