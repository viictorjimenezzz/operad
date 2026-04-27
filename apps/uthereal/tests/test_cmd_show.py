from __future__ import annotations

"""Tests for the apps-uthereal show command.

Owner: 4-1-cli-run-show-feedback.
"""

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apps_uthereal.commands import show as cmd_show
from apps_uthereal.workflow.trace import TraceFrame, WorkflowTrace


@pytest.mark.asyncio
async def test_show_prints_all_frames_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    trace = _write_trace(tmp_path)

    rc = await cmd_show.run(argparse.Namespace(trace_id=trace.trace_id, frame=None))

    captured = capsys.readouterr()
    assert rc == 0
    assert f"trace_id: {trace.trace_id}" in captured.out
    assert "[context_safeguard]" in captured.out
    assert "[reasoner]" in captured.out


@pytest.mark.asyncio
async def test_show_filters_by_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    trace = _write_trace(tmp_path)

    rc = await cmd_show.run(
        argparse.Namespace(trace_id=trace.trace_id, frame="reasoner")
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert "[reasoner]" in captured.out
    assert "[context_safeguard]" not in captured.out


@pytest.mark.asyncio
async def test_show_resolves_short_trace_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    trace = _write_trace(tmp_path)

    rc = await cmd_show.run(argparse.Namespace(trace_id=trace.trace_id[:8], frame=None))

    captured = capsys.readouterr()
    assert rc == 0
    assert f"entry_id: {trace.entry_id}" in captured.out


@pytest.mark.asyncio
async def test_show_deterministic_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    trace = _write_trace(tmp_path)
    args = argparse.Namespace(trace_id=trace.trace_id, frame=None)

    assert await cmd_show.run(args) == 0
    first = capsys.readouterr().out
    assert await cmd_show.run(args) == 0
    second = capsys.readouterr().out

    assert first == second


def _write_trace(tmp_path: Path) -> WorkflowTrace:
    trace = WorkflowTrace(
        entry_id="entry-123",
        frames=[
            _frame("context_safeguard", output={"continue_field": "yes"}),
            _frame("reasoner", output={"route": "DIRECT_ANSWER"}),
        ],
        final_answer_text="final answer",
        intent_decision="DIRECT_ANSWER",
    ).seal()
    run_dir = tmp_path / ".uthereal-runs" / trace.entry_id
    trace.to_jsonl(run_dir / "trace.jsonl")
    return trace


def _frame(step_name: str, *, output: dict[str, str]) -> TraceFrame:
    return TraceFrame(
        step_name=step_name,
        agent_class="FakeLeaf",
        leaf_role="role",
        leaf_task="task",
        input={"text": "hello"},
        output=output,
        latency_ms=1.25,
        hash_prompt=f"prompt-{step_name}",
        hash_input=f"input-{step_name}",
        hash_output_schema="schema",
        run_id="entry-123",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
