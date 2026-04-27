from __future__ import annotations

"""Tests for vendored schema boundaries.

Owner: 1-2-vendored-schemas.
"""

import importlib
import json
import sys
from pathlib import Path
from typing import get_args

import pytest
from pydantic import BaseModel, ValidationError


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


YAML_SCHEMA_MAP = {
    "input/agents/agent_context_safeguard.yaml": (
        "apps_uthereal.schemas.safeguard.ContextSafeguardInput",
        "apps_uthereal.schemas.safeguard.ContextSafeguardResponse",
    ),
    "input/agents/agent_safeguard_talker.yaml": (
        "apps_uthereal.schemas.talker.SafeguardTalkerInput",
        "apps_uthereal.schemas.talker.SafeguardTalkerOutput",
    ),
    "reasoner/agents/agent_reasoner.yaml": (
        "apps_uthereal.schemas.reasoner.ReasonerInput",
        "apps_uthereal.schemas.reasoner.ReasonerOutput",
    ),
    "reasoner/agents/agent_conversational_talker.yaml": (
        "apps_uthereal.schemas.talker.ConversationalTalkerInput",
        "apps_uthereal.schemas.talker.ConversationalTalkerOutput",
    ),
    "retrieval/agents/agent_rule_classifier.yaml": (
        "apps_uthereal.schemas.rules.RuleClassifierInput",
        "apps_uthereal.schemas.rules.RuleClassifierOutput",
    ),
    "retrieval/agents/agent_retrieval_orchestrator.yaml": (
        "apps_uthereal.schemas.rules.RetrievalOrchestratorInput",
        "apps_uthereal.schemas.rules.RetrievalOrchestratorOutput",
    ),
    "retrieval/agents/agent_evidence_planner.yaml": (
        "apps_uthereal.schemas.evidence.EvidencePlannerInput",
        "apps_uthereal.schemas.evidence.EvidencePlannerOutput",
    ),
    "retrieval/agents/agent_fact_filter.yaml": (
        "apps_uthereal.schemas.evidence.FactFilterInput",
        "apps_uthereal.schemas.evidence.FactFilterOutput",
    ),
    "retrieval/agents/agent_talker.yaml": (
        "apps_uthereal.schemas.talker.RAGTalkerInput",
        "apps_uthereal.schemas.talker.RAGTalkerOutput",
    ),
}


PUBLIC_SCHEMA_PATHS = [
    "apps_uthereal.schemas._common.ImageRef",
    "apps_uthereal.schemas._common.MessageTurn",
    "apps_uthereal.schemas.safeguard.ContextSafeguardInput",
    "apps_uthereal.schemas.safeguard.ContextSafeguardResponse",
    "apps_uthereal.schemas.reasoner.ReasonerInput",
    "apps_uthereal.schemas.reasoner.ReasonerOutput",
    "apps_uthereal.schemas.retrieval.RetrievalSpecification",
    "apps_uthereal.schemas.retrieval.RetrievalResult",
    "apps_uthereal.schemas.retrieval.SummarizationResult",
    "apps_uthereal.schemas.retrieval.ClaimItem",
    "apps_uthereal.schemas.talker.InteractionContext",
    "apps_uthereal.schemas.talker.SafeguardTalkerInput",
    "apps_uthereal.schemas.talker.SafeguardTalkerOutput",
    "apps_uthereal.schemas.talker.ConversationalTalkerInput",
    "apps_uthereal.schemas.talker.ConversationalTalkerOutput",
    "apps_uthereal.schemas.talker.RAGTalkerInput",
    "apps_uthereal.schemas.talker.RAGTalkerOutput",
    "apps_uthereal.schemas.rules.RuleClassifierInput",
    "apps_uthereal.schemas.rules.RuleClassifierOutput",
    "apps_uthereal.schemas.rules.RetrievalOrchestratorInput",
    "apps_uthereal.schemas.rules.RetrievalOrchestratorOutput",
    "apps_uthereal.schemas.evidence.EvidencePlannerInput",
    "apps_uthereal.schemas.evidence.EvidencePlannerOutput",
    "apps_uthereal.schemas.evidence.FactFilterInput",
    "apps_uthereal.schemas.evidence.FactFilterOutput",
    "apps_uthereal.schemas.workflow.DatasetEntry",
    "apps_uthereal.schemas.workflow.WorkspaceMetadata",
    "apps_uthereal.schemas.workflow.ArtemisInput",
    "apps_uthereal.schemas.workflow.ArtemisFinalAnswer",
]


def _load(path: str) -> type[BaseModel]:
    module_name, class_name = path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


@pytest.mark.parametrize(("yaml_path", "schema_paths"), YAML_SCHEMA_MAP.items())
def test_each_in_scope_yaml_has_vendored_input_and_output(yaml_path: str, schema_paths: tuple[str, str]) -> None:
    assert yaml_path.endswith(".yaml")
    for schema_path in schema_paths:
        assert issubclass(_load(schema_path), BaseModel)


@pytest.mark.parametrize("schema_path", PUBLIC_SCHEMA_PATHS)
def test_construct_default_for_every_schema(schema_path: str) -> None:
    schema = _load(schema_path)
    schema.model_construct()


@pytest.mark.parametrize("schema_path", PUBLIC_SCHEMA_PATHS)
def test_validate_round_trip(schema_path: str) -> None:
    schema = _load(schema_path)
    model = schema.model_construct()
    assert schema.model_validate(json.loads(model.model_dump_json())) == model


def test_safeguard_category_literal_set() -> None:
    from apps_uthereal.schemas.safeguard import SafeguardCategory

    assert set(get_args(SafeguardCategory)) == {
        "in_scope",
        "exit",
        "separate_domain",
        "mixed_scope",
        "dangerous_or_illegal",
        "sexual_disallowed",
        "distress_self_harm",
    }


def test_route_literal_set() -> None:
    from apps_uthereal.schemas.reasoner import RouteLiteral

    assert set(get_args(RouteLiteral)) == {"DIRECT_ANSWER", "RAG_NEEDED"}


def test_dataset_entry_id_canonicalization(tmp_path: Path) -> None:
    from apps_uthereal.schemas.workflow import DatasetEntry

    left = DatasetEntry(workspace_id="w1", user_message="hello")
    right = DatasetEntry(user_message="hello", workspace_id="w1")
    assert left.compute_entry_id() == right.compute_entry_id()
    assert left.entry_id == right.entry_id == left.compute_entry_id()

    path = tmp_path / "entry.json"
    path.write_text('{"user_message":"hello","workspace_id":"w1"}', encoding="utf-8")
    loaded = DatasetEntry.from_json(path)
    assert loaded.entry_id == left.entry_id


@pytest.mark.parametrize("schema_path", PUBLIC_SCHEMA_PATHS)
def test_frozen_models(schema_path: str) -> None:
    schema = _load(schema_path)
    model = schema.model_construct()
    field = next(iter(schema.model_fields))

    with pytest.raises((ValidationError, TypeError)):
        setattr(model, field, "changed")

    model.model_copy(update={field: getattr(model, field)})
