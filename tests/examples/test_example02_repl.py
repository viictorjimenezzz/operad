"""Tests for the interactive path of examples/02_algorithm.py."""

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


def _load_example02_module():
    path = EXAMPLES_DIR / "02_algorithm.py"
    spec = importlib.util.spec_from_file_location("examples.02_algorithm", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_example02_repl_quit_path(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_example02_module()

    cfg = Configuration(backend="llamacpp", host="127.0.0.1:0", model="test")
    monkeypatch.setattr(module, "local_config", lambda **kwargs: cfg)
    monkeypatch.setattr(module, "server_reachable", lambda host: True)
    monkeypatch.setattr(module, "print_scenario_tree", lambda tree: None)
    monkeypatch.setattr(module, "print_talker_turn", lambda turn: None)
    monkeypatch.setattr(module, "print_talker_summary", lambda transcript: None)
    monkeypatch.setattr(module, "print_panel", lambda title, body: None)
    monkeypatch.setattr(module, "print_rule", lambda title: None)

    class _DummyComponent:
        input = type("DummyInput", (), {})
        output = type("DummyOutput", (), {})

    class _FakeTalkerReasoner:
        def __init__(self, tree, max_turns, config):
            _ = (tree, config)
            self.max_turns = max_turns
            self._current_id = "greet"
            self._history = []
            self.reasoner = _DummyComponent()
            self.talker = _DummyComponent()
            self.finished = False

        async def abuild(self):
            return self

        async def step(self, message):
            _ = message
            raise AssertionError("step() should not be called when first input is quit")

    monkeypatch.setattr(module, "TalkerReasoner", _FakeTalkerReasoner)
    monkeypatch.setattr("builtins.input", lambda prompt="": "quit")

    args = argparse.Namespace(
        scripted=False,
        max_turns=10,
        offline=False,
        dashboard=None,
        no_open=False,
    )

    await module.main(args)
