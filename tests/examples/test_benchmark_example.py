"""Offline smoke test for `python -m examples.benchmark.run`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from operad.benchmark import BenchmarkReport


def test_benchmark_example_offline_smoke(
    tmp_path: Path,
) -> None:
    out = tmp_path / "report.json"
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "examples.benchmark.run",
            "--offline",
            "--max-examples",
            "5",
            "--seeds",
            "0",
            "--out",
            str(out),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ERROR" not in result.stdout
    assert "ERROR" not in result.stderr
    assert out.is_file()

    parsed = BenchmarkReport.model_validate(json.loads(out.read_text()))
    assert {row.task for row in parsed.summary} == {
        "classification",
        "summarization",
        "tool_use",
    }
    assert len(parsed.cells) == 12
