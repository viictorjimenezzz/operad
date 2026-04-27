from __future__ import annotations

"""Owner: 2-4-feedback-loss.

Tests for human-feedback loss.
"""

import pytest

from operad.optim.backprop.grad import TextualGradient

from apps_uthereal.feedback.loss import HumanFeedbackLoss, UnactionableFeedback
from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.schemas.workflow import ArtemisFinalAnswer


def _answer() -> ArtemisFinalAnswer:
    return ArtemisFinalAnswer(utterance="The answer.")


def _feedback(**overrides: object) -> HumanFeedback:
    fields = {
        "trace_id": "trace",
        "final_answer_critique": "The answer is too vague.",
        "target_path": "rag_pipeline.talker",
        "severity": 0.4,
        "desired_behavior": None,
    }
    fields.update(overrides)
    return HumanFeedback.model_validate(fields)


async def test_compute_returns_score_and_gradient() -> None:
    score, gradient = await HumanFeedbackLoss().compute(
        _answer(),
        _feedback(severity=0.25),
    )

    assert score == 0.75
    assert isinstance(gradient, TextualGradient)


async def test_gradient_target_paths_single_element_list() -> None:
    _, gradient = await HumanFeedbackLoss().compute(
        _answer(),
        _feedback(target_path="reasoner"),
    )

    assert gradient.target_paths == ["reasoner"]


async def test_gradient_severity_matches_feedback() -> None:
    _, gradient = await HumanFeedbackLoss().compute(
        _answer(),
        _feedback(severity=0.65),
    )

    assert gradient.severity == 0.65


async def test_gradient_message_joins_critique_and_desired_behavior() -> None:
    _, gradient = await HumanFeedbackLoss().compute(
        _answer(),
        _feedback(
            final_answer_critique="It missed the citation.",
            desired_behavior="Cite the retrieved protocol.",
        ),
    )

    assert gradient.message == (
        "It missed the citation.\n\n"
        "Desired behavior: Cite the retrieved protocol."
    )


@pytest.mark.parametrize(
    ("severity", "score"),
    [
        (0.3, 0.7),
        (-0.5, 1.0),
        (1.5, 0.0),
    ],
)
async def test_score_is_one_minus_severity(severity: float, score: float) -> None:
    actual_score, _ = await HumanFeedbackLoss().compute(
        _answer(),
        _feedback(severity=severity),
    )

    assert actual_score == score


async def test_compute_raises_on_none_target_path() -> None:
    with pytest.raises(ValueError):
        await HumanFeedbackLoss().compute(
            _answer(),
            _feedback(target_path=None),
        )


async def test_compute_raises_unactionable_on_control_flow_target() -> None:
    with pytest.raises(UnactionableFeedback) as exc_info:
        await HumanFeedbackLoss().compute(
            _answer(),
            _feedback(target_path="control_flow"),
        )

    assert exc_info.value.reason == "control_flow"


async def test_compute_raises_unactionable_on_data_target() -> None:
    with pytest.raises(UnactionableFeedback) as exc_info:
        await HumanFeedbackLoss().compute(
            _answer(),
            _feedback(target_path="data"),
        )

    assert exc_info.value.reason == "data"


async def test_compute_raises_unactionable_on_no_fault_target() -> None:
    with pytest.raises(UnactionableFeedback) as exc_info:
        await HumanFeedbackLoss().compute(
            _answer(),
            _feedback(target_path="no_fault"),
        )

    assert exc_info.value.reason == "no_fault"
