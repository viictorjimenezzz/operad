"""Relevance filter for retrieved facts."""

from __future__ import annotations

from inspect import cleandoc

from ....core.agent import Agent, Example
from ..schemas import FactFilterInput, FactFilterOutput


class FactFilter(Agent[FactFilterInput, FactFilterOutput]):
    """Pre-filter retrieved facts to keep only those directly relevant to the query."""

    input = FactFilterInput
    output = FactFilterOutput

    role = cleandoc("""
        You are a relevance filter for a retrieval-augmented QA
        system. You do NOT answer the query and you do NOT produce
        claims. You ONLY decide which retrieved facts are relevant
        enough to be passed to the downstream evidence planner.
    """)
    task = cleandoc("""
        Select the subset of fact_ids whose text is directly relevant
        to answering the query.

        Selection principles:

        - KEEP a fact if it contains information that could plausibly
          support, refute, define, quantify, exemplify, or otherwise
          directly inform an answer to the query.
        - DROP a fact if it is off-topic, generic boilerplate,
          tangential metadata, navigational text, or only
          weakly/associatively related.
        - When in doubt between "weakly related" and "clearly
          relevant", prefer to DROP — the downstream planner is
          expensive and benefits from a tight, high-signal set.
        - Do NOT deduplicate semantically similar facts here; keep all
          relevant facts even if they overlap. The downstream planner
          handles evidence selection.
        - Do NOT invent fact_ids. Only return IDs that appear in the
          input.
    """)
    rules = (
        "'fact_ids' MUST contain only integers that appear as fact_id values in the input.",
        "'fact_ids' MAY be empty if no fact is relevant.",
        "Do NOT include duplicates in 'fact_ids'.",
    )
    examples = (
        Example[FactFilterInput, FactFilterOutput](
            input=FactFilterInput(
                facts=(
                    "fact_id: 0\n"
                    "text: Rising sea temperatures increase coral bleaching and "
                    "contribute to sustained coral reef decline.\n\n"
                    "fact_id: 1\n"
                    "text: Certain fish species have altered their migration routes "
                    "in response to shifting ocean currents linked to climate change.\n\n"
                    "fact_id: 2\n"
                    "text: The conference on marine biology will be held in Lisbon "
                    "next spring.\n\n"
                    "fact_id: 3\n"
                    "text: Additional data on coral reef ecosystems and their inhabitants."
                ),
                query="What is the impact of climate change on marine biodiversity?",
            ),
            output=FactFilterOutput(fact_ids=[0, 1, 3]),
        ),
        Example[FactFilterInput, FactFilterOutput](
            input=FactFilterInput(
                facts=(
                    "fact_id: 0\n"
                    "text: Drug X is administered intravenously at a standard dose of 10 mg/kg.\n\n"
                    "fact_id: 1\n"
                    "text: The clinical trial enrolled 240 participants across 4 sites.\n\n"
                    "fact_id: 2\n"
                    "text: Reported adverse events for Drug X include mild nausea and transient headaches."
                ),
                query="What are the side effects of Drug X?",
            ),
            output=FactFilterOutput(fact_ids=[2]),
        ),
    )
