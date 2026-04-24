"""Tests for `operad.tracing.watch`, `OPERAD_TRACE`, and `operad tail`."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from operad.runtime.observers import base as _obs

from tests.conftest import A, B, FakeLeaf


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_trace.jsonl"


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    _obs.registry.clear()
    yield
    _obs.registry.clear()


async def test_watch_registers_and_tears_down(cfg, tmp_path) -> None:
    import operad.tracing as tracing

    pre = len(_obs.registry)
    jsonl = tmp_path / "run.jsonl"
    with tracing.watch(jsonl=jsonl, rich=False):
        assert len(_obs.registry) == pre + 1
        leaf = await FakeLeaf(
            config=cfg, input=A, output=B, canned={"value": 7}
        ).abuild()
        await leaf(A(text="hi"))

    assert len(_obs.registry) == pre
    assert jsonl.exists()
    lines = [ln for ln in jsonl.read_text().splitlines() if ln.strip()]
    assert len(lines) >= 2
    kinds = [json.loads(ln)["kind"] for ln in lines]
    assert "start" in kinds and "end" in kinds


async def test_watch_missing_rich_degrades(cfg, monkeypatch) -> None:
    import operad.tracing as tracing
    import operad.runtime.observers as obs_pkg

    # `watch()` does `from .runtime.observers import RichDashboardObserver`,
    # a statement-level import that doesn't route through
    # `importlib.import_module`. Simulate the missing extra by deleting
    # the attribute from the already-imported package namespace — the
    # from-import then raises ImportError as it would when `rich` is
    # absent.
    monkeypatch.delattr(obs_pkg, "RichDashboardObserver", raising=False)

    pre = len(_obs.registry)
    with pytest.warns(UserWarning, match="rich"):
        with tracing.watch(jsonl=None, rich=True):
            assert len(_obs.registry) == pre  # nothing attached
    assert len(_obs.registry) == pre


class _BrokenRichModule:
    def __getattr__(self, name: str) -> Any:
        raise ImportError("simulated missing rich extra")


async def test_operad_trace_env_var_auto_attach(cfg, tmp_path, monkeypatch) -> None:
    """Importing operad.tracing with OPERAD_TRACE set writes NDJSON on invoke."""
    import operad.tracing as tracing

    jsonl = tmp_path / "auto.jsonl"
    monkeypatch.setenv("OPERAD_TRACE", str(jsonl))

    importlib.reload(tracing)
    try:
        leaf = await FakeLeaf(
            config=cfg, input=A, output=B, canned={"value": 3}
        ).abuild()
        await leaf(A(text="go"))
    finally:
        _obs.registry.clear()

    assert jsonl.exists()
    lines = [ln for ln in jsonl.read_text().splitlines() if ln.strip()]
    records = [json.loads(ln) for ln in lines]
    kinds = {r["kind"] for r in records}
    assert {"start", "end"} <= kinds


def test_cli_tail_prints_events(capsys) -> None:
    from operad.cli import main

    rc = main(["tail", str(FIXTURE), "--speed", "0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Pipeline" in out
    assert "start" in out and "end" in out
    # One line per event in the fixture.
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 4
