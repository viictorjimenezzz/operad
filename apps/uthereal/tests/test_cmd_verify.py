from __future__ import annotations

"""Tests for ``apps-uthereal verify``.

Owner: 5-1-verify-and-demo.
"""

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from apps_uthereal.cli import main
from apps_uthereal.commands import verify as cmd_verify
from apps_uthereal.schemas.workflow import (
    ArtemisFinalAnswer,
    DatasetEntry,
    WorkspaceMetadata,
)
from apps_uthereal.workflow.trace import TraceFrame, WorkflowTrace


def test_cmd_verify_writes_verify_json_with_all_keys(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir, before_trace = _make_run(tmp_path)

    after_trace = _make_trace(
        entry_id=before_trace.entry_id,
        utterance="Of course. Here is what I can help with:\n* Item one.\n* Item two.",
    )

    after_answer = ArtemisFinalAnswer(
        utterance=after_trace.final_answer_text,
        intent_decision=after_trace.intent_decision,
        final_step="conv_talker",
    )
    selfserve_root = tmp_path / "selfserve"
    selfserve_root.mkdir()
    _patch_runner(monkeypatch, after_answer, after_trace)
    _patch_cassette(monkeypatch)

    rc = main(
        [
            "verify",
            "--trace-id",
            before_trace.trace_id[:8],
            "--selfserve-root",
            str(selfserve_root),
        ]
    )

    assert rc == 0, capsys.readouterr().err
    payload = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    expected_keys = {
        "trace_id_before",
        "trace_id_after",
        "before_answer",
        "after_answer",
        "before_intent",
        "after_intent",
        "before_final_step",
        "after_final_step",
        "target_path",
        "leaf_output_diff",
        "rerecorded_steps",
    }
    assert expected_keys <= set(payload.keys())
    assert payload["trace_id_before"] == before_trace.trace_id
    assert payload["trace_id_after"] == after_trace.trace_id
    assert payload["target_path"] == "conv_talker"
    assert payload["before_answer"] == before_trace.final_answer_text
    assert payload["after_answer"] == after_trace.final_answer_text


def test_cmd_verify_when_unchanged_yaml_reports_no_rerecord(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir, before_trace = _make_run(tmp_path)

    after_trace = before_trace
    after_answer = ArtemisFinalAnswer(
        utterance=before_trace.final_answer_text,
        intent_decision=before_trace.intent_decision,
        final_step="conv_talker",
    )
    selfserve_root = tmp_path / "selfserve"
    selfserve_root.mkdir()
    _patch_runner(monkeypatch, after_answer, after_trace, leave_cassette_unchanged=True)
    _patch_cassette(monkeypatch)

    rc = main(
        [
            "verify",
            "--trace-id",
            before_trace.trace_id[:8],
            "--selfserve-root",
            str(selfserve_root),
        ]
    )

    assert rc == 0
    payload = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert payload["rerecorded_steps"] == []


def test_cmd_verify_missing_fix_json_returns_2(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    _run_dir, trace = _make_run(tmp_path, with_fix=False)

    rc = main(
        [
            "verify",
            "--trace-id",
            trace.trace_id,
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "fix.json missing" in captured.err


def _make_run(
    tmp_path: Path,
    *,
    with_fix: bool = True,
) -> tuple[Path, WorkflowTrace]:
    trace = _make_trace(
        entry_id="entry-1",
        utterance="Hello! I can help with safety procedures and routine maintenance.",
    )
    run_dir = tmp_path / ".uthereal-runs" / trace.entry_id
    trace.to_jsonl(run_dir / "trace.jsonl")
    (run_dir / "answer.txt").write_text(
        trace.final_answer_text + "\n", encoding="utf-8"
    )
    entry = DatasetEntry(
        entry_id=trace.entry_id,
        workspace_id="workspace-1",
        user_message="Hi! What can you help me with?",
    )
    (run_dir / "entry.json").write_text(
        json.dumps(entry.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if with_fix:
        (run_dir / "fix.json").write_text(
            json.dumps(
                {
                    "target_path": "conv_talker",
                    "yaml_path": "reasoner/agents/agent_conversational_talker.yaml",
                    "yaml_dry_run": False,
                    "diff_text": "",
                    "severity": 0.7,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    return run_dir, trace


def _make_trace(*, entry_id: str, utterance: str) -> WorkflowTrace:
    return WorkflowTrace(
        entry_id=entry_id,
        frames=[
            TraceFrame(
                step_name="conv_talker",
                agent_class="ConversationalTalkerLeaf",
                leaf_role="ConversationalTalker role",
                leaf_task="ConversationalTalker task",
                input={"message": "Hi"},
                output={"text": utterance},
            ),
        ],
        final_answer_text=utterance,
        intent_decision="DIRECT_ANSWER",
    ).seal()


def _patch_runner(
    monkeypatch: Any,
    answer: ArtemisFinalAnswer,
    trace: WorkflowTrace,
    *,
    leave_cassette_unchanged: bool = False,
) -> None:
    class FakeRunner:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        async def abuild(self) -> "FakeRunner":
            return self

        async def run_with_trace(
            self, _input: Any
        ) -> tuple[ArtemisFinalAnswer, WorkflowTrace]:
            if not leave_cassette_unchanged:
                cassette = _CASSETTE_PATH.path
                if cassette is not None:
                    cassette.parent.mkdir(parents=True, exist_ok=True)
                    new_keys = [
                        json.dumps(
                            {
                                "key": f"key-{frame.step_name}",
                                "hash_prompt": f"key-{frame.step_name}",
                                "hash_input": frame.hash_input,
                                "response_json": "{}",
                            },
                            sort_keys=True,
                        )
                        for frame in trace.frames
                    ]
                    cassette.write_text("\n".join(new_keys) + "\n", encoding="utf-8")
            return answer, trace

    monkeypatch.setattr(cmd_verify, "ArtemisRunner", FakeRunner)


class _CassettePathHolder:
    path: Path | None = None


_CASSETTE_PATH = _CassettePathHolder()


def _patch_cassette(monkeypatch: Any) -> None:
    @contextmanager
    def fake_cassette(path: Path, mode: str):
        _CASSETTE_PATH.path = path
        try:
            yield
        finally:
            _CASSETTE_PATH.path = None

    @contextmanager
    def fake_env(*_args: Any, **_kwargs: Any):
        yield

    monkeypatch.setattr(cmd_verify, "cassette_context", fake_cassette)
    monkeypatch.setattr(cmd_verify, "_cassette_env", fake_env)


def test_cmd_verify_unknown_trace_id_returns_2(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    runs = tmp_path / ".uthereal-runs"
    runs.mkdir()

    rc = main(["verify", "--trace-id", "nonexistent"])

    captured = capsys.readouterr()
    assert rc == 2
    assert "No run found" in captured.err
