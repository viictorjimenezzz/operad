"""PRReviewer: an end-to-end, typed pull-request review composition.

``ContextOptimizer`` enriches each chunk with surrounding code, then
``DiffSummarizer`` and ``CodeReviewer`` both read the enriched diff.
Their outputs are folded into a single ``ReviewReport`` whose
``summary`` is the summarizer's one-line headline and whose ``comments``
are the reviewer's localized notes.

Not a ``Sequential``: the summarizer and reviewer share an input rather
than chaining linearly, so the composition is expressed as a custom
composite with an explicit ``forward``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ...core.agent import Agent
from ..core.pipelines import Parallel, Sequential
from ...core.config import Configuration
from .components import CodeReviewer, ContextOptimizer, DiffSummarizer
from .components.context_optimizer import ReadFile
from .schemas import DiffChunk, PRDiff, PRSummary, ReviewComment, ReviewReport

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
        self._rebuild_pipeline()

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name in {"optimizer", "summarizer", "reviewer"}:
            keys = {"optimizer", "summarizer", "reviewer"}
            if keys.issubset(self.__dict__):
                self._rebuild_pipeline()

    def _rebuild_pipeline(self) -> None:
        self._fanout = Parallel(
            {"summary": self.summarizer, "review": self.reviewer},
            input=PRDiff,
            output=ReviewReport,
            combine=self._combine,
        )
        self.pipeline = Sequential(
            self.optimizer,
            self._fanout,
            input=PRDiff,
            output=ReviewReport,
        )

    def _combine(self, results: dict[str, BaseModel]) -> ReviewReport:
        summary = results["summary"]
        report = results["review"]
        return ReviewReport(
            comments=list(report.comments),  # type: ignore[attr-defined]
            summary=summary.headline,  # type: ignore[attr-defined]
        )

    async def forward(self, x: PRDiff) -> ReviewReport:  # type: ignore[override]
        return (await self.pipeline(x)).response
