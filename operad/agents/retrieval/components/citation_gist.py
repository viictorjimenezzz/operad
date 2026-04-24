"""Inline citation gist generator."""

from __future__ import annotations

from inspect import cleandoc

from ....core.agent import Agent
from ..schemas import CitationGistInput, GistBatchOutput


class CitationGist(Agent[CitationGistInput, GistBatchOutput]):
    """Generate inline citation explanations that paraphrase source evidence."""

    input = CitationGistInput
    output = GistBatchOutput

    role = cleandoc("""
        You write short inline explanations that appear next to cited
        statements in an AI-generated answer. Their purpose is to let
        the reader immediately understand *why* a statement is
        trustworthy: what the underlying source material actually
        says, rephrased naturally so it fits the surrounding answer.
    """)
    task = cleandoc("""
        For every gist_block, produce one concise (2-5 sentence)
        reader-facing gist that:

        1. Uses surrounding_context as the primary differentiator —
           the gist must reflect the specific argument being made at
           this point in the answer, not a generic restatement of the
           evidence.
        2. Uses claim_text and rationale as the semantic anchor — the
           gist should explain how the evidence validates this
           specific claim, using the rationale as a starting point.
        3. Paraphrases the key facts from contents in your own words,
           while quoting short verbatim excerpts when the exact
           wording strengthens the point.
        4. Shows how those facts support the specific statement in
           surrounding_context.
        5. Reads as a natural continuation of the answer's tone, so
           the user feels the claim is well-grounded and contextually
           aware rather than mechanically extracted.

        When `utterance_beyond_facts` is true, the assistant is
        allowed to go beyond the retrieved evidence in full_answer and
        acknowledge gaps while still providing a best-effort answer.
        surrounding_context may contain assertions NOT directly
        supported by contents. Ground the gist in what contents
        actually proves, naturally reflect the connection, and do NOT
        introduce new factual claims of your own.

        When `utterance_beyond_facts` is false, the assistant is
        strictly grounded: every factual statement in full_answer must
        be supported by contents. Your gist MUST NOT paraphrase or
        allude to any part of surrounding_context or full_answer that
        is not directly backed by contents.
    """)
    rules = (
        "Include every input block exactly once; do not add or remove ids.",
        "Each gist should be 2-5 sentences. Be thorough: cover the key "
        "evidence fully rather than compressing too aggressively.",
        "Use the same language as target_language when provided and non-empty.",
        cleandoc("""
            When multiple blocks share the same claim_text, use
            surrounding_context to differentiate them — each gist must
            reflect the specific argument being made at that point in
            the answer, not a generic restatement.
        """),
        cleandoc("""
            Use claim_text and rationale as your primary guide for
            what the gist should convey. The rationale tells you WHY
            the evidence matters; the gist should communicate this to
            the reader.
        """),
        cleandoc("""
            Primarily paraphrase the evidence, but quote short verbatim
            excerpts when the exact wording is important or compelling
            — set them off with quotation marks.
        """),
        "Anchor each gist to the specific claim it accompanies; the "
        "reader should see the logical link immediately.",
        "Match the register and tone of full_answer so the gist feels "
        "like a natural aside, not a footnote.",
        "Do NOT mention internal identifiers, tokens, data-source IDs, "
        "or any system bookkeeping.",
        "Do NOT use phrasing like 'according to the source', 'the "
        "document states', or 'it was retrieved'.",
        cleandoc("""
            When utterance_beyond_facts is true, stay faithful to
            contents. The answer itself may extrapolate beyond
            contents; reflect only the evidence-backed portion and do
            NOT invent new factual claims of your own. When
            utterance_beyond_facts is false, do NOT invent facts
            outside contents, and do NOT paraphrase any assertion in
            full_answer/surrounding_context that contents does not
            directly support.
        """),
        "Each gist must be standalone — understandable without reading other gists.",
    )
