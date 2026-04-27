from __future__ import annotations

"""Owner: 4-3-cli-blame."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from operad import Agent
from pydantic import BaseModel

from apps_uthereal.cli import main
from apps_uthereal.commands import blame as cmd_blame
from apps_uthereal.feedback.blamer import KNOWN_LEAF_PATHS, BlamerInput, BlamerOutput
from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.workflow.trace import TraceFrame, WorkflowTrace


class DummyInput(BaseModel):
    """Minimal input for leaf-directory placeholders."""

    text: str = ""


class DummyOutput(BaseModel):
    """Minimal output for leaf-directory placeholders."""

    text: str = ""


class DummyLeaf(Agent[DummyInput, DummyOutput]):
    """Leaf placeholder used only for role/task metadata."""

    input = DummyInput
    output = DummyOutput


def test_cmd_blame_writes_blame_json_no_confirm(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir, trace = _make_run(tmp_path)
    expected = BlamerOutput(
        target_path="reasoner",
        rationale="The route is wrong.",
        leaf_targeted_critique="Route greetings to direct answer.",
        severity=0.8,
    )
    fake_blamer = _patch_blamer(monkeypatch, expected)
    cassette_calls: list[tuple[Path, str]] = []
    _patch_cassette(monkeypatch, cassette_calls)
    monkeypatch.setattr(cmd_blame, "load_all_leaves", _leaf_directory)

    rc = main(
        [
            "blame",
            "--trace-id",
            trace.trace_id[:8],
            "--selfserve-root",
            str(tmp_path),
            "--no-confirm",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert "Final answer:" in captured.out
    assert "Hello with a retrieval preamble." in captured.out
    actual = BlamerOutput.model_validate_json(
        (run_dir / "blame.json").read_text(encoding="utf-8")
    )
    assert actual == expected
    assert isinstance(fake_blamer.calls[0], BlamerInput)
    assert cassette_calls == [(run_dir / "cassettes" / "llm" / "blame.jsonl", "record")]


def test_cmd_blame_manual_override_skips_blamer_call(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir, trace = _make_run(tmp_path)

    class RaisingBlamer:
        def __init__(self) -> None:
            raise AssertionError("manual override must not construct Blamer")

    @contextmanager
    def raising_cassette(_path: Path, mode: str) -> Iterator[None]:
        raise AssertionError(f"manual override must not open cassette in {mode}")
        yield

    monkeypatch.setattr(cmd_blame, "Blamer", RaisingBlamer)
    monkeypatch.setattr(cmd_blame, "cassette_context", raising_cassette)

    rc = main(
        [
            "blame",
            "--trace-id",
            trace.trace_id,
            "--target",
            "reasoner",
            "--no-confirm",
        ]
    )

    assert rc == 0
    actual = BlamerOutput.model_validate_json(
        (run_dir / "blame.json").read_text(encoding="utf-8")
    )
    assert actual.target_path == "reasoner"
    assert "manual" in actual.rationale.lower()
    assert actual.leaf_targeted_critique == "The answer should not mention retrieval."


def test_cmd_blame_replay_deterministic(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir, trace = _make_run(tmp_path)
    cache: dict[Path, BlamerOutput] = {}
    active_path: Path | None = None

    @contextmanager
    def fake_cassette(path: Path, mode: str) -> Iterator[None]:
        nonlocal active_path
        assert mode == "record"
        active_path = path
        try:
            yield
        finally:
            active_path = None

    class CachingBlamer:
        calls = 0

        async def abuild(self) -> "CachingBlamer":
            return self

        async def __call__(self, _x: BlamerInput) -> SimpleNamespace:
            assert active_path is not None
            if active_path not in cache:
                type(self).calls += 1
                cache[active_path] = BlamerOutput(
                    target_path="reasoner",
                    rationale=f"recorded call {type(self).calls}",
                    leaf_targeted_critique="Route greetings to direct answer.",
                    severity=0.7,
                )
            return SimpleNamespace(response=cache[active_path])

    monkeypatch.setattr(cmd_blame, "Blamer", CachingBlamer)
    monkeypatch.setattr(cmd_blame, "cassette_context", fake_cassette)
    monkeypatch.setattr(cmd_blame, "load_all_leaves", _leaf_directory)

    args = [
        "blame",
        "--trace-id",
        trace.trace_id,
        "--selfserve-root",
        str(tmp_path),
        "--no-confirm",
    ]
    assert main(args) == 0
    first = (run_dir / "blame.json").read_text(encoding="utf-8")
    assert main(args) == 0
    second = (run_dir / "blame.json").read_text(encoding="utf-8")

    assert first == second
    assert CachingBlamer.calls == 1


def test_cmd_blame_missing_feedback_returns_2(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    _run_dir, trace = _make_run(tmp_path, with_feedback=False)

    rc = main(["blame", "--trace-id", trace.trace_id, "--no-confirm"])

    captured = capsys.readouterr()
    assert rc == 2
    assert "Feedback file not found" in captured.err


def test_cmd_blame_malformed_feedback_returns_2(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir, trace = _make_run(tmp_path, with_feedback=False)
    (run_dir / "feedback.json").write_text("{", encoding="utf-8")

    rc = main(["blame", "--trace-id", trace.trace_id, "--no-confirm"])

    captured = capsys.readouterr()
    assert rc == 2
    assert "Malformed feedback file" in captured.err


def test_cmd_blame_invalid_target_returns_2(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    _run_dir, trace = _make_run(tmp_path)

    rc = main(
        [
            "blame",
            "--trace-id",
            trace.trace_id,
            "--target",
            "unknown_step",
            "--no-confirm",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "Unknown target" in captured.err
    assert "reasoner" in captured.err
    assert "control_flow" in captured.err


def test_cmd_blame_special_target_writes_blame_json(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir, trace = _make_run(tmp_path)

    rc = main(
        [
            "blame",
            "--trace-id",
            trace.trace_id,
            "--target",
            "control_flow",
            "--no-confirm",
        ]
    )

    assert rc == 0
    actual = BlamerOutput.model_validate_json(
        (run_dir / "blame.json").read_text(encoding="utf-8")
    )
    assert actual.target_path == "control_flow"
    assert "manual" in actual.rationale.lower()


def _make_run(
    tmp_path: Path,
    *,
    with_feedback: bool = True,
) -> tuple[Path, WorkflowTrace]:
    trace = WorkflowTrace(
        entry_id="entry-1",
        frames=[
            TraceFrame(
                step_name="reasoner",
                agent_class="ReasonerLeaf",
                leaf_role="Reasoner role",
                leaf_task="Reasoner task",
                input={"message": "hello"},
                output={"intent": "RAG_NEEDED"},
            ),
            TraceFrame(
                step_name="rag_talker",
                agent_class="RAGTalkerLeaf",
                leaf_role="RAG talker role",
                leaf_task="RAG talker task",
                input={"message": "hello"},
                output={"answer": "Hello with a retrieval preamble."},
            ),
        ],
        final_answer_text="Hello with a retrieval preamble.",
        intent_decision="RAG_NEEDED",
    ).seal()
    run_dir = tmp_path / ".uthereal-runs" / trace.entry_id
    trace.to_jsonl(run_dir / "trace.jsonl")
    if with_feedback:
        HumanFeedback(
            trace_id=trace.trace_id,
            final_answer_critique="The answer should not mention retrieval.",
            severity=0.6,
            desired_behavior="Answer directly.",
        ).to_json(run_dir / "feedback.json")
    return run_dir, trace


def _leaf_directory(_selfserve_root: Path) -> dict[str, Agent[Any, Any]]:
    return {
        step_name: DummyLeaf(role=f"{step_name} role", task=f"{step_name} task")
        for step_name in KNOWN_LEAF_PATHS
    }


def _patch_blamer(
    monkeypatch: Any,
    output: BlamerOutput,
) -> type:
    class FakeBlamer:
        calls: list[BlamerInput] = []

        async def abuild(self) -> "FakeBlamer":
            return self

        async def __call__(self, x: BlamerInput) -> SimpleNamespace:
            type(self).calls.append(x)
            return SimpleNamespace(response=output)

    monkeypatch.setattr(cmd_blame, "Blamer", FakeBlamer)
    return FakeBlamer


def _patch_cassette(
    monkeypatch: Any,
    calls: list[tuple[Path, str]],
) -> None:
    @contextmanager
    def fake_cassette(path: Path, mode: str) -> Iterator[None]:
        calls.append((path, mode))
        yield

    monkeypatch.setattr(cmd_blame, "cassette_context", fake_cassette)
