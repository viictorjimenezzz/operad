from __future__ import annotations

"""Bridge-only workflow schemas.

Drift is monitored by `make schemas-check` (advisory, not blocking).

Owner: 1-2-vendored-schemas.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from apps_uthereal.schemas._common import JsonValue


class DatasetEntry(BaseModel):
    """One input that the user sends through the loop."""

    entry_id: str | None = Field(default=None, description="Stable entry id; computed from canonical JSON when absent.")
    id_tenant: str = Field(default="", description="Tenant identifier (uthereal multi-tenant key).")
    workspace_id: str = Field(default="", description="Workspace identifier (uthereal id_workspace).")
    id_assistant: str = Field(default="", description="Assistant identifier (selfserve id_assistant).")
    user_message: str = Field(default="", description="Latest user message.")
    chat_history: str = Field(default="", description="Rendered previous turns.")
    session_memory_context: str = Field(default="", description="Rendered SessionMemoryState for previous turns.")
    prior_beliefs_context: str = Field(default="", description="Rendered BeliefMemoryState for previous turns.")
    context: str = Field(default="", description="Assistant persona/role string.")
    workspace_guide: str = Field(default="", description="Workspace guide.")
    exit_strategy: str = Field(default="", description="Conversation exit strategy.")
    target_language: str = Field(default="", description="Optional output language code.")
    character_limit: int | None = Field(default=10000, description="Maximum user-message character count.")

    model_config = ConfigDict(frozen=True)

    def model_post_init(self, __context: Any) -> None:
        """Fill a missing entry id from the canonical entry payload."""

        if self.entry_id is None:
            object.__setattr__(self, "entry_id", self.compute_entry_id())

    def compute_entry_id(self) -> str:
        """Return sha256(canonical_json(entry_without_entry_id))[:12]."""

        payload = self.model_dump(mode="json", exclude={"entry_id"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def from_json(cls, path: Path) -> "DatasetEntry":
        """Load a dataset entry from a JSON file."""

        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))


class WorkspaceMetadata(BaseModel):
    """What the runner needs from the RAG container's metadata endpoint."""

    workspace_id: str = Field(default="", description="Workspace identifier (id_workspace).")
    id_tenant: str = Field(default="", description="Tenant identifier.")
    id_assistant: str = Field(default="", description="Assistant identifier.")
    id_to_datasource: dict[str, str] = Field(default_factory=dict, description="Datasource id lookup.")
    id_to_length: dict[str, int] = Field(default_factory=dict, description="Content-length lookup.")
    rules: list[dict[str, JsonValue]] = Field(default_factory=list, description="Opaque rule envelopes.")
    tags: list[str] = Field(default_factory=list, description="Workspace tag ids.")

    model_config = ConfigDict(frozen=True)


class ArtemisInput(BaseModel):
    """The runner's typed input, built from a DatasetEntry plus workspace metadata."""

    entry: DatasetEntry = Field(default_factory=DatasetEntry, description="Dataset entry for this run.")
    workspace: WorkspaceMetadata = Field(default_factory=WorkspaceMetadata, description="Workspace metadata.")

    model_config = ConfigDict(frozen=True)


class ArtemisFinalAnswer(BaseModel):
    """The runner's typed output: final answer plus references."""

    utterance: str = Field(default="", description="Final answer text.")
    references: dict[str, JsonValue] | None = Field(default=None, description="Opaque RAG references.")
    intent_decision: Literal["DIRECT_ANSWER", "RAG_NEEDED", "SAFEGUARD_REJECTED"] = Field(
        default="DIRECT_ANSWER",
        description="Final route that produced this answer.",
    )
    safeguard_category: str | None = Field(default=None, description="Safeguard category for rejected paths.")
    final_step: str = Field(default="", description="Leaf path that produced the utterance.")

    model_config = ConfigDict(frozen=True)
