"""`TextualGradientDescent` — the default textual-gradient optimizer.

A direct analog of `torch.optim.SGD` (without momentum): for every
parameter whose `.grad` carries nonzero severity, invoke the
kind-appropriate `RewriteAgent` via `apply_rewrite`, which writes the
new value back through `Parameter.write`. Momentum-based optimizers live
in wave 4-1.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import Any, Callable, Iterable

from operad.core.config import Configuration
from operad.optim.parameter import Parameter, ParameterKind
from operad.optim.backprop.rewrite import RewriteAgent, apply_rewrite, rewriter_for
from operad.optim.optimizers.optimizer import Optimizer, ParamGroup


RewriterFactory = Callable[
    [ParameterKind], RewriteAgent | Awaitable[RewriteAgent]
]


# ---------------------------------------------------------------------------
# Optimizer.
# ---------------------------------------------------------------------------


class TextualGradientDescent(Optimizer):
    """Vanilla textual gradient descent: one rewrite per parameter per step.

    `rewriter_factory` is keyed by `ParameterKind`. If not supplied the
    optimizer builds one `RewriteAgent` per kind lazily from
    `rewriter_for(kind)(config=config)` and memoizes it. Per-group
    factories are honoured via `group.extras["rewriter_factory"]`.
    """

    def __init__(
        self,
        params: Iterable[Parameter[Any]] | Iterable[dict[str, Any]],
        lr: float = 1.0,
        *,
        config: Configuration | None = None,
        rewriter_factory: RewriterFactory | None = None,
        persist_grads: bool = False,
    ) -> None:
        super().__init__(params, defaults={"lr": lr, "momentum": 0.0})
        self._config = config
        self._factory: RewriterFactory | None = rewriter_factory
        self._persist_grads = persist_grads
        self._cache: dict[tuple[int, ParameterKind], RewriteAgent] = {}

    async def step(self) -> None:
        items: list[tuple[Parameter[Any], ParamGroup]] = []
        for group in self.param_groups:
            for p in group.params:
                if not p.requires_grad:
                    continue
                if p.grad is None or p.grad.severity <= 0:
                    continue
                items.append((p, group))

        if not items:
            return

        await self._apply_updates(items)

        if not self._persist_grads:
            for p, _ in items:
                p.grad = None

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        rewriter = await self._resolve_rewriter(param.kind, group)
        grad = param.grad
        assert grad is not None  # filtered in step()
        await apply_rewrite(param, grad, rewriter, lr=group.lr)

    async def _resolve_rewriter(
        self, kind: ParameterKind, group: ParamGroup
    ) -> RewriteAgent:
        cache_key = (id(group), kind)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        factory = group.extras.get("rewriter_factory") or self._factory
        if factory is None:
            rewriter = await self._default_build(kind)
        else:
            produced = factory(kind)
            if inspect.isawaitable(produced):
                rewriter = await produced
            else:
                rewriter = produced

        self._cache[cache_key] = rewriter
        return rewriter

    async def _default_build(self, kind: ParameterKind) -> RewriteAgent:
        cls = rewriter_for(kind)
        return await cls(config=self._config).abuild()


__all__ = ["TextualGradientDescent"]
