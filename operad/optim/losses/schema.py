"""Schema-shape losses."""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from operad.metrics.metric import MetricBase
from operad.optim.losses.loss import _clamp01
from operad.optim.parameter import TextualGradient


# ---------------------------------------------------------------------------
# Loss.
# ---------------------------------------------------------------------------


class SchemaLoss(MetricBase):
    """Score whether `predicted` satisfies a target Pydantic schema.

    `expected` is ignored. This is useful when the only requirement is
    "the answer parses as the target schema." Score is the fraction of
    required fields that validate; per-field diagnostics populate
    `by_field` on the gradient.
    """

    def __init__(
        self, schema: type[BaseModel], *, name: str = "schema_loss"
    ) -> None:
        self.schema = schema
        self.name = name

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del expected
        s, _ = await self.compute(predicted, None)
        return s

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]:
        del expected
        required = [
            n for n, f in self.schema.model_fields.items() if f.is_required()
        ]
        by_field = _validation_errors(self.schema, predicted)
        if not by_field:
            return 1.0, TextualGradient.null_gradient()

        total = max(1, len(required))
        bad_required = sum(1 for k in by_field if k in required)
        score_val = _clamp01((total - bad_required) / total)
        message = "; ".join(f"{k}: {v}" for k, v in by_field.items())
        return score_val, TextualGradient(
            message=message,
            by_field=by_field,
            severity=_clamp01(1.0 - score_val),
        )


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _validation_errors(
    schema: type[BaseModel], predicted: BaseModel
) -> dict[str, str]:
    data = predicted.model_dump()
    try:
        schema.model_validate(data)
    except ValidationError as ve:
        by_field: dict[str, str] = {}
        for err in ve.errors():
            loc = err.get("loc", ())
            key = str(loc[0]) if loc else "?"
            by_field[key] = err.get("msg", "validation error")
        return by_field
    return {}


__all__ = ["SchemaLoss"]
