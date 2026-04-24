"""Gradient-mode ContextVars.

Two runtime flags drive `no_grad()` / `inference_mode()` semantics:

- ``_GRAD_ENABLED`` (default ``True``) — consulted by ``operad.optim.tape()``
  to decide whether to record an `Agent.invoke` call. Flipped to ``False``
  by both `operad.optim.no_grad()` and `operad.optim.inference_mode()`.
- ``_INFERENCE_MODE`` (default ``False``) — consulted by
  `Agent._invoke_envelope` to decide whether to run forward hooks.
  Flipped to ``True`` only by `operad.optim.inference_mode()`.

These live in `operad.core` (rather than `operad.optim`) so that
`operad/core/agent.py` can import the helpers without pulling the whole
`operad.optim` package — which triggers a circular import via
`grad_agent.py`. The public ``no_grad()`` / ``inference_mode()`` context
managers live in `operad/optim/context.py` and consume these vars.
"""

from __future__ import annotations

from contextvars import ContextVar

_GRAD_ENABLED: ContextVar[bool] = ContextVar("_GRAD_ENABLED", default=True)
_INFERENCE_MODE: ContextVar[bool] = ContextVar("_INFERENCE_MODE", default=False)


def _grad_enabled() -> bool:
    return _GRAD_ENABLED.get()


def _inference_mode_active() -> bool:
    return _INFERENCE_MODE.get()


__all__ = [
    "_GRAD_ENABLED",
    "_INFERENCE_MODE",
    "_grad_enabled",
    "_inference_mode_active",
]
