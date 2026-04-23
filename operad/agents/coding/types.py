"""Typed edges for the coding domain."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DiffChunk(BaseModel):
    """A single diff hunk with optional surrounding context."""

    path: str = Field(default="", description="Repository-relative file path.")
    old: str = Field(default="", description="The pre-change hunk body.")
    new: str = Field(default="", description="The post-change hunk body.")
    context: str = Field(
        default="", description="Surrounding code (populated by ContextOptimizer)."
    )


class PRDiff(BaseModel):
    """A pull request's full set of diff hunks."""

    chunks: list[DiffChunk] = Field(
        default_factory=list, description="All diff hunks in the pull request."
    )


class PRSummary(BaseModel):
    """At-a-glance summary of a pull request diff."""

    headline: str = Field(
        default="", description="One-line PR headline, under 70 characters."
    )
    changes: list[str] = Field(
        default_factory=list,
        description="Bulleted logical changes; one entry per idea, not per file.",
    )


class ReviewComment(BaseModel):
    """One localized review comment."""

    path: str = Field(default="", description="File path the comment is about.")
    line: int = Field(
        default=0, description="1-based line number in the post-change file."
    )
    severity: Literal["info", "warning", "error"] = Field(
        default="info", description="Severity tier for the comment."
    )
    comment: str = Field(default="", description="Human-readable review note.")


class ReviewReport(BaseModel):
    """Aggregated output of a code review over a whole PR."""

    comments: list[ReviewComment] = Field(default_factory=list)
    summary: str = Field(default="", description="Short narrative summary.")
