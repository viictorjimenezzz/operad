"""Gradient-mode context managers: `no_grad()` and `inference_mode()`.

Two `ContextVar` flags underpin the public API:

- ``_GRAD_ENABLED`` (default ``True``) — consulted by ``tape()`` (wave 2-5)
  to decide whether to record an `Agent.invoke` call. Flipped to ``False``
  by both `no_grad()` and `inference_mode()`.
- ``_INFERENCE_MODE`` (default ``False``) — consulted by
  `Agent._invoke_envelope` to decide whether to run forward hooks. Flipped
  to ``True`` only by `inference_mode()`.

The distinction mirrors PyTorch: `no_grad()` is the common case (skip
autograd bookkeeping); `inference_mode()` is stricter (also skip hooks).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar

_GRAD_ENABLED: ContextVar[bool] = ContextVar("_GRAD_ENABLED", default=True)
_INFERENCE_MODE: ContextVar[bool] = ContextVar("_INFERENCE_MODE", default=False)


def _grad_enabled() -> bool:
    return _GRAD_ENABLED.get()


def _inference_mode_active() -> bool:
    return _INFERENCE_MODE.get()


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


__all__ = ["no_grad", "inference_mode"]
