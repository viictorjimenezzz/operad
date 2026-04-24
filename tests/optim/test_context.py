"""Offline tests for `operad.optim.context`.

Covers the two ContextVars (`_GRAD_ENABLED`, `_INFERENCE_MODE`), the
`no_grad()` / `inference_mode()` async context managers, nested usage,
per-task isolation under `asyncio.gather`, and the public re-exports.
"""

from __future__ import annotations

import asyncio

import pytest

from operad.optim import inference_mode, no_grad
from operad.optim.context import _grad_enabled, _inference_mode_active


@pytest.mark.asyncio
async def test_no_grad_toggles_only_grad_enabled() -> None:
    assert _grad_enabled() is True
    assert _inference_mode_active() is False
    async with no_grad():
        assert _grad_enabled() is False
        assert _inference_mode_active() is False
    assert _grad_enabled() is True
    assert _inference_mode_active() is False


@pytest.mark.asyncio
async def test_inference_mode_toggles_both() -> None:
    assert _grad_enabled() is True
    assert _inference_mode_active() is False
    async with inference_mode():
        assert _grad_enabled() is False
        assert _inference_mode_active() is True
    assert _grad_enabled() is True
    assert _inference_mode_active() is False


@pytest.mark.asyncio
async def test_nested_no_grad_restores_outer_state() -> None:
    async with no_grad():
        assert _grad_enabled() is False
        async with no_grad():
            assert _grad_enabled() is False
        assert _grad_enabled() is False
    assert _grad_enabled() is True


@pytest.mark.asyncio
async def test_inference_mode_nested_inside_no_grad() -> None:
    async with no_grad():
        assert _grad_enabled() is False
        assert _inference_mode_active() is False
        async with inference_mode():
            assert _grad_enabled() is False
            assert _inference_mode_active() is True
        assert _grad_enabled() is False
        assert _inference_mode_active() is False
    assert _grad_enabled() is True
    assert _inference_mode_active() is False


@pytest.mark.asyncio
async def test_exception_inside_no_grad_restores_state() -> None:
    with pytest.raises(RuntimeError):
        async with no_grad():
            assert _grad_enabled() is False
            raise RuntimeError("boom")
    assert _grad_enabled() is True


@pytest.mark.asyncio
async def test_exception_inside_inference_mode_restores_both() -> None:
    with pytest.raises(RuntimeError):
        async with inference_mode():
            assert _grad_enabled() is False
            assert _inference_mode_active() is True
            raise RuntimeError("boom")
    assert _grad_enabled() is True
    assert _inference_mode_active() is False


@pytest.mark.asyncio
async def test_concurrent_tasks_are_isolated() -> None:
    """ContextVars copy on task creation — each task sees its own state."""
    seen: dict[str, bool] = {}
    gate = asyncio.Event()

    async def inside() -> None:
        async with no_grad():
            seen["inside"] = _grad_enabled()
            gate.set()
            await asyncio.sleep(0.02)

    async def outside() -> None:
        await gate.wait()
        seen["outside"] = _grad_enabled()

    await asyncio.gather(inside(), outside())
    assert seen["inside"] is False
    assert seen["outside"] is True


def test_public_exports() -> None:
    from operad.optim import inference_mode as im, no_grad as ng
    assert im is inference_mode
    assert ng is no_grad
