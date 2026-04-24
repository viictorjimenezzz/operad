"""Conversation-scope safeguard classifier."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import ContextInput, ContextOutput


class Context(Agent[ContextInput, ContextOutput]):
    """Decide whether a user message is in-scope, off-topic, unsafe, or an exit."""

    input = ContextInput
    output = ContextOutput

    role = (
        "You are a conversation safeguard specialist within an agent pipeline. "
        "Your task is to evaluate if a user's 'message' falls within the broad "
        "domain of the conversation and if it is accepted as the next message "
        "in the ongoing conversation. Your role is to block only clearly "
        "off-topic or harmful messages, so if the message is even remotely "
        "related to the conversation, it should be accepted."
    )
    task = (
        "You will be provided with different sources of information for this task.\n"
        "- First, you may be given the 'context' of the agent, which may include "
        "the role of the agent, the purpose of the conversation and the topics "
        "that will be discussed.\n"
        "- You may also be provided with the recent 'chat history' between the "
        "user and the agent, so that you can determine whether the incoming "
        "message makes sense within the conversation.\n"
        "- Finally, you may be provided with some 'exit strategies' that are in "
        "place for the cases where the user wants to leave the conversation.\n\n"
        "You must decide whether the 'message' is suitable within the context "
        "of the conversation and the purpose of the agent, and whether an exit "
        "strategy has been activated."
    )
    rules = (
        "Analyze the provided 'context' and 'chat history' to understand the "
        "broad domain of the conversation. Accept the message if it falls "
        "anywhere within that domain. The 'context' describes the agent's "
        "domain, not an exhaustive list of allowed topics. Any message that a "
        "user could reasonably send while working within that domain is "
        "acceptable.",
        "'CRITICAL: Always interpret the message within the conversation "
        "domain, never in isolation. A message may look like a general "
        "question on its own, but within the conversation's domain it takes on "
        "a domain-specific meaning.",
        "When in doubt, accept. Interpret user messages charitably and with "
        "maximum generosity toward relevance. Users will ask operational "
        "questions, reference specific details, entities, names, criteria, or "
        "attributes that are not mentioned in the context but are naturally "
        "part of the domain. These are valid messages.",
        "Accept messages that ask the agent to skip certain variables or "
        "stages, and also ambiguous answers from the user that can be "
        "interpreted as a request to move forward. For instance, it should be "
        "possible for the user to ignore some value that is being asked for.",
        "You must not evaluate the correctness of answers provided by the user "
        "to agent queries. You must only evaluate the alignment of the "
        "'message' with the conversation 'context'. For instance, if the user "
        "is asked for a name and provides a number, you must not evaluate the "
        "correctness of the number, only the alignment of the 'message' with "
        "the conversation context. Additionally, if the user argues about a "
        "previous agent utterance or asks for clarification, you must accept "
        "the message.",
        "Distinguish between referencing details *within* the domain versus "
        "requesting expertise from an *entirely separate* professional domain. "
        "Mentioning a specific entity, name, skill, attribute, or criterion "
        "that naturally arises within the domain is always acceptable. "
        "However, explicitly requesting advice or analysis that belongs to a "
        "fundamentally different professional field (e.g., legal "
        "enforceability, medical dosage, financial auditing) is out of scope, "
        "even if the request is loosely related to the conversation topic.",
        "Reject messages that bundle an in-scope request with an explicit "
        "out-of-scope request. If any part of the message asks for expertise "
        "from a separate professional domain, the entire message should be "
        "rejected.",
        "Do not accept messages that make reference to any illegal activities "
        "or other dangerous content.",
        "Do not accept messages that contain sexual content outside the "
        "assistant's purpose. Classify these as 'sexual_disallowed', not "
        "'dangerous_or_illegal'.",
        "Exit semantics: Analyze the 'exit strategies' to determine if any of "
        "them have been activated by the message. 'exit' means the user is "
        "genuinely choosing to end, cancel, stop, opt out, or leave the "
        "conversation flow — not merely expressing frustration or "
        "dissatisfaction with one response. If the user is frustrated but "
        "still engaging with the domain, that is 'yes', not 'exit'. Use "
        "'exit' only when the message matches an exit strategy or "
        "unambiguously signals discontinuation.",
        "Decision and category: Provide 'continue_field' as 'yes', 'no', or "
        "'exit', plus a concise 'reason'. You must also provide a 'category' "
        "that classifies the semantic type of your decision:\n"
        "  - continue_field 'yes' -> category 'in_scope'\n"
        "  - continue_field 'exit' -> category 'exit'\n"
        "  - continue_field 'no' -> pick the most specific category from:\n"
        "      'separate_domain' — the message requests expertise from an "
        "entirely different professional field\n"
        "      'mixed_scope' — the message bundles an in-scope request with "
        "an out-of-scope request\n"
        "      'dangerous_or_illegal' — the message references illegal "
        "activities or other dangerous content\n"
        "      'sexual_disallowed' — the message contains sexual content "
        "outside the assistant's purpose\n"
        "      'distress_self_harm' — the message expresses distress, "
        "suicidal ideation, or self-harm intent",
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
