from __future__ import annotations

"""Tests for the apps-uthereal run command.

Owner: 4-1-cli-run-show-feedback.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from apps_uthereal.commands import run as cmd_run
from apps_uthereal.schemas.workflow import ArtemisFinalAnswer, ArtemisInput
from apps_uthereal.workflow.trace import TraceFrame, WorkflowTrace


class FakeRunner:
    """Runner test double that returns a deterministic answer and trace."""

    def __init__(self, *, selfserve_root: Path, retrieval: Any) -> None:
        self.selfserve_root = selfserve_root
        self.retrieval = retrieval

    async def abuild(self) -> "FakeRunner":
        return self

    async def run_with_trace(
        self,
        x: ArtemisInput,
    ) -> tuple[ArtemisFinalAnswer, WorkflowTrace]:
        frame = TraceFrame(
            step_name="reasoner",
            agent_class="FakeLeaf",
            leaf_role="role",
            leaf_task="task",
            input={"text": x.entry.user_message},
            output={"text": "answer"},
            hash_prompt="prompt",
            hash_input="input",
            hash_output_schema="schema",
            run_id=x.entry.entry_id or "",
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            finished_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        trace = WorkflowTrace(
            entry_id=x.entry.entry_id or "",
            frames=[frame],
            final_answer_text="fake answer",
            intent_decision="DIRECT_ANSWER",
        ).seal()
        return ArtemisFinalAnswer(utterance="fake answer"), trace


@pytest.fixture
def entry_path(tmp_path: Path) -> Path:
    path = tmp_path / "entry.json"
    path.write_text(
        json.dumps(
            {
                "workspace_id": "workspace-1",
                "user_message": "hello",
                "workspace": {
                    "workspace_id": "workspace-1",
                    "rules": [{"id": "rule-1"}],
                    "tags": ["alpha"],
                },
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def selfserve_root(tmp_path: Path) -> Path:
    path = tmp_path / "selfserve"
    path.mkdir()
    return path


@pytest.mark.asyncio
async def test_run_creates_run_dir_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry_path: Path,
    selfserve_root: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cmd_run, "ArtemisRunner", FakeRunner)

    rc = await cmd_run.run(_args(entry_path, selfserve_root))

    assert rc == 0
    run_dirs = list((tmp_path / ".uthereal-runs").iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "entry.json").exists()
    assert (run_dir / "trace.jsonl").exists()
    assert (run_dir / "answer.txt").read_text(encoding="utf-8") == "fake answer\n"
    assert (run_dir / "cassettes" / "llm").is_dir()
    assert (run_dir / "cassettes" / "rag").is_dir()


@pytest.mark.asyncio
async def test_run_replay_produces_same_trace_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry_path: Path,
    selfserve_root: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cmd_run, "ArtemisRunner", FakeRunner)

    first = await cmd_run.run(_args(entry_path, selfserve_root))
    trace_path = next((tmp_path / ".uthereal-runs").glob("*/trace.jsonl"))
    first_trace = WorkflowTrace.from_jsonl(trace_path)

    second = await cmd_run.run(
        _args(entry_path, selfserve_root, cassette_mode="replay")
    )
    second_trace = WorkflowTrace.from_jsonl(trace_path)

    assert first == 0
    assert second == 0
    assert first_trace.trace_id == second_trace.trace_id


@pytest.mark.asyncio
async def test_run_returns_2_on_missing_entry(tmp_path: Path) -> None:
    rc = await cmd_run.run(
        _args(tmp_path / "missing.json", tmp_path, cassette_mode="replay")
    )

    assert rc == 2


def _args(
    entry: Path,
    selfserve_root: Path,
    *,
    cassette_mode: str = "record-missing",
) -> argparse.Namespace:
    return argparse.Namespace(
        entry=entry,
        selfserve_root=selfserve_root,
        rag_base_url=None,
        cassette_mode=cassette_mode,
    )
