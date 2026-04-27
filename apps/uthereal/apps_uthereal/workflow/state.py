from __future__ import annotations

"""Owner: 2-2-run-state.

Mutable workflow state for the uthereal bridge runner.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from apps_uthereal.schemas.retrieval import (
    RetrievalResult,
    RetrievalSpecification,
    SummarizationResult,
)
from apps_uthereal.schemas.workflow import ArtemisFinalAnswer, ArtemisInput


_IntentDecision = Literal[
    "DIRECT_ANSWER",
    "RAG_NEEDED",
    "SAFEGUARD_REJECTED",
    "CHAR_LIMIT_REJECTED",
]


class ArtemisRunState(BaseModel):
    """Mutable state threaded through the runner.

    Construction: created from `ArtemisInput` at the start of a run.
    Mutation: each leaf may set its declared output fields. Each field
    has a sensible default so partial runs are safe.

    This is NOT a value object; `frozen=False`. The runner mutates it.
    Treat it like an `asyncio` task-local: one instance per run.
    """

    # --- inputs (set at construction; never mutated post-init) -----------

    input_message: str = ""
    workspace_id: str = ""
    context: str = ""
    workspace_guide: str = ""
    exit_strategy: str = ""
    target_language: str = ""
    chat_history: str = ""
    session_memory_context: str = ""
    prior_beliefs_context: str = ""
    character_limit: int | None = 10000

    # --- safeguard outputs ----------------------------------------------

    safeguard_decision: Literal["yes", "no", "exit"] | None = None
    safeguard_reason: str = ""
    safeguard_category: str = ""

    # --- reasoner outputs -----------------------------------------------

    rewritten_message: str = ""
    downstream_message: str = ""
    route: Literal["DIRECT_ANSWER", "RAG_NEEDED"] | None = None
    route_reasoning: str = ""
    reasoner_scratchpad: str = ""

    # --- retrieval pipeline outputs --------------------------------------

    matched_rules: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_specs: list[RetrievalSpecification] = Field(default_factory=list)
    rag_results: list[RetrievalResult] = Field(default_factory=list)
    summarization_results: list[SummarizationResult] = Field(default_factory=list)
    collected_claims: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    references: dict[str, Any] | None = None

    # --- final ----------------------------------------------------------

    utterance: str = ""
    final_step: str = ""
    intent_decision: _IntentDecision | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def from_input(cls, x: ArtemisInput) -> "ArtemisRunState":
        """Build a state from an ArtemisInput.

        Workspace metadata is read but not stored on the state; the
        runner consumes it directly when constructing retrieval specs.
        """

        entry = x.entry
        return cls(
            input_message=entry.user_message,
            workspace_id=entry.workspace_id,
            context=entry.context,
            workspace_guide=entry.workspace_guide,
            exit_strategy=entry.exit_strategy,
            target_language=entry.target_language,
            chat_history=entry.chat_history,
            session_memory_context=entry.session_memory_context,
            prior_beliefs_context=entry.prior_beliefs_context,
            character_limit=entry.character_limit,
        )

    def to_final_answer(self) -> ArtemisFinalAnswer:
        """Project the final answer envelope from terminal state."""

        intent_decision = self.intent_decision or "DIRECT_ANSWER"
        payload = {
            "utterance": self.utterance,
            "references": self.references if intent_decision == "RAG_NEEDED" else None,
            "intent_decision": intent_decision,
            "safeguard_category": (
                self.safeguard_category
                if intent_decision == "SAFEGUARD_REJECTED"
                else None
            ),
            "final_step": self.final_step,
        }
        if intent_decision == "CHAR_LIMIT_REJECTED":
            return ArtemisFinalAnswer.model_construct(**payload)
        return ArtemisFinalAnswer.model_validate(payload)
