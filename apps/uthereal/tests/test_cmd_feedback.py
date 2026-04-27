from __future__ import annotations

"""Tests for the apps-uthereal feedback command.

Owner: 4-1-cli-run-show-feedback.
"""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apps_uthereal.commands import feedback as cmd_feedback
from apps_uthereal.workflow.trace import TraceFrame, WorkflowTrace


@pytest.mark.asyncio
async def test_feedback_writes_template_no_editor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    trace = _write_trace(tmp_path)

    rc = await cmd_feedback.run(
        argparse.Namespace(trace_id=trace.trace_id, no_editor=True)
    )

    feedback_path = tmp_path / ".uthereal-runs" / trace.entry_id / "feedback.json"
    text = feedback_path.read_text(encoding="utf-8")
    assert rc == 0
    assert text.startswith("# trace_id: filled in for you")


@pytest.mark.asyncio
async def test_feedback_template_has_all_required_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    trace = _write_trace(tmp_path)

    rc = await cmd_feedback.run(
        argparse.Namespace(trace_id=trace.trace_id, no_editor=True)
    )

    feedback_path = tmp_path / ".uthereal-runs" / trace.entry_id / "feedback.json"
    data = json.loads(_strip_comments(feedback_path))
    assert rc == 0
    assert data == {
        "desired_behavior": None,
        "final_answer_critique": "",
        "severity": 1.0,
        "target_path": None,
        "trace_id": trace.trace_id,
    }


@pytest.mark.asyncio
async def test_feedback_validates_after_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    trace = _write_trace(tmp_path)

    def write_valid(cmd: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        Path(cmd[1]).write_text(
            json.dumps(
                {
                    "trace_id": trace.trace_id,
                    "final_answer_critique": "The answer used the wrong tone.",
                    "target_path": "reasoner",
                    "severity": 0.5,
                    "desired_behavior": "Answer more directly.",
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setenv("EDITOR", "test-editor")
    monkeypatch.setattr(cmd_feedback.subprocess, "run", write_valid)

    rc = await cmd_feedback.run(
        argparse.Namespace(trace_id=trace.trace_id, no_editor=False)
    )

    feedback_path = tmp_path / ".uthereal-runs" / trace.entry_id / "feedback.json"
    data = json.loads(feedback_path.read_text(encoding="utf-8"))
    assert rc == 0
    assert data["final_answer_critique"] == "The answer used the wrong tone."
    assert data["target_path"] == "reasoner"

    feedback_path.write_text(
        json.dumps(
            {
                "trace_id": trace.trace_id,
                "final_answer_critique": "Bad target.",
                "target_path": "unknown_leaf",
                "severity": 1.0,
                "desired_behavior": None,
            }
        ),
        encoding="utf-8",
    )
    invalid_rc = await cmd_feedback.run(
        argparse.Namespace(trace_id=trace.trace_id, no_editor=True)
    )

    assert invalid_rc == 2


def _write_trace(tmp_path: Path) -> WorkflowTrace:
    trace = WorkflowTrace(
        entry_id="entry-123",
        frames=[_frame("reasoner")],
        final_answer_text="final answer",
        intent_decision="DIRECT_ANSWER",
    ).seal()
    run_dir = tmp_path / ".uthereal-runs" / trace.entry_id
    trace.to_jsonl(run_dir / "trace.jsonl")
    (run_dir / "answer.txt").write_text("final answer\n", encoding="utf-8")
    return trace


def _frame(step_name: str) -> TraceFrame:
    return TraceFrame(
        step_name=step_name,
        agent_class="FakeLeaf",
        leaf_role="role",
        leaf_task="task",
        input={"text": "hello"},
        output={"text": "answer"},
        hash_prompt="prompt",
        hash_input="input",
        hash_output_schema="schema",
        run_id="entry-123",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _strip_comments(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    return "\n".join(lines)
