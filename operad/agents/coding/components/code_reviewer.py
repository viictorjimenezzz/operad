"""Whole-PR code-review LLM leaf."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import DiffChunk, PRDiff, ReviewComment, ReviewReport


class CodeReviewer(Agent[PRDiff, ReviewReport]):
    """Review an entire pull request in one LLM call.

    Takes the whole ``PRDiff`` so the reviewer can reason cross-file
    (e.g. a caller changed in one chunk, a callee in another). Each
    emitted ``ReviewComment`` carries its own ``path`` and ``line``, so
    downstream tools can still group comments per file.
    """

    input = PRDiff
    output = ReviewReport

    role = "You are a meticulous senior code reviewer."
    task = (
        "Read every diff chunk in the pull request and identify bugs, "
        "unsafe changes, missing tests, and clear style violations. Emit "
        "one ReviewComment per issue, citing the exact file path and line "
        "number, and end with a short narrative summary."
    )
    rules = (
        "Only comment when the issue is real; do not nitpick style if the "
        "codebase doesn't enforce it.",
        "Cite the exact file path and the 1-based line number in the "
        "post-change file for every comment.",
        "Classify severity strictly as 'info', 'warning', or 'error'.",
        "If a chunk is clean, do not invent comments for it.",
    )
    examples = (
        Example[PRDiff, ReviewReport](
            input=PRDiff(
                chunks=[
                    DiffChunk(
                        path="svc/auth.py",
                        old="return user.token",
                        new="return user.token or ''",
                        context="def get_token(user):\n    ...",
                    ),
                ]
            ),
            output=ReviewReport(
                comments=[
                    ReviewComment(
                        path="svc/auth.py",
                        line=1,
                        severity="warning",
                        comment=(
                            "Returning '' masks a missing token; prefer "
                            "raising so callers handle the absence."
                        ),
                    ),
                ],
                summary="One auth-token masking concern.",
            ),
        ),
    )
