# 1-2 — vendor Pydantic schemas

**Batch:** 1 · **Parallelizable with:** 1-1, 1-3, 1-4, 1-5 · **Depends on:** —

You are vendoring the Pydantic schemas referenced by `selfserve/`'s
YAMLs. These schemas become the typed boundaries for every leaf agent
the bridge loads.

## Goal

Vendor every Pydantic schema referenced by the nine in-scope YAMLs into
`apps_uthereal/schemas/`. Add input schemas where the YAML's `input:`
block doesn't reference an external class (most YAMLs use a flat list of
fields and we need to give them a typed envelope). Provide a small
`make schemas-check` target that prints drift against the live
uthereal-src copies (advisory only).

## Files to create

| Path | What goes there |
|---|---|
| `apps_uthereal/schemas/__init__.py` | empty (touch only — created by 1-1) |
| `apps_uthereal/schemas/safeguard.py` | `ContextSafeguardResponse`, `SafeguardCategory` Literal |
| `apps_uthereal/schemas/reasoner.py` | `ReasonerInput`, `ReasonerOutput`, `RouteLiteral` |
| `apps_uthereal/schemas/retrieval.py` | `RetrievalSpecification`, `RetrievalResult`, `SummarizationResult`, `ClaimItem` |
| `apps_uthereal/schemas/talker.py` | `SafeguardTalkerInput`, `ConversationalTalkerInput`, `RAGTalkerInput`, plus shared `InteractionContext` value-object |
| `apps_uthereal/schemas/rules.py` | `RuleClassifierInput`, `RuleClassifierOutput`, `RetrievalOrchestratorInput`, `RetrievalOrchestratorOutput` |
| `apps_uthereal/schemas/evidence.py` | `EvidencePlannerInput`, `EvidencePlannerOutput`, `FactFilterInput`, `FactFilterOutput` |
| `apps_uthereal/schemas/workflow.py` | `ArtemisInput`, `ArtemisFinalAnswer`, `DatasetEntry`, `WorkspaceMetadata` |
| `apps_uthereal/schemas/_common.py` | `ImageRef`, `MessageTurn`, `JsonValue`, shared field validators |
| `apps/uthereal/Makefile` | adds `schemas-check` target (full Makefile is owned by 5-1; create stub here) |
| `apps/uthereal/scripts/schemas_check.py` | drift checker |
| `apps/uthereal/tests/test_schemas.py` | round-trip + literal tests |

## Source of truth

The canonical uthereal schemas live at:

```
/Users/viictorjimenezzz/Documents/uthereal/uthereal-src/uthereal_workflow/agentic_workflows/chat/selfserve/
├── input/schemas.py            (ContextSafeguardResponse)
├── reasoner/...                (intent/route schemas; may be inlined in workflow)
├── retrieval/...               (RetrievalSpecification, RetrievalResult, ...)
├── memory/schemas.py           (BeliefItem, BeliefMemoryState, BeliefOperation, ...)
└── ...
```

For each YAML in the in-scope set (`input/agents/agent_context_safeguard.yaml`,
`input/agents/agent_safeguard_talker.yaml`,
`reasoner/agents/agent_reasoner.yaml`,
`reasoner/agents/agent_conversational_talker.yaml`,
`retrieval/agents/agent_rule_classifier.yaml`,
`retrieval/agents/agent_retrieval_orchestrator.yaml`,
`retrieval/agents/agent_evidence_planner.yaml`,
`retrieval/agents/agent_fact_filter.yaml`,
`retrieval/agents/agent_talker.yaml`):

1. Read the YAML.
2. Inspect `output:` — if it points to a class
   (`uthereal_workflow.…schemas.X`), find that class in uthereal-src,
   copy its definition (and any transitively-referenced classes) into
   the appropriate `schemas/` module.
3. Inspect `input:` — if it's a flat list of fields, define a typed
   `<LeafName>Input` Pydantic model with one field per entry, preserving
   types and the `system: bool` / `optional: bool` flags via
   `json_schema_extra={"operad": {"system": bool}}` (matches operad's
   convention; see
   `operad/agents/safeguard/schemas.py::ContextInput` for an example).
4. If `output:` is `str` (free text, e.g. `agent_safeguard_talker.yaml`,
   `agent_conversational_talker.yaml`, `agent_talker.yaml`), define a
   single-field wrapper `class XOutput(BaseModel): text: str`. We
   consistently use typed outputs for everything to keep the operad
   pipeline uniform.

## API surface

Every vendored schema:

```python
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class ContextSafeguardResponse(BaseModel):
    """Vendored from
    uthereal_workflow.agentic_workflows.chat.selfserve.input.schemas.ContextSafeguardResponse.

    Drift is monitored by `make schemas-check`.
    """
    reason: str = Field(default="", description="...")
    continue_field: Literal["yes", "no", "exit"] = Field(default="yes", ...)
    category: SafeguardCategory = Field(default="in_scope", ...)

    model_config = ConfigDict(frozen=True)
```

The bridge-only top-level schemas:

```python
class DatasetEntry(BaseModel):
    """One input that the user sends through the loop."""
    entry_id: str | None = None        # filled by canonical_json hash if missing
    workspace_id: str
    user_message: str
    chat_history: str = ""             # rendered, n-1 turns
    session_memory_context: str = ""   # rendered SessionMemoryState; n-1
    prior_beliefs_context: str = ""    # rendered BeliefMemoryState; n-1
    context: str = ""                  # assistant persona/role string
    workspace_guide: str = ""
    exit_strategy: str = ""
    target_language: str = ""
    character_limit: int | None = 10000

    def compute_entry_id(self) -> str: ...   # sha256(canonical_json)[:12]
    @classmethod
    def from_json(cls, path: Path) -> "DatasetEntry": ...

class WorkspaceMetadata(BaseModel):
    """What the runner needs from the RAG container's metadata endpoint."""
    workspace_id: str
    id_to_datasource: dict[str, str]
    id_to_length: dict[str, int]
    rules: list[dict]               # opaque rule envelopes; rule_classifier interprets
    tags: list[str]

class ArtemisInput(BaseModel):
    """The runner's typed input — built from a DatasetEntry plus workspace metadata."""
    entry: DatasetEntry
    workspace: WorkspaceMetadata

class ArtemisFinalAnswer(BaseModel):
    """The runner's typed output — final answer plus references."""
    utterance: str
    references: dict | None = None     # opaque shape from RAG path; None for direct paths
    intent_decision: Literal["DIRECT_ANSWER", "RAG_NEEDED", "SAFEGUARD_REJECTED"]
    safeguard_category: str | None = None
    final_step: str                    # which leaf produced the utterance
```

## Implementation notes

- **Field defaults.** Every field gets a default that survives
  `model_construct()` (operad's build-time tracer constructs sentinel
  inputs with default values). Use `Field(default=...)` or `default=...`.
  Lists default to `Field(default_factory=list)`, dicts to
  `Field(default_factory=dict)`.
- **Frozen models.** Apply `model_config = ConfigDict(frozen=True)` to
  every value-object schema (everything in `schemas/`). Mutability
  belongs to the runner's `ArtemisRunState` (owned by 2-2), not here.
- **System fields.** Mark fields described as `system: true` in the YAML
  with `json_schema_extra={"operad": {"system": True}}`. Operad's
  renderer uses this annotation.
- **No imports from `uthereal_*`.** Even when copying definitions. If a
  vendored class transitively references another uthereal class, vendor
  that one too.
- **Schemas-check script.** `scripts/schemas_check.py` imports the
  vendored class and the live uthereal-src class (when available),
  computes `model_json_schema()` for each, and prints a unified diff.
  Exit 0 always (advisory). Skip silently if uthereal-src is not on the
  PYTHONPATH.

## Acceptance criteria

- [ ] Every YAML in the in-scope set has its `output:` schema vendored.
- [ ] Every YAML in the in-scope set has a typed `<Name>Input` model.
- [ ] `from apps_uthereal.schemas.safeguard import ContextSafeguardResponse` succeeds.
- [ ] `ContextSafeguardResponse(reason="x", continue_field="yes", category="in_scope")` constructs.
- [ ] `ContextSafeguardResponse.model_construct()` returns a model with all fields at defaults — no validation errors.
- [ ] Every model is frozen (`model.copy(update={...})` works; `model.field = ...` raises).
- [ ] `make schemas-check` runs and prints either "no drift" or a diff (depending on uthereal-src availability), exits 0.
- [ ] No imports from `uthereal_*` in any shipped module.

## Tests

- `test_each_in_scope_yaml_has_vendored_input_and_output` — for each YAML path, loadable + each schema importable.
- `test_construct_default_for_every_schema` — `Schema.model_construct()` for every public schema.
- `test_validate_round_trip` — for every schema, `Schema.model_validate(json.loads(s.model_dump_json())) == s`.
- `test_safeguard_category_literal_set` — assert the literal exactly matches `{"in_scope", "exit", "separate_domain", "mixed_scope", "dangerous_or_illegal", "sexual_disallowed", "distress_self_harm"}`.
- `test_route_literal_set` — `{"DIRECT_ANSWER", "RAG_NEEDED"}`.
- `test_dataset_entry_id_canonicalization` — same-content entries produce equal `entry_id`; reordering keys does not break stability.
- `test_frozen_models` — assert assignment raises.

## References

- `operad/agents/safeguard/schemas.py` — exact pattern for vendored
  schema files, including the `json_schema_extra={"operad": {"system": True}}`
  annotation style.
- `operad/agents/memory/shapes.py` — typed schemas with operations and
  literal-typed unions.
- `operad/agents/retrieval/schemas.py` — retrieval pipeline schemas.
- The uthereal `selfserve/AGENTS.md` documents which schemas exist and
  their relationships.

## Notes

(Append discoveries here as you implement.)
