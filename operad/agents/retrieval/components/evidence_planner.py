"""Evidence planner: produces supported claims for downstream answer generation."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import ClaimItem, EvidencePlannerInput, EvidencePlannerOutput


class EvidencePlanner(Agent[EvidencePlannerInput, EvidencePlannerOutput]):
    """Build an evidence-backed claim plan (supported claims + evidence ids)."""

    input = EvidencePlannerInput
    output = EvidencePlannerOutput

    role = (
        "You are an evidence planner for a retrieval-augmented QA system.\n"
        "You do NOT write the final answer. You ONLY produce a structured "
        "plan of supported claims."
    )
    task = (
        "You will receive the following inputs:\n"
        "  - \"query\": string (the user question)\n"
        "  - \"facts\": a pre-rendered string that groups text facts by "
        "their source document. Each document block begins with two header "
        "lines:\n\n"
        "        datasource_id: d-N\n"
        "        datasource_summary: <one-paragraph summary of that "
        "datasource, may be empty>\n\n"
        "    followed by one or more fact entries:\n\n"
        "        fact_id: f-M\n"
        "        text: <fact text>\n\n"
        "    Facts within a block appear in their original reading order "
        "(top to bottom, page by page). Blocks for different datasources "
        "are separated by blank lines. The `d-N` identifiers are for your "
        "reasoning context only — DO NOT emit them as evidence ids.\n\n"
        "Separately (outside the facts string), you may receive zero or "
        "more image attachments. If images are provided, they will be "
        "attached as distinct inputs labeled exactly 'Image i-0', 'Image "
        "i-1', ... You may cite images as evidence by using their id "
        "strings ('i-0', 'i-1', ...).\n\n"
        "Use the `datasource_summary` for each block only to understand "
        "the scope and intent of that document when judging relevance; do "
        "not treat it as a citable fact and do not quote it in claims.\n\n"
        "Your job is to produce a set of distinct, atomic, answer-relevant "
        "claims supported by the provided facts and/or images.\n\n"
        "Treat each claim's `scratchpad` as genuine chain-of-thought: "
        "write it first, use it to commit to the `claim` / `evidence` / "
        "`rationale` that follow, and do NOT retro-fit it to match a "
        "claim you have already decided on. If no claims are supported, "
        "return an empty `claim_sequence`.\n\n"
        "IMPORTANT: Prioritize relevance and precision:\n"
        "- Each claim MUST cite every fact (or image) that materially "
        "supports it or was used to derive it. Atomic claims typically "
        "cite 1 fact; composite or general claims that synthesize across "
        "multiple facts MUST cite all of them.\n"
        "- Do NOT pad `evidence` with tangential, redundant, or only "
        "weakly related items.\n"
        "- A claim may still be split into smaller atomic claims when the "
        "underlying facts address genuinely distinct ideas — but do NOT "
        "force-split a single synthesized statement just to keep the "
        "`evidence` list short."
    )
    rules = (
        '"claim_id" MUST be a unique string identifier. Use the pattern '
        '"c-0", "c-1", ... in order.',
        '"scratchpad" MUST be a short (1-3 sentences) working note where '
        "you briefly discuss how you are constructing this claim and why "
        "you are selecting these specific evidence ids. Keep it "
        "internal-facing: do NOT address the user, do NOT restate the full "
        "claim verbatim, and do NOT add information that is not supported "
        "by the evidence.",
        '"claim" MUST be a clear, self-contained statement written as a '
        "plain sentence. It MAY be atomic (single idea) or "
        "composite/general (a synthesis across multiple facts), as long as "
        "every assertion it makes is supported by the listed `evidence`.",
        '"evidence" MUST be a non-empty JSON array of strings, each being '
        'a fact ID ("f-M") or image ID ("i-K") present in the inputs. '
        "Order does not matter.",
        "Do NOT invent evidence ids. Do NOT reference ids not present in "
        "the input facts or image attachments.",
        'If images are not provided, do NOT reference any "i-*" ids.',
        "NEVER cite a `d-*` datasource id as evidence — only `f-*` fact "
        "ids and `i-*` image ids are valid entries in `evidence`.",
        "Do NOT include duplicate ids within a single `evidence` list.",
        '"rationale" MUST be 1-2 sentences explaining how the cited facts '
        "together support this claim. Focus on the logical link between "
        "the evidence content and the assertion. Do NOT reference evidence "
        'by its id (e.g. "f-0", "i-1"); instead, refer to them in general '
        "language such as 'one of the facts', 'the first fact', 'both "
        "facts', 'the image', etc.",
        "Do NOT quote evidence verbatim; paraphrase into claims.",
        "Do NOT use external knowledge. If a detail is not supported by "
        "the provided evidence, do not claim it.",
        "Evidence selection constraint (CRITICAL):\n"
        "- Every claim MUST be fully grounded: each assertion inside "
        "`claim` must be traceable to at least one id in `evidence`.\n"
        "- `evidence` MUST list every fact/image that materially supports "
        "or was used to derive the claim — do NOT omit relevant "
        "supporting facts.\n"
        "- `evidence` MUST NOT contain tangential, redundant, or only "
        "weakly related ids — only include what genuinely supports the "
        "claim.\n"
        "- Prefer atomic claims (one idea, typically 1-2 facts) when the "
        "underlying evidence addresses genuinely distinct ideas.\n"
        "- Prefer composite/general claims (one synthesized statement "
        "with multiple facts) when several facts jointly express a single "
        "coherent idea, shared pattern, or consolidated finding. Do NOT "
        "artificially fragment a synthesis into many near-duplicate "
        "claims just to shrink each `evidence` list.\n"
        "- If an id would appear in several claims, that is fine — reuse "
        "ids across claims when genuinely relevant to each.",
        "Relevance objective (most important):\n"
        "- Focus on what directly answers the query.\n"
        "- Prefer evidence that contains direct definitions, "
        "quantitative/causal statements, or explicit outcomes related to "
        "the query.\n"
        "- Ignore evidence that is generic background, tangential "
        "context, metadata, boilerplate, or only weakly related.",
        "Evidence utilization (relaxed):\n"
        "- You do NOT need to use every fact or image.\n"
        "- Use evidence only when it materially contributes to answering "
        "the query.\n"
        "- Evidence that is irrelevant or redundant SHOULD be left unused.",
        "Definitional / general queries rubric:\n"
        "If the query is definitional or general (e.g., 'What is X?', "
        "'Define X', 'Explain X'), produce claims (when supported by "
        "evidence) that cover:\n"
        "- a definition/characterization of X\n"
        "- scope/boundaries (what it includes/excludes)\n"
        "- purpose/why it matters\n"
        "- key concepts/components\n"
        "- typical methods/activities/processes\n"
        "- common applications/examples\n"
        "- related/adjacent terms (synonyms, subfields, contrasts)\n"
        "Only include facets that are supported by the provided evidence.",
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
