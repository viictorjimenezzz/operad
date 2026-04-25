"""Run each offline-capable example's ``main`` end-to-end.

Stronger than a smoke-import: confirms every offline example actually
completes its ``asyncio.run`` without contacting a network. The four
scripts listed here are the same set that ``scripts/verify.sh`` runs.

Each example exposes ``_parse_args`` (constructs the example's
``argparse.Namespace``) and ``main(args)``. We construct args via the
parser and override ``offline=True`` so the call shape matches what
``verify.sh`` does on the command line.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"

OFFLINE_SCRIPTS = [
    "01_composition_research_analyst.py",
    "02_talker_reasoner_intake.py",
    "03_train_config_temperature.py",
    "04_evolutionary_best_of_n.py",
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
    assert hasattr(module, "main"), f"{name} missing async main(args)"
    assert hasattr(module, "_parse_args"), f"{name} missing _parse_args"

    # Construct the example's args via its own parser, then force --offline.
    sys.argv = [name, "--offline"]
    args = module._parse_args()
    asyncio.run(module.main(args))
