from __future__ import annotations

"""Owner: 2-4-feedback-loss.

Human-feedback loss for leaf-targeted textual gradients.
"""

from dataclasses import dataclass

from operad.optim.backprop.grad import TextualGradient

from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.schemas.workflow import ArtemisFinalAnswer

SPECIAL_TARGETS = frozenset(("control_flow", "data", "no_fault"))


class UnactionableFeedback(Exception):
    """Raised when feedback can't be turned into a leaf-targeted gradient."""

    def __init__(self, *, reason: str, message: str) -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


@dataclass
class HumanFeedbackLoss:
    """Loss-shaped adapter from human feedback to a textual gradient."""

    name: str = "human_feedback"

    async def compute(
        self,
        pred: ArtemisFinalAnswer,
        expected: HumanFeedback,
    ) -> tuple[float, TextualGradient]:
        """Compute a score and leaf-targeted textual gradient."""

        del pred
        target_path = expected.target_path
        if target_path is None:
            raise ValueError("HumanFeedbackLoss requires expected.target_path")
        if target_path in SPECIAL_TARGETS:
            raise UnactionableFeedback(
                reason=target_path,
                message=(
                    f"Feedback target {target_path!r} cannot be turned into "
                    "a leaf-targeted gradient."
                ),
            )

        message = expected.final_answer_critique
        if expected.desired_behavior:
            message = f"{message}\n\nDesired behavior: {expected.desired_behavior}"

        score = min(1.0, max(0.0, 1.0 - expected.severity))
        return score, TextualGradient(
            message=message,
            severity=expected.severity,
            target_paths=[target_path],
        )


__all__ = ["HumanFeedbackLoss", "SPECIAL_TARGETS", "UnactionableFeedback"]
