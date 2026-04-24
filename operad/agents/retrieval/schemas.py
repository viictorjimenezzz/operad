"""Typed edges for the retrieval domain."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- FactFilter -------------------------------------------------------------


class FactFilterInput(BaseModel):
    facts: str = Field(
        default="",
        description="Plain-text block of facts, each formatted as 'fact_id: <int>' and 'text: <content>', separated by a blank line.",
    )
    query: str = Field(default="", description="User question.")


class FactFilterOutput(BaseModel):
    fact_ids: list[int] = Field(
        default_factory=list,
        description="List of fact_id integers to keep.",
    )


# --- EvidencePlanner --------------------------------------------------------


class ClaimItem(BaseModel):
    claim_id: str = Field(
        default="",
        description="Unique identifier (e.g. 'c-0', 'c-1').",
    )
    scratchpad: str = Field(
        default="",
        description="1-3 sentence working note on how this claim was constructed.",
    )
    claim: str = Field(
        default="",
        description="Self-contained claim written as a plain sentence.",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Non-empty list of fact IDs ('f-M') or image IDs ('i-K').",
    )
    rationale: str = Field(
        default="",
        description="1-2 sentences explaining how the evidence supports the claim.",
    )


class EvidencePlannerInput(BaseModel):
    query: str = Field(default="", description="User question.")
    facts: str = Field(
        default="",
        description="Pre-rendered facts grouped by datasource (d-N / f-M blocks).",
    )
    images: str = Field(
        default="",
        description="Optional textual descriptor for image attachments labelled i-0, i-1, ...",
    )


class EvidencePlannerOutput(BaseModel):
    claim_sequence: list[ClaimItem] = Field(
        default_factory=list,
        description="List of claims supported by the evidence.",
    )


# --- CitationGist -----------------------------------------------------------


class GistBlock(BaseModel):
    id: int = Field(default=0, description="Sequential identifier.")
    token: str = Field(default="", description="Placeholder in the answer text.")
    claim_text: str = Field(
        default="",
        description="Atomic claim from the evidence planner (what is being asserted).",
    )
    rationale: str = Field(
        default="",
        description="Planner's reasoning for why the evidence supports the claim.",
    )
    surrounding_context: str = Field(
        default="",
        description="Sentences in the answer immediately around this citation occurrence.",
    )
    contents: str = Field(
        default="",
        description="Raw evidence texts from the referenced source.",
    )


class CitationGistInput(BaseModel):
    target_language: str = Field(
        default="",
        description="Target language for the gists.",
    )
    assistant_context: str = Field(
        default="",
        description="Background context the assistant relied on.",
    )
    utterance_beyond_facts: bool = Field(
        default=False,
        description="True when the assistant may go beyond retrieved evidence in full_answer.",
    )
    gist_blocks: list[GistBlock] = Field(
        default_factory=list,
        description="One entry per citation occurrence that needs an explanation.",
    )
    full_answer: str = Field(
        default="",
        description="The complete answer the user will read.",
    )


class GistItem(BaseModel):
    id: int = Field(default=0, description="The corresponding gist_block id.")
    gist: str = Field(
        default="",
        description="Concise 2-5 sentence reader-facing explanation.",
    )


class GistBatchOutput(BaseModel):
    gists: list[GistItem] = Field(
        default_factory=list,
        description="One gist per input block, keyed by block id.",
    )


class TextResponse(BaseModel):
    text: str = Field(default="", description="The response body as raw text.")


__all__ = [
    "CitationGistInput",
    "ClaimItem",
    "EvidencePlannerInput",
    "EvidencePlannerOutput",
    "FactFilterInput",
    "FactFilterOutput",
    "GistBatchOutput",
    "GistBlock",
    "GistItem",
    "TextResponse",
]
