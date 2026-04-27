from __future__ import annotations

"""Tests for mutable Artemis runner state.

Owner: 2-2-run-state.
"""

from apps_uthereal.schemas.workflow import (
    ArtemisFinalAnswer,
    ArtemisInput,
    DatasetEntry,
    WorkspaceMetadata,
)
from apps_uthereal.workflow.state import ArtemisRunState


def test_run_state_construct_default() -> None:
    state = ArtemisRunState.model_construct()

    assert state.input_message == ""
    assert state.workspace_id == ""
    assert state.matched_rules == []
    assert state.retrieval_specs == []
    assert state.rag_results == []
    assert state.summarization_results == []
    assert state.collected_claims == {}
    assert state.references is None
    assert state.intent_decision is None


def test_run_state_from_input_copies_fields() -> None:
    entry = DatasetEntry(
        workspace_id="workspace-entry",
        user_message="How do I cite this?",
        chat_history="user: earlier",
        session_memory_context="user likes concise answers",
        prior_beliefs_context="[]",
        context="You answer from the workspace.",
        workspace_guide="Workspace guide",
        exit_strategy="End politely.",
        target_language="de",
        character_limit=123,
    )
    x = ArtemisInput(
        entry=entry,
        workspace=WorkspaceMetadata(
            workspace_id="workspace-metadata",
            rules=[{"id": "rule-1"}],
            tags=["tag-1"],
        ),
    )

    state = ArtemisRunState.from_input(x)

    assert state.input_message == entry.user_message
    assert state.workspace_id == entry.workspace_id
    assert state.context == entry.context
    assert state.workspace_guide == entry.workspace_guide
    assert state.exit_strategy == entry.exit_strategy
    assert state.target_language == entry.target_language
    assert state.chat_history == entry.chat_history
    assert state.session_memory_context == entry.session_memory_context
    assert state.prior_beliefs_context == entry.prior_beliefs_context
    assert state.character_limit == entry.character_limit
    assert state.safeguard_decision is None
    assert state.route is None
    assert state.retrieval_specs == []
    assert state.references is None


def test_run_state_is_mutable() -> None:
    state = ArtemisRunState()

    state.utterance = "hello"

    assert state.utterance == "hello"


def test_to_final_answer_for_direct_path() -> None:
    state = ArtemisRunState(
        intent_decision="DIRECT_ANSWER",
        utterance="Hi there.",
        final_step="conv_talker",
    )

    answer = state.to_final_answer()

    assert answer == ArtemisFinalAnswer(
        utterance="Hi there.",
        references=None,
        intent_decision="DIRECT_ANSWER",
        safeguard_category=None,
        final_step="conv_talker",
    )


def test_to_final_answer_for_rag_path() -> None:
    state = ArtemisRunState(
        intent_decision="RAG_NEEDED",
        utterance="Use the cited protocol.",
        references={"claim-1": "document-1"},
        final_step="rag_talker",
    )

    answer = state.to_final_answer()

    assert answer == ArtemisFinalAnswer(
        utterance="Use the cited protocol.",
        references={"claim-1": "document-1"},
        intent_decision="RAG_NEEDED",
        safeguard_category=None,
        final_step="rag_talker",
    )


def test_to_final_answer_for_safeguard_path() -> None:
    state = ArtemisRunState(
        intent_decision="SAFEGUARD_REJECTED",
        utterance="I can only help with workspace topics.",
        safeguard_category="separate_domain",
        references={"ignored": "outside-terminal-path"},
        final_step="safeguard_talker",
    )

    answer = state.to_final_answer()

    assert answer == ArtemisFinalAnswer(
        utterance="I can only help with workspace topics.",
        references=None,
        intent_decision="SAFEGUARD_REJECTED",
        safeguard_category="separate_domain",
        final_step="safeguard_talker",
    )


def test_to_final_answer_for_char_limit_path() -> None:
    state = ArtemisRunState(
        intent_decision="CHAR_LIMIT_REJECTED",
        utterance="Your message exceeds the 10000 character limit.",
        references={"ignored": "outside-terminal-path"},
        final_step="char_limit",
    )

    answer = state.to_final_answer()

    assert isinstance(answer, ArtemisFinalAnswer)
    assert answer.utterance == "Your message exceeds the 10000 character limit."
    assert answer.references is None
    assert answer.intent_decision == "CHAR_LIMIT_REJECTED"
    assert answer.safeguard_category is None
    assert answer.final_step == "char_limit"
