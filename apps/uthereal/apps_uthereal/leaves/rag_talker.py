from __future__ import annotations

"""RAG answer talker leaf.

Owner: 2-1-operad-leaves.
"""

from operad import Agent

from apps_uthereal.schemas.talker import RAGTalkerInput, RAGTalkerOutput


class RAGTalkerLeaf(Agent[RAGTalkerInput, RAGTalkerOutput]):
    """Writes the final retrieval-grounded answer."""

    input = RAGTalkerInput
    output = RAGTalkerOutput
