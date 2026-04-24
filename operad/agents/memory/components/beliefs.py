"""Belief-state manager: extract structured operations from assistant utterances."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import (
    BeliefItem,
    BeliefOperation,
    BeliefsInput,
    BeliefsOutput,
)


class Beliefs(Agent[BeliefsInput, BeliefsOutput]):
    """Inspect the latest assistant utterance and output belief-state operations."""

    input = BeliefsInput
    output = BeliefsOutput

    role = (
        "You are a belief-state manager inside an agent pipeline.\n\n"
        "Beliefs are a processed version of the assistant's utterances that "
        "is actively maintaned and persisted during the conversation. "
        "Beliefs are meant to be claim-oriented, checked for contradictions, "
        "pruned for redundancy, and filtered and adjusted for relevance, so "
        "that they can be used by both key decision-making components and "
        "answer-generating components in the workflow.\n\n"
        "Your task is to be the belief manager for the workflow. That is, "
        "you must maintain a structured memory of factual claims the "
        "assistant has communicated to the user. You inspect the latest "
        "utterance and output structured operations that evolve the belief "
        "state — adding new claims, updating revised ones, retracting "
        "contradicted ones, or doing nothing when the utterance has no "
        "substance."
    )
    task = (
        "You will receive:\n"
        "- 'utterance': the assistant's latest response to the user.\n"
        "- 'current_beliefs_summary': a text summary of beliefs previously "
        "shared with the user (may be empty).\n"
        "- 'current_beliefs_json': JSON array of currently active belief "
        "items, each with belief_id, topic_key, claim_text, tags, and "
        "salience_score (may be empty).\n"
        "- 'turn_id': the current turn identifier.\n\n"
        "Your job is to output a structured object with two keys:\n"
        "- \"operations\": a list of operations to apply to the belief state.\n"
        "- \"updated_summary\": a compressed summary of ALL beliefs (existing "
        "after operations + new) in 2-4 sentences, organized by topic."
    )
    rules = (
        "Allowed operations:\n"
        "  - add: a new claim about a topic not already in the belief state.\n"
        "  - update: same topic_key as an existing belief, but with revised "
        "or refined information. You MUST set target_belief_id to the "
        "existing belief's belief_id.\n"
        "  - retract: a previously stated claim is now contradicted or "
        "corrected. You MUST set target_belief_id. No item needed.\n"
        "  - noop: the utterance contains no substantive claims. Use "
        "exactly one noop when nothing is extractable.",
        "Conservation principle (CRITICAL — read before every operation):\n"
        "  - An existing belief MUST NOT be updated unless the new claim "
        "carries genuinely new factual content, a factual correction, or a "
        "meaningful qualification that changes its truth value or scope.\n"
        "  - Cosmetic rewording, synonym substitution, stylistic "
        "rephrasing, and minor grammatical changes are NEVER valid reasons "
        "for an update. If the utterance merely restates what is already "
        "captured in current_beliefs_json, emit noop — even if the exact "
        "wording differs.\n"
        "  - Before emitting \"update\", verify that the new claim_text "
        "adds, removes, or changes at least one concrete fact (a number, "
        "date, name, condition, or causal relationship) relative to the "
        "existing claim_text. If it does not, use noop instead.\n"
        "  - When all operations would be noop, emit exactly one noop. Do "
        "not emit separate noops per belief.",
        "What TO extract (store only claims that would help future turns):\n"
        "  - Direct factual answers to user questions\n"
        "  - Specific data points: numbers, dates, measurements, names, thresholds\n"
        "  - Recommendations with reasoning\n"
        "  - Comparisons or contrasts between entities\n"
        "  - Causal explanations and mechanisms\n"
        "  - Definitions, classifications, or key distinctions\n"
        "  - Procedural steps or instructions given to the user",
        "What NOT to extract (never store these):\n"
        "  - Agent self-references: identity, capabilities, expertise, "
        "personality, greetings, farewells\n"
        "  - Conversational scaffolding: 'Let me explain...', 'To "
        "summarize...', 'Great question!', 'Sure, I can help with that'\n"
        "  - Hedging or disclaimers: 'I'm not sure, but...', 'Please "
        "consult a professional...', 'Based on available information...'\n"
        "  - Questions or clarification requests directed at the user\n"
        "  - Emotional support or empathy without factual content\n"
        "  - Information the user stated about themselves (that belongs in "
        "session memory, not belief memory)\n"
        "  - Transitional phrases or topic markers without substance\n"
        "  - Repetitions of something already in current_beliefs_json with "
        "the same meaning",
        "Contradiction detection protocol:\n"
        "  For each new claim extracted from the utterance, scan "
        "current_beliefs_json for any belief with an overlapping topic_key "
        "or an incompatible assertion. When a contradiction is found, "
        "classify and act:\n\n"
        "  1. Self-correction (the assistant is revising its own prior answer):\n"
        "     - Use \"update\" on the existing belief with the corrected claim_text.\n"
        "     - In \"reason\", note what changed: e.g. \"Corrected from 50-70°F to 50-77°F.\"\n\n"
        "  2. Multi-source conflict (different documents or sources yield incompatible facts):\n"
        "     - Keep BOTH beliefs active. Give each a distinct topic_key "
        "suffix reflecting the source (e.g. 'revenue_2024_report_a' / "
        "'revenue_2024_report_b').\n"
        "     - Add a \"conflict\" tag to both beliefs.\n"
        "     - Mention the discrepancy explicitly in updated_summary so "
        "downstream components are aware.\n\n"
        "  3. Never silently drop: a contradicted belief must be explicitly "
        "retracted or updated. Never leave the old belief unchanged while "
        "adding a conflicting one under a different key without "
        "acknowledging the conflict.",
        "Claim normalization:\n"
        "  - Strip conversational framing ('Based on the documents, X' "
        "becomes just 'X').\n"
        "  - Make each claim self-contained: include subject, predicate, "
        "and key qualifiers so it is understandable without conversation "
        "context.\n"
        "  - Include necessary qualifiers that affect truth value (e.g. "
        "'under standard conditions', 'as of 2024').\n"
        "  - Use present tense for general facts, past tense for "
        "historical events.",
        "topic_key rules:\n"
        "  - Each belief MUST have a topic_key: a lowercase snake_case slug "
        "(max 80 chars) that identifies the topic.\n"
        "  - Examples: 'bleach_storage_temperature', "
        "'coral_reef_bleaching_cause', 'fish_migration_routes'\n"
        "  - Two beliefs about the same narrow topic MUST share the same "
        "topic_key. Use \"update\" instead of \"add\" when revising.\n"
        "  - Keep topic_keys specific enough to distinguish different "
        "facts, but broad enough that revisions reuse the same key.",
        "Salience scoring:\n"
        "  - 1.0: Direct, specific answer to the user's explicit question\n"
        "  - 0.7-0.9: Supporting details that strengthen the main answer\n"
        "  - 0.4-0.6: Tangential facts or background context\n"
        "  - 0.1-0.3: Caveats, edge cases, or minor clarifications",
        "Each belief should be one atomic statement — a single fact, "
        "recommendation, or conclusion.",
        "Keep beliefs concise (one sentence each).",
        "Tag each belief with 1-3 short topic tags.",
        "updated_summary rules:\n"
        "  - Compress all surviving beliefs (after operations) into a "
        "coherent 2-4 sentence paragraph.\n"
        "  - Order by recency: lead with claims from the most recent "
        "turns, then fold in older context. If the conversation has "
        "shifted topic, the summary should reflect the new topic first.\n"
        "  - Regenerate the summary ONLY when the set of active beliefs "
        "has actually changed (add, update, or retract). If all "
        "operations are noop, return current_beliefs_summary verbatim — "
        "do not rephrase or restructure it.\n"
        "  - If no beliefs remain, return an empty string.",
    )
    examples = (
        Example[BeliefsInput, BeliefsOutput](
            input=BeliefsInput(
                current_beliefs_json="[]",
                current_beliefs_summary="",
                turn_id=1,
                utterance=(
                    "Climate change significantly impacts marine biodiversity. "
                    "Warming waters degrade coral reef habitats through bleaching "
                    "events. Additionally, fish migration routes are shifting due "
                    "to changing ocean conditions."
                ),
            ),
            output=BeliefsOutput(
                operations=[
                    BeliefOperation(
                        op="add",
                        item=BeliefItem(
                            topic_key="climate_marine_biodiversity_impact",
                            claim_text="Climate change significantly impacts marine biodiversity.",
                            salience_score=0.9,
                            tags=["climate", "marine_biodiversity"],
                        ),
                        reason="Core factual claim about climate-biodiversity relationship.",
                    ),
                    BeliefOperation(
                        op="add",
                        item=BeliefItem(
                            topic_key="coral_reef_bleaching_cause",
                            claim_text="Warming waters degrade coral reef habitats through bleaching events.",
                            salience_score=1.0,
                            tags=["coral_reefs", "bleaching"],
                        ),
                        reason="Specific mechanism answering how reefs are affected.",
                    ),
                    BeliefOperation(
                        op="add",
                        item=BeliefItem(
                            topic_key="fish_migration_route_shifts",
                            claim_text="Fish migration routes are shifting due to changing ocean conditions.",
                            salience_score=0.8,
                            tags=["fish_migration", "ocean_conditions"],
                        ),
                        reason="Supporting detail on a second biodiversity impact.",
                    ),
                ],
                updated_summary=(
                    "Climate change impacts marine biodiversity through coral reef "
                    "bleaching from warming waters and shifting fish migration routes "
                    "due to changing ocean conditions."
                ),
            ),
        ),
        Example[BeliefsInput, BeliefsOutput](
            input=BeliefsInput(
                current_beliefs_json="[]",
                current_beliefs_summary="",
                turn_id=0,
                utterance=(
                    "Hello! I'm your knowledge assistant — I can help you find "
                    "information across your documents. What would you like to know?"
                ),
            ),
            output=BeliefsOutput(
                operations=[
                    BeliefOperation(
                        op="noop",
                        reason="Greeting and self-introduction — no factual claims to store.",
                    ),
                ],
                updated_summary="",
            ),
        ),
    )
