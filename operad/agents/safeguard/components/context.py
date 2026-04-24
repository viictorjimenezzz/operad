"""Conversation-scope safeguard classifier."""

from __future__ import annotations

from inspect import cleandoc

from ....core.agent import Agent, Example
from ..schemas import ContextInput, ContextOutput


class Context(Agent[ContextInput, ContextOutput]):
    """Decide whether a user message is in-scope, off-topic, unsafe, or an exit."""

    input = ContextInput
    output = ContextOutput

    role = cleandoc("""
        You are a conversation safeguard specialist within an agent
        pipeline. Your task is to evaluate whether the user's latest
        message falls within the broad domain of the conversation and
        whether it is acceptable as the next message in the ongoing
        exchange. Your role is to block only clearly off-topic or
        harmful messages — if the message is even remotely related to
        the conversation, it should be accepted.
    """)
    task = cleandoc("""
        Decide whether the message is suitable within the conversation
        domain and the assistant's purpose, and whether an exit
        strategy has been activated.
    """)
    rules = (
        cleandoc("""
            Analyse the assistant context and recent chat history to
            understand the broad domain of the conversation. Accept
            the message if it falls anywhere within that domain. The
            context describes the domain, not an exhaustive list of
            allowed topics. Any message that a user could reasonably
            send while working within that domain is acceptable.
        """),
        "CRITICAL: Always interpret the message within the conversation "
        "domain, never in isolation. A message may look like a general "
        "question on its own, but within the conversation's domain it "
        "takes on a domain-specific meaning.",
        cleandoc("""
            When in doubt, accept. Interpret user messages charitably
            and with maximum generosity toward relevance. Users will
            ask operational questions, reference specific details,
            entities, names, criteria, or attributes that are not
            mentioned in the context but are naturally part of the
            domain. These are valid messages.
        """),
        cleandoc("""
            Accept messages that ask the agent to skip certain
            variables or stages, and ambiguous user answers that can
            be interpreted as a request to move forward. It should be
            possible for the user to ignore a value that is being
            asked for.
        """),
        cleandoc("""
            Do not evaluate the correctness of answers provided by the
            user to agent queries. Only evaluate the alignment of the
            message with the conversation context. For instance, if
            the user is asked for a name and provides a number, do not
            evaluate the correctness of the number, only the
            alignment. If the user argues about a previous agent
            utterance or asks for clarification, accept the message.
        """),
        cleandoc("""
            Distinguish between referencing details *within* the domain
            and requesting expertise from an *entirely separate*
            professional domain. Mentioning a specific entity, name,
            skill, attribute, or criterion that naturally arises within
            the domain is always acceptable. However, explicitly
            requesting advice or analysis that belongs to a
            fundamentally different professional field (e.g. legal
            enforceability, medical dosage, financial auditing) is out
            of scope, even if the request is loosely related to the
            conversation topic.
        """),
        "Reject messages that bundle an in-scope request with an explicit "
        "out-of-scope request. If any part of the message asks for "
        "expertise from a separate professional domain, the entire "
        "message should be rejected.",
        "Do not accept messages that reference illegal activities or "
        "other dangerous content.",
        "Do not accept messages that contain sexual content outside the "
        "assistant's purpose. Classify these as 'sexual_disallowed', not "
        "'dangerous_or_illegal'.",
        cleandoc("""
            Exit semantics: analyse the exit strategies to determine if
            any of them have been activated by the message. "exit"
            means the user is genuinely choosing to end, cancel, stop,
            opt out, or leave the conversation flow — not merely
            expressing frustration or dissatisfaction with one
            response. If the user is frustrated but still engaging
            with the domain, that is "yes", not "exit". Use "exit"
            only when the message matches an exit strategy or
            unambiguously signals discontinuation.
        """),
        cleandoc("""
            Decision and category:
              - continue_field "yes" -> category "in_scope"
              - continue_field "exit" -> category "exit"
              - continue_field "no" -> pick the most specific category from:
                    "separate_domain" — the message requests expertise from an entirely different professional field
                    "mixed_scope" — the message bundles an in-scope request with an out-of-scope request
                    "dangerous_or_illegal" — the message references illegal activities or other dangerous content
                    "sexual_disallowed" — the message contains sexual content outside the assistant's purpose
                    "distress_self_harm" — the message expresses distress, suicidal ideation, or self-harm intent
        """),
    )
    examples = (
        Example[ContextInput, ContextOutput](
            input=ContextInput(
                context="This is a professional discussion about environmental sustainability.",
                recent_chat_history=(
                    "AGENT: How can I help you? USER: I would like you to design a "
                    "sustainability strategy for my business. AGENT: Great! What aspects "
                    "of environmental sustainability are you interested in addressing? "
                    "USER: I am not sure. AGENT: No worries, I will explain them to you. "
                    "The first aspect to consider is..."
                ),
                exit_strategy="The conversation must be terminated when the message...",
                message="I am interested in the last one you mentioned.",
            ),
            output=ContextOutput(
                reason="The message aligns with the conversation context.",
                continue_field="yes",
                category="in_scope",
            ),
        ),
        Example[ContextInput, ContextOutput](
            input=ContextInput(
                context=(
                    "You are an expert in investment portfolio analysis. Your primary "
                    "function is to help users evaluate and optimize their investment "
                    "portfolios."
                ),
                recent_chat_history="",
                exit_strategy="",
                message="What about Tesla?",
            ),
            output=ContextOutput(
                reason=(
                    "Within the investment portfolio domain, the user is asking about "
                    "Tesla as a stock or investment, which is a valid operational question."
                ),
                continue_field="yes",
                category="in_scope",
            ),
        ),
        Example[ContextInput, ContextOutput](
            input=ContextInput(
                context="You are a hazardous materials storage expert.",
                recent_chat_history="",
                exit_strategy="",
                message="What medication should I take for my headache?",
            ),
            output=ContextOutput(
                reason=(
                    "The message requests medical advice, which belongs to a separate "
                    "professional domain."
                ),
                continue_field="no",
                category="separate_domain",
            ),
        ),
        Example[ContextInput, ContextOutput](
            input=ContextInput(
                context="You are a hazardous materials storage expert.",
                recent_chat_history="",
                exit_strategy="",
                message="I want to kill myself",
            ),
            output=ContextOutput(
                reason=(
                    "The message expresses distress and self-harm intent, which is "
                    "outside the domain and requires specialized support."
                ),
                continue_field="no",
                category="distress_self_harm",
            ),
        ),
    )
