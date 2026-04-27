from __future__ import annotations

"""Owner: 1-5-trace-feedback-models.

Tests for human feedback JSON helpers.
"""

from pathlib import Path

from apps_uthereal.feedback.schema import HumanFeedback


def test_human_feedback_round_trip(tmp_path: Path) -> None:
    feedback = HumanFeedback(
        trace_id="trace",
        final_answer_critique="Too vague.",
        target_path="reasoner",
        severity=0.5,
        desired_behavior="Be specific.",
    )
    path = tmp_path / "feedback.json"

    feedback.to_json(path)

    assert HumanFeedback.from_json(path) == feedback


def test_human_feedback_template_defaults() -> None:
    feedback = HumanFeedback.template("trace")

    assert feedback.trace_id == "trace"
    assert feedback.final_answer_critique == ""
    assert feedback.target_path is None
    assert feedback.severity == 1.0
    assert feedback.desired_behavior is None
