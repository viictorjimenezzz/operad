"""Whole-PR diff summarizer LLM leaf."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import DiffChunk, PRDiff, PRSummary


class DiffSummarizer(Agent[PRDiff, PRSummary]):
    """Summarize a pull request diff at a glance.

    Emits a one-line headline and a bulleted list of logical changes.
    Operates on the whole ``PRDiff`` in a single LLM call.
    """

    input = PRDiff
    output = PRSummary

    role = "You summarize pull request diffs at a glance."
    task = (
        "Read the full PR diff and produce a one-line headline plus a "
        "bulleted list of logical changes."
    )
    rules = (
        "Keep the headline under 70 characters.",
        "One bullet per logical change, not per file.",
        "Do not fabricate intent the diff does not evidence.",
    )
    examples = (
        Example[PRDiff, PRSummary](
            input=PRDiff(
                chunks=[
                    DiffChunk(
                        path="svc/auth.py",
                        old="return t",
                        new="return t or ''",
                    ),
                    DiffChunk(
                        path="tests/test_auth.py",
                        old="",
                        new="def test_empty_token(): ...",
                    ),
                ]
            ),
            output=PRSummary(
                headline="Tolerate missing auth tokens and cover with a test",
                changes=[
                    "Return empty string for missing auth token",
                    "Add regression test for the empty-token case",
                ],
            ),
        ),
    )
