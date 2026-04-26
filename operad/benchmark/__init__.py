"""Benchmark primitives: typed datasets, per-row entries, and evaluation."""

from __future__ import annotations

from .aggregated import AggregatedMetric, Reducer
from .dataset import Dataset
from .entry import Entry
from .evaluate import EvalReport, evaluate
from .experiment import Experiment
from .regression import RegressionReport, regression_check
from .sensitivity import SensitivityCell, SensitivityReport, sensitivity
from .suite import (
    ALL_METHODS,
    OFFLINE_METHODS,
    BenchmarkCell,
    BenchmarkContext,
    BenchmarkMethod,
    BenchmarkReport,
    BenchmarkRunConfig,
    BenchmarkSuite,
    BenchmarkSummaryRow,
    BenchmarkTask,
    BenchmarkTokens,
    default_benchmark_methods,
)

__all__ = [
    "AggregatedMetric",
    "ALL_METHODS",
    "BenchmarkCell",
    "BenchmarkContext",
    "BenchmarkMethod",
    "BenchmarkReport",
    "BenchmarkRunConfig",
    "BenchmarkSuite",
    "BenchmarkSummaryRow",
    "BenchmarkTask",
    "BenchmarkTokens",
    "Dataset",
    "Entry",
    "EvalReport",
    "Experiment",
    "OFFLINE_METHODS",
    "Reducer",
    "RegressionReport",
    "SensitivityCell",
    "SensitivityReport",
    "default_benchmark_methods",
    "evaluate",
    "regression_check",
    "sensitivity",
]
