"""Tests for `operad.cli` — in-process invocation via `main([...])`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from operad import cli  # noqa: E402


def _write_yaml(tmp_path: Path, agent: str = "operad.agents.reasoning.react.ReAct") -> Path:
    data = {
        "agent": agent,
        "config": {
            "backend": "llamacpp",
            "host": "127.0.0.1:0",
            "model": "test-model",
            "sampling": {"temperature": 0.0},
        },
    }
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_trace_prints_mermaid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = _write_yaml(tmp_path)
    rc = cli.main(["trace", str(config)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "flowchart" in out
    assert "ReAct" in out or "reasoner" in out


def test_graph_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = _write_yaml(tmp_path)
    rc = cli.main(["graph", str(config), "--format", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert "nodes" in data and "edges" in data
    assert len(data["nodes"]) >= 1


def test_graph_mermaid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = _write_yaml(tmp_path)
    rc = cli.main(["graph", str(config), "--format", "mermaid"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "flowchart" in out


def test_missing_config_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(["trace", str(tmp_path / "nope.yaml")])
    captured = capsys.readouterr()
    assert rc == 2
    assert "operad:" in captured.err
    assert "not found" in captured.err


def test_run_with_dummy_agent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _write_yaml(tmp_path, agent="_helpers.cli_fixtures.DummyAgent")
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"text": "hello"}))

    rc = cli.main(["run", str(config), "--input", str(input_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out) == {"echoed": "hello"}


def test_run_bad_input_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _write_yaml(tmp_path, agent="_helpers.cli_fixtures.DummyAgent")
    input_path = tmp_path / "input.json"
    input_path.write_text("{not valid json")

    rc = cli.main(["run", str(config), "--input", str(input_path)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "invalid JSON" in err


def test_run_input_schema_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _write_yaml(tmp_path, agent="_helpers.cli_fixtures.DummyAgent")
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"wrong_field": 42, "text": [1, 2]}))

    rc = cli.main(["run", str(config), "--input", str(input_path)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "does not match" in err
