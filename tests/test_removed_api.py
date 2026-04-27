"""Removed API surface from the operad flow refactor."""

from __future__ import annotations

import importlib

import pytest

import operad.metrics as metrics
import operad.train as train


@pytest.mark.parametrize(
    "module_name",
    [
        "operad.configs",
        "operad.runtime.cost",
        "operad.metrics.deterministic",
        "operad.metrics.base",
        "operad.metrics.contains",
        "operad.metrics.regex_match",
        "operad.metrics.rubric_critic",
        "operad.train.losses_hf",
        "operad.train.callbacks_traceback",
    ],
)
def test_removed_modules_are_gone(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


@pytest.mark.parametrize(
    "name",
    ["Contains", "RegexMatch", "Rouge1", "RubricCritic"],
)
def test_removed_metric_names_are_gone(name: str) -> None:
    assert not hasattr(metrics, name)


@pytest.mark.parametrize(
    "name",
    ["HumanFeedbackLoss", "LearningRateLogger", "EarlyStoppingSpec"],
)
def test_removed_train_names_are_gone(name: str) -> None:
    assert not hasattr(train, name)
