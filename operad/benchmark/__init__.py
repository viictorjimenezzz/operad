"""Benchmark primitives: typed datasets, per-row entries, and evaluation."""

from __future__ import annotations

from .aggregated import AggregatedMetric, Reducer
from .dataset import Dataset
from .entry import Entry
from .evaluate import EvalReport, evaluate
from .experiment import Experiment

__all__ = [
    "AggregatedMetric",
    "Dataset",
    "Entry",
    "EvalReport",
    "Experiment",
    "Reducer",
    "evaluate",
]
