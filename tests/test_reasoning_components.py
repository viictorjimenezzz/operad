"""Tests for the leaf agents under `operad.agents.reasoning.components`."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel, Field

from operad.agents import (
    Action,
    Actor,
    Answer,
    Classifier,
    Critic,
    Evaluator,
    Extractor,
    Observation,
    Planner,
    Reasoner,
    Thought,
)
from operad.algorithms import Candidate, Score


class _Question(BaseModel):
    text: str = Field(default="", description="The user's question.")


class _Reasoning(BaseModel):
    reasoning: str = Field(default="")
    answer: str = Field(default="")


class _Review(BaseModel):
    text: str = Field(default="")


class _Sentiment(BaseModel):
    label: Literal["positive", "negative", "neutral"] = "neutral"


class _Goal(BaseModel):
    goal: str = Field(default="")


class _Plan(BaseModel):
    steps: list[str] = Field(default_factory=list)


class _Doc(BaseModel):
    text: str = Field(default="")


class _Facts(BaseModel):
    facts: list[str] = Field(default_factory=list)


LEAF_SPECS = [
    (Reasoner, _Question, _Reasoning),
    (Extractor, _Doc, _Facts),
    (Classifier, _Review, _Sentiment),
    (Planner, _Goal, _Plan),
    (Actor, Thought, Action),
    (Evaluator, Observation, Answer),
]


@pytest.mark.parametrize("cls,in_cls,out_cls", LEAF_SPECS)
def test_leaf_defaults_are_populated(cfg, cls, in_cls, out_cls) -> None:
    leaf = cls(config=cfg, input=in_cls, output=out_cls)
    assert leaf.role, f"{cls.__name__}.role is empty"
    assert leaf.task, f"{cls.__name__}.task is empty"
    assert leaf.rules, f"{cls.__name__}.rules is empty"
    assert leaf.input is in_cls
    assert leaf.output is out_cls


@pytest.mark.parametrize("cls,in_cls,out_cls", LEAF_SPECS)
def test_leaf_task_override_wins(cfg, cls, in_cls, out_cls) -> None:
    leaf = cls(config=cfg, input=in_cls, output=out_cls, task="custom-task")
    assert leaf.task == "custom-task"


def test_subclass_can_specialize_class_attrs(cfg) -> None:
    class SentimentClassifier(Classifier):
        input = _Review
        output = _Sentiment
        task = "Classify the review's overall sentiment."

    leaf = SentimentClassifier(config=cfg)
    assert leaf.input is _Review
    assert leaf.output is _Sentiment
    assert leaf.task == "Classify the review's overall sentiment."
    assert leaf.role == Classifier.role  # inherited default


def test_critic_input_output_are_fixed(cfg) -> None:
    critic = Critic(config=cfg)
    assert critic.input is Candidate
    assert critic.output is Score
    assert critic.role and critic.task and critic.rules
