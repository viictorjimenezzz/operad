"""Tests for leaf agents under `operad.agents.coding.components`."""

from __future__ import annotations
import pytest
from operad.agents import CodeReviewer, ContextOptimizer, DiffChunk, DiffSummarizer, PRDiff, PRSummary, ReviewReport
from operad.agents import CodeReviewer, ContextOptimizer, DiffChunk, DiffSummarizer, PRDiff, PRReviewer, PRSummary, ReviewComment, ReviewReport
from operad.core.view import to_mermaid
from ..conftest import FakeLeaf


# --- from test_coding_components.py ---
LLM_LEAF_SPECS = [
    (CodeReviewer, PRDiff, ReviewReport),
    (DiffSummarizer, PRDiff, PRSummary),
]


@pytest.mark.parametrize("cls,in_cls,out_cls", LLM_LEAF_SPECS)
def test_llm_leaf_defaults_are_populated(cfg, cls, in_cls, out_cls) -> None:
    leaf = cls(config=cfg)
    assert leaf.role, f"{cls.__name__}.role is empty"
    assert leaf.task, f"{cls.__name__}.task is empty"
    assert leaf.rules, f"{cls.__name__}.rules is empty"
    assert leaf.input is in_cls
    assert leaf.output is out_cls


@pytest.mark.parametrize("cls", [CodeReviewer, DiffSummarizer])
def test_llm_leaf_ships_an_example(cfg, cls) -> None:
    leaf = cls(config=cfg)
    assert len(leaf.examples) >= 1
    for ex in leaf.examples:
        assert isinstance(ex.input, leaf.input)
        assert isinstance(ex.output, leaf.output)


def test_context_optimizer_needs_no_config() -> None:
    async def _noop(path: str) -> str:
        return ""

    opt = ContextOptimizer(read_file=_noop)
    assert opt.config is None
    assert opt.input is PRDiff
    assert opt.output is PRDiff


@pytest.mark.asyncio
async def test_context_optimizer_fills_empty_context() -> None:
    async def fake_read(path: str) -> str:
        return f"# file: {path}\nLINE1\nLINE2\n"

    opt = ContextOptimizer(read_file=fake_read)
    await opt.abuild()
    out = (await opt(
        PRDiff(
            chunks=[
                DiffChunk(path="a.py", old="x", new="y"),
                DiffChunk(path="b.py", old="x", new="y", context="prefilled"),
                DiffChunk(path="", old="x", new="y"),
            ]
        )
    )).response
    assert out.chunks[0].context, "context should be filled from fake_read"
    assert "a.py" in out.chunks[0].context
    assert out.chunks[1].context == "prefilled"
    assert out.chunks[2].context == ""  # no path, untouched


@pytest.mark.asyncio
async def test_context_optimizer_survives_read_file_errors() -> None:
    async def boom(path: str) -> str:
        raise FileNotFoundError(path)

    opt = ContextOptimizer(read_file=boom)
    await opt.abuild()
    out = (await opt(PRDiff(chunks=[DiffChunk(path="nope.py", old="", new="")]))).response
    assert out.chunks[0].context == ""


@pytest.mark.asyncio
async def test_context_optimizer_trims_large_files() -> None:
    async def big(path: str) -> str:
        return "\n".join(f"line{i}" for i in range(500))

    opt = ContextOptimizer(read_file=big, window=5)
    await opt.abuild()
    out = (await opt(PRDiff(chunks=[DiffChunk(path="big.py", old="", new="")]))).response
    ctx = out.chunks[0].context
    assert "..." in ctx
    assert "line0" in ctx
    assert "line499" in ctx

# --- from test_pr_reviewer.py ---
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
        "PRReviewer.pipeline",
        "PRReviewer.pipeline.stage_0",
        "PRReviewer.pipeline.stage_1",
        "PRReviewer.pipeline.stage_1.summary",
        "PRReviewer.pipeline.stage_1.review",
    }


async def test_pr_reviewer_graph_edges_match_stage_types(cfg) -> None:
    r = await _stub_pr_reviewer(cfg).abuild()
    by_callee = {e.callee: e for e in r._graph.edges}
    assert set(by_callee) == {
        "PRReviewer.pipeline",
        "PRReviewer.pipeline.stage_0",
        "PRReviewer.pipeline.stage_1",
        "PRReviewer.pipeline.stage_1.summary",
        "PRReviewer.pipeline.stage_1.review",
    }
    assert by_callee["PRReviewer.pipeline"].input_type is PRDiff
    assert by_callee["PRReviewer.pipeline"].output_type is ReviewReport
    assert by_callee["PRReviewer.pipeline.stage_0"].input_type is PRDiff
    assert by_callee["PRReviewer.pipeline.stage_0"].output_type is PRDiff
    assert by_callee["PRReviewer.pipeline.stage_1"].input_type is PRDiff
    assert by_callee["PRReviewer.pipeline.stage_1"].output_type is ReviewReport
    assert by_callee["PRReviewer.pipeline.stage_1.summary"].input_type is PRDiff
    assert by_callee["PRReviewer.pipeline.stage_1.summary"].output_type is PRSummary
    assert by_callee["PRReviewer.pipeline.stage_1.review"].input_type is PRDiff
    assert by_callee["PRReviewer.pipeline.stage_1.review"].output_type is ReviewReport


async def test_pr_reviewer_mermaid_contains_stage_paths(cfg) -> None:
    r = await _stub_pr_reviewer(cfg).abuild()
    text = to_mermaid(r._graph)
    assert "PRReviewer_pipeline_stage_0" in text
    assert "PRReviewer_pipeline_stage_1_summary" in text
    assert "PRReviewer_pipeline_stage_1_review" in text


async def test_pr_reviewer_routes_through_stubs_end_to_end(cfg) -> None:
    r = await _stub_pr_reviewer(cfg).abuild()
    out = (await r(PRDiff(chunks=[DiffChunk(path="a.py", old="o", new="n")]))).response
    assert isinstance(out, ReviewReport)
    assert out.summary == "h"  # from summarizer's headline
    assert len(out.comments) == 1 and out.comments[0].comment == "ok"
