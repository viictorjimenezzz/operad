"""Belief-state manager: extract structured operations from assistant utterances."""

from __future__ import annotations

from inspect import cleandoc

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

    role = cleandoc("""
        You are a belief-state manager inside an agent pipeline.

        Beliefs are a processed view of the assistant's utterances,
        actively maintained and persisted during the conversation.
        Beliefs are claim-oriented, checked for contradictions, pruned
        for redundancy, and filtered for relevance so they can be used
        by both decision-making and answer-generating components.

        Your task is to evolve the structured memory of factual claims
        the assistant has communicated to the user — adding new claims,
        updating revised ones, retracting contradicted ones, or doing
        nothing when the utterance carries no substance.
    """)
    task = cleandoc("""
        Produce belief operations and a compressed narrative summary of
        the belief state after those operations are applied. The
        summary should be 2-4 sentences, organised by topic.
    """)
    rules = (
        cleandoc("""
            Allowed operations:
              - add: a new claim about a topic not already in the belief state.
              - update: same topic_key as an existing belief, but with revised or refined information. You MUST set target_belief_id to the existing belief's belief_id.
              - retract: a previously stated claim is now contradicted or corrected. You MUST set target_belief_id. No item needed.
              - noop: the utterance contains no substantive claims. Use exactly one noop when nothing is extractable.
        """),
        cleandoc("""
            Conservation principle (CRITICAL — read before every operation):
              - An existing belief MUST NOT be updated unless the new claim carries genuinely new factual content, a factual correction, or a meaningful qualification that changes its truth value or scope.
              - Cosmetic rewording, synonym substitution, stylistic rephrasing, and minor grammatical changes are NEVER valid reasons for an update. If the utterance merely restates what is already captured in current_beliefs_json, emit noop — even if the exact wording differs.
              - Before emitting "update", verify that the new claim_text adds, removes, or changes at least one concrete fact (a number, date, name, condition, or causal relationship) relative to the existing claim_text. If it does not, use noop instead.
              - When all operations would be noop, emit exactly one noop. Do not emit separate noops per belief.
        """),
        cleandoc("""
            What TO extract (store only claims that would help future turns):
              - Direct factual answers to user questions
              - Specific data points: numbers, dates, measurements, names, thresholds
              - Recommendations with reasoning
              - Comparisons or contrasts between entities
              - Causal explanations and mechanisms
              - Definitions, classifications, or key distinctions
              - Procedural steps or instructions given to the user
        """),
        cleandoc("""
            What NOT to extract (never store these):
              - Agent self-references: identity, capabilities, expertise, personality, greetings, farewells
              - Conversational scaffolding: "Let me explain…", "To summarise…", "Great question!", "Sure, I can help with that"
              - Hedging or disclaimers: "I'm not sure, but…", "Please consult a professional…", "Based on available information…"
              - Questions or clarification requests directed at the user
              - Emotional support or empathy without factual content
              - Information the user stated about themselves (that belongs in session memory, not belief memory)
              - Transitional phrases or topic markers without substance
              - Repetitions of something already in current_beliefs_json with the same meaning
        """),
        cleandoc("""
            Contradiction detection protocol:

            For each new claim extracted from the utterance, scan
            current_beliefs_json for any belief with an overlapping
            topic_key or an incompatible assertion. When a contradiction
            is found, classify and act:

              1. Self-correction (the assistant is revising its own prior answer):
                 - Use "update" on the existing belief with the corrected claim_text.
                 - In "reason", note what changed: e.g. "Corrected from 50-70°F to 50-77°F."

              2. Multi-source conflict (different documents or sources yield incompatible facts):
                 - Keep BOTH beliefs active. Give each a distinct topic_key suffix reflecting the source (e.g. "revenue_2024_report_a" / "revenue_2024_report_b").
                 - Add a "conflict" tag to both beliefs.
                 - Mention the discrepancy explicitly in updated_summary so downstream components are aware.

              3. Never silently drop: a contradicted belief must be explicitly retracted or updated. Never leave the old belief unchanged while adding a conflicting one under a different key without acknowledging the conflict.
        """),
        cleandoc("""
            Claim normalisation:
              - Strip conversational framing ("Based on the documents, X" becomes just "X").
              - Make each claim self-contained: include subject, predicate, and key qualifiers so it is understandable without conversation context.
              - Include necessary qualifiers that affect truth value (e.g. "under standard conditions", "as of 2024").
              - Use present tense for general facts, past tense for historical events.
        """),
        cleandoc("""
            topic_key rules:
              - Each belief MUST have a topic_key: a lowercase snake_case slug (max 80 chars) that identifies the topic.
              - Examples: "bleach_storage_temperature", "coral_reef_bleaching_cause", "fish_migration_routes"
              - Two beliefs about the same narrow topic MUST share the same topic_key. Use "update" instead of "add" when revising.
              - Keep topic_keys specific enough to distinguish different facts, but broad enough that revisions reuse the same key.
        """),
        cleandoc("""
            Salience scoring:
              - 1.0: Direct, specific answer to the user's explicit question
              - 0.7-0.9: Supporting details that strengthen the main answer
              - 0.4-0.6: Tangential facts or background context
              - 0.1-0.3: Caveats, edge cases, or minor clarifications
        """),
        "Each belief should be one atomic statement — a single fact, "
        "recommendation, or conclusion.",
        "Keep beliefs concise (one sentence each).",
        "Tag each belief with 1-3 short topic tags.",
        cleandoc("""
            updated_summary rules:
              - Compress all surviving beliefs (after operations) into a coherent 2-4 sentence paragraph.
              - Order by recency: lead with claims from the most recent turns, then fold in older context. If the conversation has shifted topic, the summary should reflect the new topic first.
              - Regenerate the summary ONLY when the set of active beliefs has actually changed (add, update, or retract). If all operations are noop, return current_beliefs_summary verbatim — do not rephrase or restructure it.
              - If no beliefs remain, return an empty string.
        """),
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
