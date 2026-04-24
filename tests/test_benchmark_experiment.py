"""Tests for `operad.benchmark.Experiment`."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from operad import Agent, Configuration
from operad.core.config import Sampling
from operad.benchmark import Dataset, Entry, Experiment
from operad.metrics import ExactMatch
from operad.utils.ops import AppendRule

from .conftest import A, FakeLeaf


# A concrete leaf with class-level input/output so Experiment.load() can
# resolve its I/O types. Defined at module level so the cross-interpreter
# subprocess test can re-import it via `tests.test_benchmark_experiment`.
class RoundTripLeaf(Agent[A, A]):
    input = A
    output = A
    role = "round-trip leaf"
    task = "echo the canned response"

    async def forward(self, x: A) -> A:
        return A(text="hello")


def _build_fake(cfg: Configuration, *, canned: str = "hello") -> FakeLeaf:
    agent = FakeLeaf(config=cfg, input=A, output=A, canned={"text": canned})
    agent.build()
    return agent


async def _abuild_fake(cfg: Configuration, *, canned: str = "hello") -> FakeLeaf:
    agent = FakeLeaf(config=cfg, input=A, output=A, canned={"text": canned})
    await agent.abuild()
    return agent


async def _abuild_round_trip(cfg: Configuration) -> "RoundTripLeaf":
    agent = RoundTripLeaf(config=cfg)
    await agent.abuild()
    return agent


def _dataset(n: int = 3) -> Dataset[A, A]:
    entries = [
        Entry(input=A(text=f"q{i}"), expected_output=A(text="hello"))
        for i in range(n)
    ]
    return Dataset(entries, name="ds", version="v1")


# --- 1. experiment_id stable ------------------------------------------------


def test_experiment_id_stable(cfg: Configuration) -> None:
    a1 = _build_fake(cfg)
    a2 = _build_fake(cfg)
    ds = _dataset()
    exp1 = Experiment(agent=a1, dataset=ds, metrics=[ExactMatch()], name="n")
    exp2 = Experiment(agent=a2, dataset=ds, metrics=[ExactMatch()], name="n")
    assert exp1.experiment_id == exp2.experiment_id


# --- 2. experiment_id sensitive --------------------------------------------


def test_experiment_id_sensitive_to_agent_mutation(cfg: Configuration) -> None:
    agent = _build_fake(cfg)
    ds = _dataset()
    exp = Experiment(agent=agent, dataset=ds, metrics=[ExactMatch()])
    before = exp.experiment_id
    AppendRule(path="", rule="new rule").apply(agent)
    assert exp.experiment_id != before


def test_experiment_id_sensitive_to_dataset_mutation(cfg: Configuration) -> None:
    agent = _build_fake(cfg)
    ds_a = _dataset(n=3)
    ds_b = Dataset(
        [
            Entry(input=A(text="different"), expected_output=A(text="hello")),
            Entry(input=A(text="q1"), expected_output=A(text="hello")),
            Entry(input=A(text="q2"), expected_output=A(text="hello")),
        ],
        name="ds",
        version="v1",
    )
    a = Experiment(agent=agent, dataset=ds_a, metrics=[ExactMatch()])
    b = Experiment(agent=agent, dataset=ds_b, metrics=[ExactMatch()])
    assert a.experiment_id != b.experiment_id


# --- 3. run() captures traces ----------------------------------------------


@pytest.mark.asyncio
async def test_run_captures_one_trace_per_entry(cfg: Configuration) -> None:
    agent = await _abuild_fake(cfg)
    ds = _dataset(n=3)
    exp = Experiment(agent=agent, dataset=ds, metrics=[ExactMatch()])
    report = await exp.run()
    assert len(exp.traces) == 3
    run_ids = [t.run_id for t in exp.traces]
    assert len(set(run_ids)) == 3
    assert exp.report is report
    assert report.summary.get("exact_match") == pytest.approx(1.0)


# --- 4. save() layout -------------------------------------------------------


@pytest.mark.asyncio
async def test_save_writes_expected_layout(
    cfg: Configuration, tmp_path: Path
) -> None:
    agent = await _abuild_fake(cfg)
    ds = _dataset(n=3)
    exp = Experiment(agent=agent, dataset=ds, metrics=[ExactMatch()])
    await exp.run()
    folder = tmp_path / "exp"
    out = exp.save(folder)
    assert out == folder
    for name in (
        "manifest.json",
        "graph.json",
        "state.json",
        "dataset.ndjson",
        "report.json",
    ):
        assert (folder / name).is_file(), f"missing {name}"
    traces_dir = folder / "traces"
    assert traces_dir.is_dir()
    trace_files = sorted(traces_dir.glob("*.json"))
    assert len(trace_files) == 3


# --- 5. round-trip ----------------------------------------------------------


@pytest.mark.asyncio
async def test_round_trip(cfg: Configuration, tmp_path: Path) -> None:
    agent = await _abuild_round_trip(cfg)
    ds = _dataset(n=3)
    exp = Experiment(
        agent=agent, dataset=ds, metrics=[ExactMatch()], name="rt"
    )
    report = await exp.run()

    folder = tmp_path / "rt"
    exp.save(folder)
    loaded = Experiment.load(folder)

    assert loaded.agent.hash_content == agent.hash_content
    assert loaded.dataset.hash_dataset == ds.hash_dataset
    assert loaded.report is not None
    assert loaded.report.summary == report.summary
    assert len(loaded.traces) == 3
    assert loaded.metrics == []
    assert loaded.name == "rt"


# --- 6. api_key scrubbed ----------------------------------------------------


@pytest.mark.asyncio
async def test_api_key_scrubbed(tmp_path: Path) -> None:
    secret = "secret-xyz"
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        sampling=Sampling(temperature=0.0, max_tokens=16),
        api_key=secret,
    )
    agent = RoundTripLeaf(config=cfg)
    await agent.abuild()
    ds = _dataset(n=2)
    exp = Experiment(agent=agent, dataset=ds, metrics=[ExactMatch()])
    await exp.run()
    folder = tmp_path / "s"
    exp.save(folder)
    for p in folder.rglob("*"):
        if p.is_file():
            assert secret not in p.read_text(encoding="utf-8"), (
                f"api_key leaked into {p}"
            )


# --- 7. load skips metrics --------------------------------------------------


@pytest.mark.asyncio
async def test_load_skips_metrics(cfg: Configuration, tmp_path: Path) -> None:
    agent = await _abuild_round_trip(cfg)
    ds = _dataset(n=2)
    exp = Experiment(
        agent=agent, dataset=ds, metrics=[ExactMatch()], name="m"
    )
    await exp.run()
    folder = tmp_path / "m"
    exp.save(folder)

    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["metrics"] == ["exact_match"]

    loaded = Experiment.load(folder)
    assert loaded.metrics == []


# --- cross-interpreter round-trip (acceptance) ------------------------------


@pytest.mark.asyncio
async def test_cross_interpreter_round_trip(
    cfg: Configuration, tmp_path: Path
) -> None:
    agent = await _abuild_round_trip(cfg)
    expected_hash = agent.hash_content

    ds = _dataset(n=2)
    exp = Experiment(agent=agent, dataset=ds, metrics=[ExactMatch()], name="x")
    await exp.run()
    folder = tmp_path / "x"
    exp.save(folder)

    repo_root = Path(__file__).resolve().parent.parent
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(repo_root)!r})
        # Import the test module so `RoundTripLeaf`'s qualified class name
        # resolves in this fresh interpreter.
        import tests.test_benchmark_experiment  # noqa: F401
        from operad.benchmark import Experiment

        loaded = Experiment.load({str(folder)!r})
        print(loaded.agent.hash_content)
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"subprocess failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.stdout.strip() == expected_hash
