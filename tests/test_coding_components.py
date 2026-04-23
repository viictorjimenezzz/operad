"""Tests for leaf agents under `operad.agents.coding.components`."""

from __future__ import annotations

import pytest

from operad import (
    CodeReviewer,
    ContextOptimizer,
    DiffChunk,
    DiffSummarizer,
    PRDiff,
    PRSummary,
    ReviewReport,
)


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
    out = await opt(
        PRDiff(
            chunks=[
                DiffChunk(path="a.py", old="x", new="y"),
                DiffChunk(path="b.py", old="x", new="y", context="prefilled"),
                DiffChunk(path="", old="x", new="y"),
            ]
        )
    )
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
    out = await opt(PRDiff(chunks=[DiffChunk(path="nope.py", old="", new="")]))
    assert out.chunks[0].context == ""


@pytest.mark.asyncio
async def test_context_optimizer_trims_large_files() -> None:
    async def big(path: str) -> str:
        return "\n".join(f"line{i}" for i in range(500))

    opt = ContextOptimizer(read_file=big, window=5)
    await opt.abuild()
    out = await opt(PRDiff(chunks=[DiffChunk(path="big.py", old="", new="")]))
    ctx = out.chunks[0].context
    assert "..." in ctx
    assert "line0" in ctx
    assert "line499" in ctx
