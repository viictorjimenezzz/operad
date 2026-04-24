"""`HumanFeedbackCallback` NDJSON writer + `HumanFeedbackLoss` reader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from operad.benchmark.evaluate import EvalReport
from operad.train import HumanFeedbackCallback, HumanFeedbackLoss
from operad.train.callbacks import _row_id


class _Out(BaseModel):
    text: str


def _report(rows: list[dict]) -> EvalReport:
    return EvalReport(rows=rows, summary={})


async def test_callback_writes_one_row_per_validation_row(tmp_path: Path) -> None:
    cb = HumanFeedbackCallback(tmp_path / "hf.jsonl", agent_path="Talker")
    report = _report(
        [
            {"input": {"text": "hi"}, "expected": None, "predicted": {"text": "hello"}},
            {"input": {"text": "bye"}, "expected": None, "predicted": {"text": "goodbye"}},
        ]
    )
    await cb.on_validation_end(trainer=None, report=report)  # type: ignore[arg-type]

    lines = (tmp_path / "hf.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    row0 = json.loads(lines[0])
    assert row0["id"] and isinstance(row0["id"], str)
    assert row0["input"] == {"text": "hi"}
    assert row0["predicted"] == {"text": "hello"}
    assert row0["rating"] is None
    assert row0["agent_path"] == "Talker"


async def test_callback_appends_across_validations(tmp_path: Path) -> None:
    cb = HumanFeedbackCallback(tmp_path / "hf.jsonl")
    r1 = _report([{"input": {"text": "a"}, "expected": None, "predicted": {"text": "A"}}])
    r2 = _report([{"input": {"text": "b"}, "expected": None, "predicted": {"text": "B"}}])
    await cb.on_validation_end(trainer=None, report=r1)  # type: ignore[arg-type]
    await cb.on_validation_end(trainer=None, report=r2)  # type: ignore[arg-type]
    assert len((tmp_path / "hf.jsonl").read_text().splitlines()) == 2


async def test_callback_skips_rows_without_predictions(tmp_path: Path) -> None:
    cb = HumanFeedbackCallback(tmp_path / "hf.jsonl")
    r = _report(
        [
            {"input": {"text": "hi"}, "expected": None, "predicted": None},
            {"input": {"text": "bye"}, "expected": None, "predicted": {"text": "ok"}},
        ]
    )
    await cb.on_validation_end(trainer=None, report=r)  # type: ignore[arg-type]
    lines = (tmp_path / "hf.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["predicted"] == {"text": "ok"}


async def test_loss_rates_matched_predicted_output(tmp_path: Path) -> None:
    predicted = _Out(text="hello")
    row_id = _row_id(predicted.model_dump(mode="json"))
    ratings_path = tmp_path / "r.jsonl"
    ratings_path.write_text(
        json.dumps(
            {
                "id": row_id,
                "run_id": "r",
                "agent_path": "",
                "input": {"text": "hi"},
                "expected": None,
                "predicted": {"text": "hello"},
                "rating": 4,
                "rationale": "Good tone.",
                "written_at": "",
            }
        )
        + "\n"
    )
    loss = HumanFeedbackLoss(ratings_path)
    score, grad = await loss.compute(predicted, None)
    assert score == pytest.approx(0.8)
    assert grad.severity == pytest.approx(0.2)
    assert "4/5" in grad.message
    assert "Good tone." in grad.message


async def test_loss_neutral_for_unrated_or_missing_row(tmp_path: Path) -> None:
    loss = HumanFeedbackLoss(tmp_path / "nope.jsonl")
    score, grad = await loss.compute(_Out(text="anything"), None)
    assert score == pytest.approx(0.5)
    assert grad.severity == 0.0
    # Unrated (rating=None) row also produces neutral result.
    ratings_path = tmp_path / "r.jsonl"
    predicted = _Out(text="wave")
    row_id = _row_id(predicted.model_dump(mode="json"))
    ratings_path.write_text(
        json.dumps({"id": row_id, "rating": None, "rationale": None}) + "\n"
    )
    loss2 = HumanFeedbackLoss(ratings_path)
    score2, grad2 = await loss2.compute(predicted, None)
    assert score2 == pytest.approx(0.5)
    assert grad2.severity == 0.0


async def test_loss_perfect_rating_emits_null_gradient(tmp_path: Path) -> None:
    predicted = _Out(text="ok")
    row_id = _row_id(predicted.model_dump(mode="json"))
    ratings_path = tmp_path / "r.jsonl"
    ratings_path.write_text(
        json.dumps({"id": row_id, "rating": 5, "rationale": ""}) + "\n"
    )
    loss = HumanFeedbackLoss(ratings_path)
    score, grad = await loss.compute(predicted, None)
    assert score == pytest.approx(1.0)
    assert grad.severity == 0.0
