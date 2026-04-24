"""Structured reports surfaced by `Trainer.fit()`.

`EpochReport` captures one training epoch; `TrainingReport` wraps the
list plus best-epoch bookkeeping. Both are Pydantic models so they can
be serialised alongside cassettes or persisted next to a frozen agent.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EpochReport(BaseModel):
    """One epoch of `fit()` — train loss, optional val metrics, LR."""

    epoch: int
    train_loss: float
    train_metrics: dict[str, float] = Field(default_factory=dict)
    val_loss: float | None = None
    val_metrics: dict[str, float] = Field(default_factory=dict)
    lr: list[float] = Field(default_factory=list)
    duration_s: float = 0.0
    hash_content: str = ""


class TrainingReport(BaseModel):
    """Full `fit()` report: every epoch, plus best-monitor bookkeeping."""

    epochs: list[EpochReport] = Field(default_factory=list)
    best_epoch: int = -1
    best_val_metric: float = float("nan")
    best_hash_content: str = ""
    seed_hash_content: str = ""


__all__ = ["EpochReport", "TrainingReport"]
