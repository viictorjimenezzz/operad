"""Tests for the composed `PRReviewer` coding pattern."""

from __future__ import annotations

import pytest

from operad.agents import (
    CodeReviewer,
    ContextOptimizer,
    DiffChunk,
    DiffSummarizer,
    PRDiff,
    PRReviewer,
    PRSummary,
    ReviewComment,
    ReviewReport,
)
from operad.core.graph import to_mermaid

from .conftest import FakeLeaf


pytestmark = pytest.mark.asyncio


async def _noop_read(path: str) -> str:
    return f"# ctx for {path}\n"


def _stub_pr_reviewer(cfg) -> PRReviewer:
    r = PRReviewer(config=cfg, read_file=_noop_read)
    r.optimizer = FakeLeaf(
        config=cfg,
        input=PRDiff,
        output=PRDiff,
        canned={"chunks": [DiffChunk(path="a.py", old="", new="", context="ctx")]},
    )
    r.summarizer = FakeLeaf(
        config=cfg,
        input=PRDiff,
        output=PRSummary,
        canned={"headline": "h", "changes": ["c1"]},
    )
    r.reviewer = FakeLeaf(
        config=cfg,
        input=PRDiff,
        output=ReviewReport,
        canned={
            "comments": [
                ReviewComment(path="a.py", line=1, severity="info", comment="ok")
            ],
            "summary": "r",
        },
    )
    return r


async def test_pr_reviewer_default_construction_wires_real_components(cfg) -> None:
    r = PRReviewer(config=cfg, read_file=_noop_read)
    assert isinstance(r.optimizer, ContextOptimizer)
    assert isinstance(r.summarizer, DiffSummarizer)
    assert isinstance(r.reviewer, CodeReviewer)
    assert r.config is None
    assert r.summarizer.config is cfg
    assert r.reviewer.config is cfg
    assert r.optimizer.config is None


async def test_pr_reviewer_graph_has_expected_nodes(cfg) -> None:
    r = await _stub_pr_reviewer(cfg).abuild()
    paths = {n.path for n in r._graph.nodes}
    assert paths == {
        "PRReviewer",
        "PRReviewer.optimizer",
        "PRReviewer.summarizer",
        "PRReviewer.reviewer",
    }


async def test_pr_reviewer_graph_edges_match_stage_types(cfg) -> None:
    r = await _stub_pr_reviewer(cfg).abuild()
    by_callee = {e.callee: e for e in r._graph.edges}
    assert set(by_callee) == {
        "PRReviewer.optimizer",
        "PRReviewer.summarizer",
        "PRReviewer.reviewer",
    }
    assert by_callee["PRReviewer.optimizer"].input_type is PRDiff
    assert by_callee["PRReviewer.optimizer"].output_type is PRDiff
    assert by_callee["PRReviewer.summarizer"].input_type is PRDiff
    assert by_callee["PRReviewer.summarizer"].output_type is PRSummary
    assert by_callee["PRReviewer.reviewer"].input_type is PRDiff
    assert by_callee["PRReviewer.reviewer"].output_type is ReviewReport


async def test_pr_reviewer_mermaid_contains_stage_paths(cfg) -> None:
    r = await _stub_pr_reviewer(cfg).abuild()
    text = to_mermaid(r._graph)
    assert "PRReviewer_optimizer" in text
    assert "PRReviewer_summarizer" in text
    assert "PRReviewer_reviewer" in text


async def test_pr_reviewer_routes_through_stubs_end_to_end(cfg) -> None:
    r = await _stub_pr_reviewer(cfg).abuild()
    out = (await r(PRDiff(chunks=[DiffChunk(path="a.py", old="o", new="n")]))).response
    assert isinstance(out, ReviewReport)
    assert out.summary == "h"  # from summarizer's headline
    assert len(out.comments) == 1 and out.comments[0].comment == "ok"
