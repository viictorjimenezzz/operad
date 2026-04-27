from __future__ import annotations

"""Owner: 2-3-blamer.

Tests for the feedback Blamer agent and renderer.
"""

import json
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import BaseModel, ValidationError

from operad import Agent, Configuration

from apps_uthereal.feedback.blamer import (
    KNOWN_LEAF_PATHS,
    SPECIAL_TARGETS,
    Blamer,
    BlamerInput,
    BlamerOutput,
    LeafSummary,
    render_blamer_input,
)
from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.workflow.trace import TraceFrame, WorkflowTrace


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "blamer"
CASE_NAMES = (
    "case_wrong_route",
    "case_wrong_refusal",
    "case_off_style",
    "case_unresolvable",
    "case_no_fault",
)


class DummyInput(BaseModel):
    """Minimal input for renderer-only leaf placeholders."""

    text: str = ""


class DummyOutput(BaseModel):
    """Minimal output for renderer-only leaf placeholders."""

    text: str = ""


class DummyLeaf(Agent[DummyInput, DummyOutput]):
    """Leaf placeholder used only for role/task metadata."""

    input = DummyInput
    output = DummyOutput


def _leaf_directory() -> dict[str, Agent[Any, Any]]:
    return {
        step_name: DummyLeaf(
            role=f"{step_name} role",
            task=f"{step_name} task",
            rules=(f"{step_name} rule",),
        )
        for step_name in KNOWN_LEAF_PATHS
    }


def _load_case(name: str) -> tuple[WorkflowTrace, HumanFeedback, dict[str, str]]:
    case_dir = FIXTURE_DIR / name
    expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    return (
        WorkflowTrace.from_jsonl(case_dir / "trace.jsonl"),
        HumanFeedback.from_json(case_dir / "feedback.json"),
        expected,
    )


def test_blamer_class_pins_input_output() -> None:
    blamer = Blamer()

    assert Blamer.input is BlamerInput
    assert Blamer.output is BlamerOutput
    assert blamer.input is BlamerInput
    assert blamer.output is BlamerOutput


def test_blamer_target_path_literal_includes_all_leaves_and_specials() -> None:
    target_args = set(get_args(BlamerOutput.model_fields["target_path"].annotation))

    assert target_args == set(KNOWN_LEAF_PATHS + SPECIAL_TARGETS)


@pytest.mark.asyncio
async def test_blamer_abuild_succeeds_with_test_config() -> None:
    blamer = await Blamer(
        config=Configuration(
            backend="openai",
            model="gpt-4o-mini",
            api_key="test",
        )
    ).abuild()

    assert blamer.input is BlamerInput
    assert blamer.output is BlamerOutput


def test_render_blamer_input_deterministic() -> None:
    trace, feedback, _expected = _load_case("case_wrong_route")
    leaves = _leaf_directory()

    first = render_blamer_input(
        trace=trace,
        feedback=feedback,
        leaf_directory=leaves,
    )
    second = render_blamer_input(
        trace=trace,
        feedback=feedback,
        leaf_directory=leaves,
    )

    assert first == second
    assert first.trace_summary
    assert first.final_answer == trace.final_answer_text
    assert first.user_critique == feedback.final_answer_critique
    assert first.desired_behavior == feedback.desired_behavior


def test_render_blamer_input_includes_all_leaves() -> None:
    trace, feedback, _expected = _load_case("case_wrong_route")

    rendered = render_blamer_input(
        trace=trace,
        feedback=feedback,
        leaf_directory=_leaf_directory(),
    )

    by_step = {leaf.step_name: leaf for leaf in rendered.leaves}
    assert tuple(by_step) == KNOWN_LEAF_PATHS
    assert by_step["reasoner"].fired_in_trace is True
    assert by_step["rag_talker"].fired_in_trace is True
    assert by_step["context_safeguard"].fired_in_trace is False
    assert by_step["context_safeguard"].role == "context_safeguard role"


def test_render_blamer_input_truncates_long_fields() -> None:
    long_text = "x" * 700
    trace = WorkflowTrace(
        entry_id="entry",
        frames=[
            TraceFrame(
                step_name="reasoner",
                agent_class="ReasonerLeaf",
                leaf_role=long_text,
                leaf_task=long_text,
                input={"message": long_text},
                output={"intent": "DIRECT_ANSWER", "reasoning": long_text},
            )
        ],
        final_answer_text=long_text,
    ).seal()
    feedback = HumanFeedback(
        trace_id=trace.trace_id,
        final_answer_critique="Too long.",
    )

    rendered = render_blamer_input(
        trace=trace,
        feedback=feedback,
        leaf_directory=_leaf_directory(),
    )
    reasoner = next(leaf for leaf in rendered.leaves if leaf.step_name == "reasoner")

    assert "truncated, total=" in rendered.trace_summary
    assert "truncated, total=" in reasoner.input_preview
    assert "truncated, total=" in reasoner.output_preview


def test_blamer_examples_validate() -> None:
    assert len(Blamer.examples) >= 5
    for example in Blamer.examples:
        assert isinstance(BlamerInput.model_validate(example.input), BlamerInput)
        assert isinstance(BlamerOutput.model_validate(example.output), BlamerOutput)
        assert example.input.trace_summary
        assert example.input.leaves


def test_blamer_severity_in_unit_interval() -> None:
    for example in Blamer.examples:
        assert 0.0 <= example.output.severity <= 1.0

    with pytest.raises(ValidationError):
        BlamerOutput(
            target_path="reasoner",
            rationale="bad severity",
            leaf_targeted_critique="bad severity",
            severity=1.1,
        )


@pytest.mark.parametrize("case_name", CASE_NAMES)
def test_blamer_fixture_cases_are_well_formed(case_name: str) -> None:
    trace, feedback, expected = _load_case(case_name)

    assert trace.frames
    assert feedback.final_answer_critique
    assert expected["target_path"] in KNOWN_LEAF_PATHS + SPECIAL_TARGETS
    assert expected["rationale_substring"]


@pytest.mark.asyncio
async def test_blamer_picks_reasoner_on_wrong_route() -> None:
    cassette_path = (
        Path(__file__).parent
        / "cassettes"
        / "test_blamer_picks_reasoner_on_wrong_route.jsonl"
    )
    if not cassette_path.exists():
        pytest.skip("Blamer LLM cassette is absent.")

    from operad.utils.cassette import cassette_context

    trace, feedback, _expected = _load_case("case_wrong_route")
    rendered = render_blamer_input(
        trace=trace,
        feedback=feedback,
        leaf_directory=_leaf_directory(),
    )
    with cassette_context(cassette_path, mode="replay"):
        blamer = await Blamer().abuild()
        output = (await blamer(rendered)).response

    assert output.target_path == "reasoner"
