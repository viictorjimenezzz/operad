"""Benchmark primitives: typed datasets, per-row entries, and evaluation."""

from __future__ import annotations

from .aggregated import AggregatedMetric, Reducer
from .dataset import Dataset
from .entry import Entry
from .evaluate import EvalReport, evaluate
from .experiment import Experiment
from .regression import RegressionReport, regression_check

__all__ = [
    "AggregatedMetric",
    "Dataset",
    "Entry",
    "EvalReport",
    "Experiment",
    "Reducer",
    "RegressionReport",
    "evaluate",
    "regression_check",
]
