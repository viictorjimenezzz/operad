"""Targeted tests for hosted-backend behavior in examples/03_training.py."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

from operad import Configuration


EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


@pytest.fixture(autouse=True)
def _examples_on_path():
    sys.path.insert(0, str(EXAMPLES_DIR))
    try:
        yield
    finally:
        sys.path.remove(str(EXAMPLES_DIR))


def _load_example03_module():
    path = EXAMPLES_DIR / "03_training.py"
    spec = importlib.util.spec_from_file_location("examples.03_training", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_example03_gemini_skips_local_server_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_example03_module()

    cfg = Configuration(backend="gemini", model="gemini-1.5-pro", api_key="x")
    monkeypatch.setattr(module, "local_config", lambda **kwargs: cfg)

    def _fail_if_called(host: str) -> bool:
        _ = host
        raise AssertionError("server_reachable() should not be called for gemini")

    monkeypatch.setattr(module, "server_reachable", _fail_if_called)

    class _StopAfterServerGate(Exception):
        pass

    def _stop_after_gate(*args, **kwargs):
        _ = (args, kwargs)
        raise _StopAfterServerGate()

    monkeypatch.setattr(module, "set_limit", _stop_after_gate)

    args = argparse.Namespace(
        offline=False,
        dashboard=None,
        no_open=False,
        epochs=1,
        candidates=1,
    )

    with pytest.raises(_StopAfterServerGate):
        await module.main(args)
