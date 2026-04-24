"""Benchmark primitives: typed datasets, per-row entries, and evaluation."""

from __future__ import annotations

from .aggregated import AggregatedMetric, Reducer
from .dataset import Dataset
from .entry import Entry
from .evaluate import EvalReport, evaluate
from .sensitivity import SensitivityCell, SensitivityReport, sensitivity

__all__ = [
    "AggregatedMetric",
    "Dataset",
    "Entry",
    "EvalReport",
    "Reducer",
    "SensitivityCell",
    "SensitivityReport",
    "evaluate",
    "sensitivity",
]
