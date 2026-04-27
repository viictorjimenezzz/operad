"""Gradient-mode flags and context managers.

Two runtime flags drive `no_grad()` / `inference_mode()` semantics:

- ``_GRAD_ENABLED`` (default ``True``) — consulted by
  ``operad.optim.backprop.tape`` to decide whether to record an
  `Agent.invoke` call. Flipped to ``False`` by both
  `operad.optim.gradmode.no_grad()` and
  `operad.optim.gradmode.inference_mode()`.
- ``_INFERENCE_MODE`` (default ``False``) — consulted by
  `Agent._invoke_envelope` to decide whether to run forward hooks.
  Flipped to ``True`` only by `operad.optim.gradmode.inference_mode()`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextvars import ContextVar
from contextlib import asynccontextmanager


# ---------------------------------------------------------------------------
# Runtime flags.
# ---------------------------------------------------------------------------


_GRAD_ENABLED: ContextVar[bool] = ContextVar("_GRAD_ENABLED", default=True)
_INFERENCE_MODE: ContextVar[bool] = ContextVar("_INFERENCE_MODE", default=False)


def _grad_enabled() -> bool:
    return _GRAD_ENABLED.get()


def _inference_mode_active() -> bool:
    return _INFERENCE_MODE.get()


# ---------------------------------------------------------------------------
# Public context managers.
# ---------------------------------------------------------------------------


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
    """Disable tape recording and forward hooks for the duration.

    This is the stricter sibling of `no_grad()`, mirroring
    `torch.inference_mode()`.
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
