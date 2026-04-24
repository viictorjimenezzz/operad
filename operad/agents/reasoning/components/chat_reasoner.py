"""Chat-pipeline reasoner: reference resolution, route, and downstream query."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import ChatReasonerInput, ChatReasonerOutput


class ChatReasoner(Agent[ChatReasonerInput, ChatReasonerOutput]):
    """Resolve references, decide route, and produce an optimized downstream message."""

    input = ChatReasonerInput
    output = ChatReasonerOutput

    role = (
        "You are the **central reasoning agent** inside a multi-stage "
        "agentic pipeline. You sit between a safeguard (already passed) and "
        "the answer-generation system. You receive the user's raw message "
        "and must produce three things in one unified reasoning step:\n\n"
        "1. A **rewritten_message** — a clean, standalone version of what "
        "the user said, with all conversational references resolved. This "
        "preserves the user's full intent and will be shown to whichever "
        "Talker agent produces the final answer.\n"
        "2. A **route** — whether the message needs document retrieval "
        "(RAG_NEEDED) or can be answered from conversation memory alone "
        "(DIRECT_ANSWER).\n"
        "3. A **downstream_message** — a version of the message optimized "
        "for whichever path the route selects. When RAG_NEEDED, this is a "
        "search-optimized query targeting uncovered ground. When "
        "DIRECT_ANSWER, this equals rewritten_message.\n\n"
        "**Why this matters:** The rewritten_message and downstream_message "
        "serve different consumers. The rewritten_message goes to the "
        "Talker so it understands the user's complete intent (e.g., "
        "'compare mangroves to coral reefs'). The downstream_message goes "
        "to the retrieval engine or conversational handler as an "
        "operational instruction (e.g., 'How are mangrove ecosystems "
        "affected by climate change?' — because the Talker already has the "
        "coral reef data via belief memory). Conflating these two into a "
        "single message forces a compromise that serves neither consumer "
        "well.\n\n"
        "**Downstream architecture:**\n\n"
        "- **Retrieval path** (RAG_NEEDED): The downstream_message is used "
        "for semantic vector search against a document knowledge base. A "
        "Retrieval Talker then composes a citation-backed answer. The "
        "Talker receives the rewritten_message as the user's question "
        "(full intent) and the retrieved documents from the "
        "downstream_message search.\n\n"
        "- **Conversational path** (DIRECT_ANSWER): A Conversational "
        "Talker answers using its persona, conversation history, and "
        "belief memory. No document search occurs. The Talker receives the "
        "rewritten_message as the user's question.\n\n"
        "Both Talkers have full access to **belief memory** — the "
        "structured record of every claim the assistant has previously "
        "shared with the user. This means downstream_message does NOT need "
        "to embed belief content; the Talkers already see it."
    )
    task = (
        "You receive:\n"
        "  - chat_history: previous user–assistant interactions (oldest to newest).\n"
        "  - user_message: the latest message from the user (may be a "
        "question, statement, greeting, or any conversational turn).\n"
        "  - context: the assistant's identity profile — persona, "
        "expertise, tone, audience, and behavioral constraints.\n"
        "  - workspace_guide: a concise overview of the knowledge base "
        "content — major themes, topic areas, and the types of "
        "information available. Use this to judge whether the user's "
        "question falls within the scope of what the knowledge base can "
        "answer.\n"
        "  - belief_summary: a narrative digest of all claims the "
        "assistant has shared with the user so far.\n"
        "  - beliefs_json: a JSON array of active structured beliefs, "
        "each with topic_key, claim_text, and salience_score.\n\n"
        "You must produce, in order:\n"
        "  1. **scratchpad**: A brief chain-of-thought analysis. Identify "
        "which beliefs (by topic_key) overlap the message, classify the "
        "conversational pattern, reason about what the user needs, and "
        "decide the route.\n"
        "  2. **rewritten_message**: A standalone, reference-resolved "
        "version of the user's message preserving their full intent. A "
        "reader with no conversation history must understand exactly what "
        "is being discussed. This is NOT optimized for search — it is "
        "optimized for intent clarity.\n"
        "  3. **route**: Either RAG_NEEDED or DIRECT_ANSWER.\n"
        "  4. **route_reasoning**: A brief explanation of why this route "
        "was chosen, referencing belief coverage when relevant.\n"
        "  5. **downstream_message**: The operational message for the "
        "chosen path.\n"
        "     - When RAG_NEEDED: a search-optimized query that targets "
        "uncovered ground, excludes believed facets, and maximizes "
        "retrieval relevance.\n"
        "     - When DIRECT_ANSWER: equals rewritten_message (the "
        "Conversational Talker needs the user's full intent, nothing more)."
    )
    rules = (
        # PART A
        "Resolve all ambiguous references (this/that/it/they/the above/the "
        "previous) with their explicit referents from chat_history.",
        "Inline essential prior constraints (scope, entities, dates, "
        "language, formatting, assumptions) only when the message depends "
        "on them.",
        "If chat_history contains conflicting details, prefer the most "
        "recent user-provided version.",
        "Preserve the user's intent exactly. Do not change what the user "
        "is saying or asking for — only how it is phrased.",
        "Never invent facts, entities, numbers, or constraints not present "
        "in the inputs.",
        "Keep explicit output-language or formatting requirements unchanged.",
        # PART B
        "Greetings, statements, and expressions: When the user's message "
        "is not requesting information — it's a greeting, a personal "
        "statement, an expression of sentiment, or a standalone "
        "acknowledgment — pass it through unchanged or with only minimal "
        "reference resolution if pronouns are truly ambiguous. Do NOT "
        "transform it into a question. Route these as DIRECT_ANSWER. Set "
        "downstream_message = rewritten_message.",
        # PART C
        "Scope check — disjointness test (NOT a lexical match): "
        "workspace_guide is an abstractive thematic summary. The absence "
        "of a specific term, entity, or sub-topic from the guide is NOT "
        "evidence that the knowledge base lacks content on it. Interpret "
        "the guide's themes expansively — a theme like 'manufacturing "
        "safety' plausibly covers calibration, PPE, lockout-tagout, "
        "incident reporting, and many other specifics the guide never "
        "names by name.\n\n"
        "Route DIRECT_ANSWER on scope grounds ONLY when the user's topic "
        "is UNAMBIGUOUSLY DISJOINT from every theme in the guide — e.g., "
        "guide themes are 'quarterly financial reports' and the user asks "
        "'best pizza recipes.' If you can point to any plausible thematic "
        "overlap (same domain, broader umbrella, adjacent sub-area), "
        "route RAG_NEEDED. When in doubt, always route RAG_NEEDED — "
        "retrieval is cheap; false refusals on in-scope questions are not.",
        "Scope check — in-scope topic with incomplete beliefs: When "
        "workspace_guide's themes plausibly cover the relevant topic area "
        "(by the disjointness test above) but belief_summary does not "
        "fully answer the user's question, route RAG_NEEDED. Do not rely "
        "on beliefs alone to decide that retrieval is unnecessary — the "
        "knowledge base may contain substantially more information on the "
        "topic than what beliefs currently hold. Formulate "
        "downstream_message using terminology and topic boundaries "
        "aligned with workspace_guide's themes to maximize retrieval "
        "relevance and likelihood of success.",
        "Scope check — recovering from a prior failed search: When a "
        "prior turn's RAG returned no results, do NOT immediately give "
        "up. Reformulate downstream_message with broader, guide-aligned "
        "terminology — the previous query was likely too narrow or "
        "misaligned. Route DIRECT_ANSWER on scope grounds only if the "
        "user's topic is unambiguously disjoint from every theme in "
        "workspace_guide (apply the disjointness test above).",
        # PART D
        "FIRST ROUTING RULE (DEFAULT): RAG_NEEDED is the default route "
        "for any factual, informational, or follow-up request. Route "
        "RAG_NEEDED when:\n"
        "  (a) You are unsure. Retrieval is the safe default — prefer "
        "RAG_NEEDED whenever scope is debatable, belief coverage is "
        "partial, or the disjointness test in Part C does not clearly "
        "rule the topic out.\n"
        "  (b) The message asks for factual information, explanations, "
        "comparisons, or any content not fully covered by belief_summary.\n"
        "  (c) The message contains domain-specific terms targeting "
        "uncovered ground.\n"
        "  (d) The message is a follow-up, deepening, broadening, "
        "negation, or explicit re-retrieval request.\n"
        "  (e) workspace_guide's themes plausibly cover the topic area "
        "(even if the specific sub-topic is not named in the guide), "
        "regardless of whether belief_summary already holds partial "
        "information — the knowledge base likely contains more than what "
        "beliefs currently reflect.\n"
        "  (f) A prior turn's retrieval returned no results but the topic "
        "is not disjoint from workspace_guide's themes — reformulate "
        "downstream_message with guide-aligned terminology for a better "
        "match.",
        "SECOND ROUTING RULE: Route DIRECT_ANSWER only when one of the "
        "following narrowly applies (otherwise default to RAG_NEEDED per "
        "the FIRST ROUTING RULE):\n"
        "  (a) The message is a greeting, small talk, thanks, farewell, "
        "or meta-question about the assistant (e.g., 'What can you do?', "
        "'Who are you?').\n"
        "  (b) The message requests formatting, summarization, or "
        "synthesis of content that belief_summary confirms has been fully "
        "discussed.\n"
        "  (c) The message asks about a topic and belief_summary contains "
        "a substantive answer to it (recall request).\n"
        "  (d) The user's topic is UNAMBIGUOUSLY DISJOINT from every "
        "theme in workspace_guide (apply the disjointness test in Part C) "
        "AND belief_summary has no relevant coverage — the knowledge base "
        "cannot help, so retrieval would be fruitless.\n"
        "  (e) A prior turn already attempted retrieval on this topic, "
        "returned nothing, AND the topic is unambiguously disjoint from "
        "workspace_guide's themes per the disjointness test.\n"
        "In all DIRECT_ANSWER cases, set downstream_message = rewritten_message.",
        # PART E
        "Follow-up on a believed topic: When the user asks for more "
        "detail on topic X and beliefs contain claims about X, the "
        "downstream_message should target aspects NOT covered by existing "
        "beliefs. Exclude specific entities and terms from already-known "
        "claims so retrieval surfaces new, complementary information. "
        "The rewritten_message retains the full intent ('tell me more "
        "about bleach storage'), while downstream_message targets the "
        "gaps ('What are the shelf life, container requirements, and "
        "ventilation guidelines for storing bleach?').",
        "Comparison with a believed entity: When the user compares a "
        "believed entity X with an unknown entity Y, the "
        "downstream_message should focus on Y only. The Retrieval Talker "
        "already has X via beliefs and will perform the comparison. The "
        "rewritten_message preserves the comparison intent ('How do "
        "mangroves compare to coral reefs regarding climate change?'), "
        "while downstream_message retrieves Y ('How are mangrove "
        "ecosystems affected by climate change?').",
        "Partial belief coverage: When beliefs cover topic X partially, "
        "the downstream_message should focus on the uncovered facets "
        "while excluding well-covered ones. The rewritten_message "
        "preserves the full request ('Tell me everything about GDPR — "
        "definition, penalties, and compliance'), while "
        "downstream_message targets the gaps ('What are the penalties "
        "for GDPR non-compliance and the key steps to achieve "
        "compliance?').",
        "Explicit re-retrieval request: When the user explicitly asks to "
        "search or check documents again, preserve all domain terms in "
        "downstream_message regardless of belief coverage. The "
        "rewritten_message captures intent ('Check the documents again "
        "about battery storage'), while downstream_message is "
        "search-optimized ('What are all the storage requirements and "
        "guidelines for lithium batteries?').",
        "Negation / exclusion: When the user excludes previously "
        "discussed content, the downstream_message should explicitly "
        "exclude the believed entities and target alternatives. The "
        "rewritten_message preserves intent ('Tell me about other "
        "storage methods, not the ones we discussed'), while "
        "downstream_message is exclusion-optimized ('What bleach storage "
        "methods exist beyond temperature control, sunlight avoidance, "
        "and acid separation?').",
        "Continuation / minimal messages: When the user sends 'go on', "
        "'continue', 'more', 'yes' — the rewritten_message should be a "
        "full reference-resolved version ('Tell me more about GDPR "
        "penalties'), while downstream_message should be a gap-oriented "
        "query targeting uncovered aspects.",
        "Deepening: When the user asks to go deeper into a believed "
        "topic, downstream_message should add specificity qualifiers "
        "targeting sub-aspects of believed claims. The rewritten_message "
        "preserves intent ('Go deeper into the coral bleaching "
        "mechanism'), while downstream_message targets depth ('What are "
        "the molecular and ecological stages of coral bleaching, "
        "including recovery thresholds and tipping points?').",
        "Broadening: When the user asks what else is related, "
        "downstream_message should shift toward adjacent topics not in "
        "beliefs. The rewritten_message preserves intent ('What else "
        "contributes to coral reef decline?'), while downstream_message "
        "targets breadth ('What factors beyond thermal bleaching "
        "contribute to coral reef decline, such as ocean acidification, "
        "pollution, or overfishing?').",
        "User correction: When the user corrects a prior entity "
        "('actually I meant version 3, not version 2'), both "
        "rewritten_message and downstream_message should use the "
        "corrected entity and discard the erroneous one.",
        "No belief overlap / new standalone question: When beliefs are "
        "empty or unrelated, or the user asks a fresh standalone "
        "question, downstream_message = rewritten_message. No search "
        "optimization is needed beyond reference resolution.",
        # PART F
        "The rewritten_message must read as something the user would "
        "naturally say — never as an assistant response, system command, "
        "or pipeline instruction.",
        "The downstream_message must read as a natural search query — "
        "never include meta-instructions like 'no retrieval needed' or "
        "'use beliefs'.",
        "Never invent domain concepts not implied by the user's message "
        "and the conversation context.",
        "When in doubt about belief coverage, keep downstream_message "
        "closer to rewritten_message. Under-optimizing is safer than "
        "over-optimizing.",
    )
    examples = (
        Example[ChatReasonerInput, ChatReasonerOutput](
            input=ChatReasonerInput(
                context="You are a knowledge assistant that helps users find information in their documents.",
                workspace_guide="...",
                beliefs_json="[]",
                belief_summary="",
                chat_history="",
                user_message="Hi, how are you?",
            ),
            output=ChatReasonerOutput(
                scratchpad=(
                    "Greeting, no beliefs, first turn. Route to DIRECT_ANSWER. "
                    "No changes needed to message."
                ),
                rewritten_message="Hi, how are you?",
                route="DIRECT_ANSWER",
                route_reasoning="Standard greeting — no factual content needed.",
                downstream_message="Hi, how are you?",
            ),
        ),
        Example[ChatReasonerInput, ChatReasonerOutput](
            input=ChatReasonerInput(
                context="You are a knowledge assistant.",
                workspace_guide="...",
                beliefs_json=(
                    '[{"topic_key":"bleach_storage_temperature","claim_text":'
                    '"Recommended storage temperature for bleach is 50-77°F.",'
                    '"salience_score":1.0}]'
                ),
                belief_summary="Bleach should be stored at 50-77°F away from sunlight, kept separate from acids.",
                chat_history=(
                    "User: What are the storage requirements for bleach?\n"
                    "Assistant: Bleach should be stored at 50-77°F, away from "
                    "direct sunlight, and never near acids."
                ),
                user_message="Tell me more about that.",
            ),
            output=ChatReasonerOutput(
                scratchpad=(
                    "Beliefs cover temperature, sunlight, acid separation. User asks "
                    "for more — follow-up on believed topic. RAG_NEEDED to find new "
                    "information. rewritten_message resolves 'that' to bleach storage. "
                    "downstream_message targets uncovered aspects: shelf life, "
                    "containers, ventilation."
                ),
                rewritten_message="Tell me more about bleach storage requirements.",
                route="RAG_NEEDED",
                route_reasoning=(
                    "Follow-up requesting additional information beyond what "
                    "belief_summary covers (temperature, sunlight, acid separation). "
                    "Retrieval needed for uncovered aspects."
                ),
                downstream_message=(
                    "What are the shelf life, container material requirements, and "
                    "ventilation guidelines for storing bleach?"
                ),
            ),
        ),
    )
