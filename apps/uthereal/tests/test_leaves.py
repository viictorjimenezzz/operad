from __future__ import annotations

"""Tests for YAML-loaded uthereal leaf classes.

Owner: 2-1-operad-leaves.
"""

import shutil
from pathlib import Path
from typing import Any

import pytest
from operad import Agent
from pydantic import BaseModel

from apps_uthereal.leaves._common import load_yaml
from apps_uthereal.leaves.context_safeguard import ContextSafeguardLeaf
from apps_uthereal.leaves.conversational_talker import ConversationalTalkerLeaf
from apps_uthereal.leaves.evidence_planner import EvidencePlannerLeaf
from apps_uthereal.leaves.fact_filter import FactFilterLeaf
from apps_uthereal.leaves.rag_talker import RAGTalkerLeaf
from apps_uthereal.leaves.reasoner import ReasonerLeaf
from apps_uthereal.leaves.registry import (
    LEAF_REGISTRY,
    LEAF_STEP_NAMES,
    load_all_leaves,
)
from apps_uthereal.leaves.retrieval_orchestrator import RetrievalOrchestratorLeaf
from apps_uthereal.leaves.rule_classifier import RuleClassifierLeaf
from apps_uthereal.leaves.safeguard_talker import SafeguardTalkerLeaf
from apps_uthereal.schemas.evidence import (
    EvidencePlannerInput,
    EvidencePlannerOutput,
    FactFilterInput,
    FactFilterOutput,
)
from apps_uthereal.schemas.reasoner import ReasonerInput, ReasonerOutput
from apps_uthereal.schemas.rules import (
    RetrievalOrchestratorInput,
    RetrievalOrchestratorOutput,
    RuleClassifierInput,
    RuleClassifierOutput,
)
from apps_uthereal.schemas.safeguard import (
    ContextSafeguardInput,
    ContextSafeguardResponse,
)
from apps_uthereal.schemas.talker import (
    ConversationalTalkerInput,
    ConversationalTalkerOutput,
    RAGTalkerInput,
    RAGTalkerOutput,
    SafeguardTalkerInput,
    SafeguardTalkerOutput,
)


FIXTURES = Path(__file__).parent / "fixtures" / "yamls"
BUILD_OVERRIDES = {"backend": "openai", "model": "gpt-4o-mini"}

LEAF_CASES: list[
    tuple[
        str,
        type[Agent[Any, Any]],
        type[BaseModel],
        type[BaseModel],
    ]
] = [
    (
        "context_safeguard",
        ContextSafeguardLeaf,
        ContextSafeguardInput,
        ContextSafeguardResponse,
    ),
    (
        "safeguard_talker",
        SafeguardTalkerLeaf,
        SafeguardTalkerInput,
        SafeguardTalkerOutput,
    ),
    ("reasoner", ReasonerLeaf, ReasonerInput, ReasonerOutput),
    (
        "conv_talker",
        ConversationalTalkerLeaf,
        ConversationalTalkerInput,
        ConversationalTalkerOutput,
    ),
    (
        "rule_classifier",
        RuleClassifierLeaf,
        RuleClassifierInput,
        RuleClassifierOutput,
    ),
    (
        "retrieval_orchestrator",
        RetrievalOrchestratorLeaf,
        RetrievalOrchestratorInput,
        RetrievalOrchestratorOutput,
    ),
    (
        "evidence_planner",
        EvidencePlannerLeaf,
        EvidencePlannerInput,
        EvidencePlannerOutput,
    ),
    ("fact_filter", FactFilterLeaf, FactFilterInput, FactFilterOutput),
    ("rag_talker", RAGTalkerLeaf, RAGTalkerInput, RAGTalkerOutput),
]


@pytest.mark.parametrize(
    ("step_name", "leaf_cls", "input_cls", "output_cls"),
    LEAF_CASES,
    ids=[case[0] for case in LEAF_CASES],
)
def test_leaf_class_pins_correct_schemas(
    step_name: str,
    leaf_cls: type[Agent[Any, Any]],
    input_cls: type[BaseModel],
    output_cls: type[BaseModel],
) -> None:
    assert step_name
    assert leaf_cls.input is input_cls
    assert leaf_cls.output is output_cls


@pytest.mark.parametrize(
    ("step_name", "leaf_cls", "_input_cls", "_output_cls"),
    LEAF_CASES,
    ids=[case[0] for case in LEAF_CASES],
)
def test_leaf_loads_from_vendored_yaml(
    step_name: str,
    leaf_cls: type[Agent[Any, Any]],
    _input_cls: type[BaseModel],
    _output_cls: type[BaseModel],
) -> None:
    leaf = load_yaml(FIXTURES / f"{step_name}.yaml", leaf_cls=leaf_cls)

    assert leaf.role
    assert leaf.task
    assert leaf.rules


@pytest.mark.parametrize(
    ("step_name", "leaf_cls", "_input_cls", "_output_cls"),
    LEAF_CASES,
    ids=[case[0] for case in LEAF_CASES],
)
async def test_leaf_abuild_succeeds_offline(
    step_name: str,
    leaf_cls: type[Agent[Any, Any]],
    _input_cls: type[BaseModel],
    _output_cls: type[BaseModel],
) -> None:
    leaf = load_yaml(
        FIXTURES / f"{step_name}.yaml",
        leaf_cls=leaf_cls,
        config_overrides=BUILD_OVERRIDES,
    )

    assert await leaf.abuild() is leaf


def test_load_all_leaves_returns_all_step_names(tmp_path: Path) -> None:
    root = _copy_fixtures_to_selfserve_root(tmp_path)

    leaves = load_all_leaves(root, config_overrides=BUILD_OVERRIDES)

    assert set(leaves) == set(LEAF_STEP_NAMES.values())
    assert all(leaf._built for leaf in leaves.values())


def test_load_all_leaves_step_name_matches_runner_get_submodule_lookup(
    tmp_path: Path,
) -> None:
    root = _copy_fixtures_to_selfserve_root(tmp_path)
    leaves = load_all_leaves(root, config_overrides=BUILD_OVERRIDES)
    runner = _RunnerStub()

    for step_name, leaf in leaves.items():
        assert step_name.isidentifier()
        setattr(runner, step_name, leaf)
        assert getattr(runner, step_name) is leaf


@pytest.mark.parametrize(
    ("step_name", "leaf_cls", "_input_cls", "_output_cls"),
    LEAF_CASES,
    ids=[case[0] for case in LEAF_CASES],
)
def test_hash_content_stable_across_loads(
    step_name: str,
    leaf_cls: type[Agent[Any, Any]],
    _input_cls: type[BaseModel],
    _output_cls: type[BaseModel],
) -> None:
    first = load_yaml(FIXTURES / f"{step_name}.yaml", leaf_cls=leaf_cls)
    second = load_yaml(FIXTURES / f"{step_name}.yaml", leaf_cls=leaf_cls)

    assert first.hash_content == second.hash_content


def test_registry_paths_match_step_name_table() -> None:
    assert set(LEAF_REGISTRY) == set(LEAF_STEP_NAMES)


def _copy_fixtures_to_selfserve_root(tmp_path: Path) -> Path:
    for relative_path, step_name in LEAF_STEP_NAMES.items():
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURES / f"{step_name}.yaml", destination)
    return tmp_path


class _RunnerStub:
    pass
