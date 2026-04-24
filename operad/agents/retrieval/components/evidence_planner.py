"""Evidence planner: produces supported claims for downstream answer generation."""

from __future__ import annotations

from inspect import cleandoc

from ....core.agent import Agent, Example
from ..schemas import ClaimItem, EvidencePlannerInput, EvidencePlannerOutput


class EvidencePlanner(Agent[EvidencePlannerInput, EvidencePlannerOutput]):
    """Build an evidence-backed claim plan (supported claims + evidence ids)."""

    input = EvidencePlannerInput
    output = EvidencePlannerOutput

    role = cleandoc("""
        You are an evidence planner for a retrieval-augmented QA
        system. You do NOT write the final answer. You ONLY produce a
        structured plan of supported claims.
    """)
    task = cleandoc("""
        Produce a set of distinct, answer-relevant claims supported by
        the provided facts (and images, when available).

        The `facts` field is a pre-rendered string grouping text facts
        by source document. Each block begins with two header lines:

            datasource_id: d-N
            datasource_summary: <one-paragraph summary of the
            datasource, may be empty>

        followed by one or more fact entries:

            fact_id: f-M
            text: <fact text>

        Facts within a block are in original reading order. Blocks for
        different datasources are separated by blank lines. Use
        `datasource_summary` only to judge relevance — do not quote it
        and do not emit `d-N` as an evidence id.

        Images (when provided) arrive as separate inputs labelled
        exactly "Image i-0", "Image i-1", … Cite them in evidence as
        "i-0", "i-1", ….

        Treat each claim's `scratchpad` as genuine chain-of-thought:
        write it first, use it to commit to the `claim` / `evidence` /
        `rationale` that follow, and do NOT retro-fit it. If no claims
        are supported, return an empty `claim_sequence`.

        Prioritise relevance and precision:
        - Each claim MUST cite every fact (or image) that materially
          supports it. Atomic claims typically cite 1 fact; composite
          claims MUST cite all synthesised facts.
        - Do NOT pad `evidence` with tangential, redundant, or weakly
          related items.
        - Split into smaller atomic claims when the underlying facts
          address genuinely distinct ideas — but do NOT force-split a
          single synthesised statement just to keep evidence short.
    """)
    rules = (
        '"claim_id" MUST be a unique string identifier. Use the pattern '
        '"c-0", "c-1", ... in order.',
        cleandoc("""
            "scratchpad" MUST be a short (1-3 sentences) working note
            where you briefly discuss how you are constructing this
            claim and why you are selecting these specific evidence
            ids. Keep it internal-facing: do NOT address the user, do
            NOT restate the full claim verbatim, and do NOT add
            information that is not supported by the evidence.
        """),
        cleandoc("""
            "claim" MUST be a clear, self-contained statement written
            as a plain sentence. It MAY be atomic (single idea) or
            composite/general (a synthesis across multiple facts), as
            long as every assertion it makes is supported by the
            listed `evidence`.
        """),
        '"evidence" MUST be a non-empty JSON array of strings, each being '
        'a fact ID ("f-M") or image ID ("i-K") present in the inputs. '
        "Order does not matter.",
        "Do NOT invent evidence ids. Do NOT reference ids not present in "
        "the input facts or image attachments.",
        'If images are not provided, do NOT reference any "i-*" ids.',
        "NEVER cite a `d-*` datasource id as evidence — only `f-*` fact "
        "ids and `i-*` image ids are valid entries in `evidence`.",
        "Do NOT include duplicate ids within a single `evidence` list.",
        cleandoc("""
            "rationale" MUST be 1-2 sentences explaining how the cited
            facts together support this claim. Focus on the logical
            link between the evidence content and the assertion. Do
            NOT reference evidence by its id (e.g. "f-0", "i-1");
            instead, refer to them in general language such as "one of
            the facts", "the first fact", "both facts", "the image",
            etc.
        """),
        "Do NOT quote evidence verbatim; paraphrase into claims.",
        "Do NOT use external knowledge. If a detail is not supported by "
        "the provided evidence, do not claim it.",
        cleandoc("""
            Evidence selection constraint (CRITICAL):
              - Every claim MUST be fully grounded: each assertion inside `claim` must be traceable to at least one id in `evidence`.
              - `evidence` MUST list every fact/image that materially supports or was used to derive the claim — do NOT omit relevant supporting facts.
              - `evidence` MUST NOT contain tangential, redundant, or only weakly related ids — only include what genuinely supports the claim.
              - Prefer atomic claims (one idea, typically 1-2 facts) when the underlying evidence addresses genuinely distinct ideas.
              - Prefer composite/general claims (one synthesised statement with multiple facts) when several facts jointly express a single coherent idea, shared pattern, or consolidated finding. Do NOT artificially fragment a synthesis into many near-duplicate claims just to shrink each `evidence` list.
              - If an id would appear in several claims, that is fine — reuse ids across claims when genuinely relevant to each.
        """),
        cleandoc("""
            Relevance objective (most important):
              - Focus on what directly answers the query.
              - Prefer evidence that contains direct definitions, quantitative/causal statements, or explicit outcomes related to the query.
              - Ignore evidence that is generic background, tangential context, metadata, boilerplate, or only weakly related.
        """),
        cleandoc("""
            Evidence utilisation (relaxed):
              - You do NOT need to use every fact or image.
              - Use evidence only when it materially contributes to answering the query.
              - Evidence that is irrelevant or redundant SHOULD be left unused.
        """),
        cleandoc("""
            Definitional / general queries rubric:
            If the query is definitional or general (e.g. "What is X?",
            "Define X", "Explain X"), produce claims (when supported
            by evidence) that cover:
              - a definition/characterisation of X
              - scope/boundaries (what it includes/excludes)
              - purpose/why it matters
              - key concepts/components
              - typical methods/activities/processes
              - common applications/examples
              - related/adjacent terms (synonyms, subfields, contrasts)
            Only include facets that are supported by the provided evidence.
        """),
    )
    examples = (
        Example[EvidencePlannerInput, EvidencePlannerOutput](
            input=EvidencePlannerInput(
                query="What is the impact of climate change on marine biodiversity?",
                facts=(
                    "datasource_id: d-0\n"
                    "datasource_summary: Peer-reviewed review of climate-driven "
                    "changes in coral reef ecosystems.\n\n"
                    "fact_id: f-0\n"
                    "text: Rising sea temperatures increase coral bleaching and "
                    "contribute to sustained coral reef decline.\n\n"
                    "fact_id: f-1\n"
                    "text: Ocean acidification weakens coral skeletons and reduces "
                    "reef resilience to bleaching events.\n\n\n"
                    "datasource_id: d-1\n"
                    "datasource_summary: Survey of ocean current shifts and their "
                    "ecological effects on pelagic fish populations.\n\n"
                    "fact_id: f-2\n"
                    "text: Certain fish species have altered their migration routes "
                    "in response to shifting ocean currents linked to climate change.\n\n"
                    "fact_id: f-3\n"
                    "text: Redistribution of pelagic species has been observed to "
                    "alter predator-prey composition in affected regions."
                ),
            ),
            output=EvidencePlannerOutput(
                claim_sequence=[
                    ClaimItem(
                        claim_id="c-0",
                        scratchpad=(
                            "f-0 and f-1 both speak to coral reef degradation but "
                            "via distinct, reinforcing mechanisms (warming/bleaching "
                            "vs acidification/skeletal weakening); a single composite "
                            "claim captures the joint story better than two "
                            "near-duplicate atomic claims."
                        ),
                        claim=(
                            "Climate change degrades coral reef habitats through "
                            "compounding stressors — rising sea temperatures drive "
                            "bleaching and reef decline, while acidification further "
                            "weakens coral skeletons and reduces reef resilience."
                        ),
                        evidence=["f-0", "f-1"],
                        rationale=(
                            "The cited facts jointly describe two reinforcing "
                            "mechanisms — warming-driven bleaching and "
                            "acidification-driven skeletal weakening — that together "
                            "account for the overall reef degradation narrative."
                        ),
                    ),
                    ClaimItem(
                        claim_id="c-1",
                        scratchpad=(
                            "f-2 gives the migration-route shift and f-3 gives the "
                            "ecosystem-level consequence; they form a tight "
                            "cause-then-effect chain, so merging them into one claim "
                            "avoids stating either half in isolation."
                        ),
                        claim=(
                            "Climate-driven ocean changes redistribute pelagic "
                            "species by altering migration routes, which in turn "
                            "reshapes predator-prey composition in affected regions."
                        ),
                        evidence=["f-2", "f-3"],
                        rationale=(
                            "The first fact establishes the migration-route shift, "
                            "and the second extends it to the downstream ecosystem "
                            "effect of altered predator-prey composition — together "
                            "they support the full claim."
                        ),
                    ),
                ],
            ),
        ),
    )
