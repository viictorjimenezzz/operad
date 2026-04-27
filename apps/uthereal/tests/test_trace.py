from __future__ import annotations

"""Owner: 1-5-trace-feedback-models.

Tests for workflow trace models and observer capture.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from apps_uthereal.workflow.trace import (
    TraceFrame,
    WorkflowTrace,
    WorkflowTraceObserver,
)
from operad import Agent, Configuration, Sequential
from operad.optim.backprop import tape
from operad.runtime.observers.base import registry


class InputModel(BaseModel):
    text: str = ""


class MiddleModel(BaseModel):
    value: int = 0


class OutputModel(BaseModel):
    label: str = ""


class FakeLeaf(Agent[Any, Any]):
    """Offline leaf that returns a canned typed output."""

    def __init__(
        self,
        *,
        config: Configuration,
        input: type[BaseModel],
        output: type[BaseModel],
        task: str = "",
        rules: tuple[str, ...] = (),
        canned: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            config=config,
            input=input,
            output=output,
            task=task,
            rules=rules,
        )
        self.canned = dict(canned or {})

    async def forward(self, x: Any) -> Any:
        return self.output.model_construct(**self.canned)


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    registry.clear()
    yield
    registry.clear()


@pytest.fixture
def cfg() -> Configuration:
    return Configuration(backend="openai", model="gpt-4o-mini", api_key="test")


def _frame(step_name: str, *, value: int = 1) -> TraceFrame:
    return TraceFrame(
        step_name=step_name,
        agent_class="FakeLeaf",
        leaf_role="role",
        leaf_task="task",
        leaf_rules=["rule"],
        input={"text": "hello"},
        output={"value": value},
        latency_ms=1.0,
        hash_prompt=f"prompt-{step_name}",
        hash_input=f"input-{step_name}",
        hash_output_schema="schema",
        run_id="run",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
    )


def test_trace_frame_frozen() -> None:
    frame = _frame("first")

    with pytest.raises(ValidationError):
        frame.step_name = "changed"  # type: ignore[misc]


def test_trace_frame_model_construct_returns_default_frame() -> None:
    frame = TraceFrame.model_construct()

    assert isinstance(frame, TraceFrame)


def test_workflow_trace_seal_is_deterministic() -> None:
    first = _frame("first")
    second = _frame("second")

    trace_a = WorkflowTrace(frames=[first, second]).seal()
    trace_b = WorkflowTrace(frames=[first, second]).seal()
    trace_c = WorkflowTrace(frames=[second, first]).seal()

    assert trace_a.trace_id
    assert trace_a.trace_id == trace_b.trace_id
    assert trace_a.trace_id != trace_c.trace_id
    assert trace_a.sealed is True


def test_to_jsonl_round_trip(tmp_path: Path) -> None:
    trace = WorkflowTrace(
        entry_id="entry",
        frames=[_frame("first")],
        final_answer_text="final",
        intent_decision="RAG_NEEDED",
    ).seal()
    path = tmp_path / "trace.jsonl"

    trace.to_jsonl(path)
    loaded = WorkflowTrace.from_jsonl(path)

    assert loaded == trace
    assert loaded.sealed is True


def test_jsonl_header_first(tmp_path: Path) -> None:
    trace = WorkflowTrace(entry_id="entry", frames=[_frame("first")]).seal()
    path = tmp_path / "trace.jsonl"

    trace.to_jsonl(path)
    header = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    assert header["trace_id"] == trace.trace_id
    assert header["entry_id"] == "entry"
    assert "step_name" not in header


def test_to_blamer_summary_truncates_long_fields() -> None:
    long_text = "x" * 80
    trace = WorkflowTrace(
        frames=[
            _frame("first").model_copy(
                update={
                    "leaf_role": long_text,
                    "leaf_task": long_text,
                    "input": {"text": long_text},
                    "output": {"text": long_text},
                }
            )
        ]
    )

    summary = trace.to_blamer_summary(max_field_chars=20)

    assert "…[truncated, total=80 chars]" in summary
    for line in summary.splitlines():
        if line.startswith(("role: ", "task: ")):
            assert len(line.split(": ", 1)[1]) <= 55


@pytest.mark.asyncio
async def test_observer_records_one_frame_per_leaf(cfg: Configuration) -> None:
    first = FakeLeaf(
        config=cfg,
        input=InputModel,
        output=MiddleModel,
        task="first task",
        canned={"value": 2},
    )
    second = FakeLeaf(
        config=cfg,
        input=MiddleModel,
        output=OutputModel,
        task="second task",
        canned={"label": "ok"},
    )
    pipeline = await Sequential(
        first,
        second,
        input=InputModel,
        output=OutputModel,
    ).abuild()
    observer = WorkflowTraceObserver(entry_id="entry")
    registry.register(observer)

    async with tape():
        await pipeline(InputModel(text="go"))

    trace = observer.trace
    assert len(trace.frames) == 2
    assert [frame.step_name for frame in trace.frames] == [
        "Sequential.stage_0",
        "Sequential.stage_1",
    ]


@pytest.mark.asyncio
async def test_observer_records_input_output_dicts(cfg: Configuration) -> None:
    leaf = await FakeLeaf(
        config=cfg,
        input=InputModel,
        output=MiddleModel,
        canned={"value": 7},
    ).abuild()
    observer = WorkflowTraceObserver(entry_id="entry")
    registry.register(observer)

    await leaf(InputModel(text="hello"))

    frame = observer.trace.frames[0]
    assert frame.input == {"text": "hello"}
    assert frame.output == {"value": 7}


@pytest.mark.asyncio
async def test_observer_records_hash_fields(cfg: Configuration) -> None:
    leaf = await FakeLeaf(
        config=cfg,
        input=InputModel,
        output=MiddleModel,
        canned={"value": 1},
    ).abuild()
    observer = WorkflowTraceObserver(entry_id="entry")
    registry.register(observer)

    await leaf(InputModel(text="hash me"))

    frame = observer.trace.frames[0]
    assert frame.hash_prompt
    assert frame.hash_input
    assert frame.hash_output_schema


def test_workflow_trace_find_step_raises_keyerror_on_missing() -> None:
    trace = WorkflowTrace(frames=[_frame("present")])

    with pytest.raises(KeyError):
        trace.find_step("missing")
