"""PRReviewer: an end-to-end, typed pull-request review composition.

``ContextOptimizer`` enriches each chunk with surrounding code, then
``DiffSummarizer`` and ``CodeReviewer`` both read the enriched diff.
Their outputs are folded into a single ``ReviewReport`` whose
``summary`` is the summarizer's one-line headline and whose ``comments``
are the reviewer's localized notes.

Not a ``Pipeline``: the summarizer and reviewer share an input rather
than chaining linearly, so the composition is expressed as a custom
composite with an explicit ``forward``.
"""

from __future__ import annotations

from ...core.agent import Agent
from ...core.config import Configuration
from .components import CodeReviewer, ContextOptimizer, DiffSummarizer
from .components.context_optimizer import ReadFile
from .types import DiffChunk, PRDiff, PRSummary, ReviewComment, ReviewReport

__all__ = [
    "DiffChunk",
    "PRDiff",
    "PRReviewer",
    "PRSummary",
    "ReviewComment",
    "ReviewReport",
]


class PRReviewer(Agent[PRDiff, ReviewReport]):
    """Review a pull request end-to-end.

    Wires three leaves::

        ContextOptimizer   (PRDiff  -> PRDiff)
        DiffSummarizer     (PRDiff  -> PRSummary)
        CodeReviewer       (PRDiff  -> ReviewReport)

    and folds the summarizer's headline into the reviewer's report as
    the final ``ReviewReport.summary``.
    """

    input = PRDiff
    output = ReviewReport

    def __init__(self, *, config: Configuration, read_file: ReadFile) -> None:
        super().__init__(config=None, input=PRDiff, output=ReviewReport)
        self.optimizer = ContextOptimizer(read_file=read_file)
        self.summarizer = DiffSummarizer(config=config)
        self.reviewer = CodeReviewer(config=config)

    async def forward(self, x: PRDiff) -> ReviewReport:  # type: ignore[override]
        enriched = (await self.optimizer(x)).response
        summary = (await self.summarizer(enriched)).response
        report = (await self.reviewer(enriched)).response
        return ReviewReport(
            comments=list(report.comments),
            summary=summary.headline,
        )
