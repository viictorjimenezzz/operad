"""Gradient-mode context managers: `no_grad()` and `inference_mode()`.

The underlying ContextVars live in `operad.core.gradmode` so that
`operad.core.agent` can consult them without importing from
`operad.optim` (which would circle back through `grad_agent.py`). This
module re-exports them for callers that already reference
``operad.optim.context._GRAD_ENABLED`` (notably `operad.optim.tape`).

The distinction between the two CMs mirrors PyTorch: `no_grad()` is the
common case (skip autograd bookkeeping); `inference_mode()` is stricter
(also skip forward hooks).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from operad.core.gradmode import (
    _GRAD_ENABLED,
    _INFERENCE_MODE,
    _grad_enabled,
    _inference_mode_active,
)


@asynccontextmanager
async def no_grad() -> AsyncIterator[None]:
    """Disable tape recording for the duration of the block.

    Forward hooks still run. Nesting restores the outer state on exit.
    """
    token = _GRAD_ENABLED.set(False)
    try:
        yield
    finally:
        _GRAD_ENABLED.reset(token)


@asynccontextmanager
async def inference_mode() -> AsyncIterator[None]:
    """Disable tape recording *and* forward hooks for the duration.

    Stricter sibling of `no_grad()`; mirrors PyTorch's
    `torch.inference_mode()`. Use when you want the cheapest possible
    inference path with no side-channel instrumentation.
    """
    grad_token = _GRAD_ENABLED.set(False)
    inf_token = _INFERENCE_MODE.set(True)
    try:
        yield
    finally:
        _INFERENCE_MODE.reset(inf_token)
        _GRAD_ENABLED.reset(grad_token)


__all__ = [
    "_GRAD_ENABLED",
    "_INFERENCE_MODE",
    "_grad_enabled",
    "_inference_mode_active",
    "inference_mode",
    "no_grad",
]
