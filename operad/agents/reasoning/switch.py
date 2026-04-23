"""``Switch`` composite: dispatch to a branch chosen by a ``Router`` leaf.

``Switch`` is the only composite in operad that inspects the tracer
context. The reason: at runtime it reads ``choice.label`` — the typed
output of its ``Router`` child — and dispatches to the matching branch.
That read is of a child's *typed output*, not of an input payload field,
so it does **not** violate the no-payload-branching invariant enforced
by the sentinel proxy in ``operad.core.build``.

During tracing, however, the tracer returns
``router.output.model_construct()`` for leaf children (see
``operad.core.build.Tracer.record``); that instance has no ``label`` set
and routing on it would raise ``router_miss`` and skip every branch. So
``forward`` takes a tracer-guarded fast path that visits every branch
exactly once, ensuring the ``AgentGraph`` records edges to all of them.
"""

from __future__ import annotations

import re
from collections.abc import Hashable, Mapping
from typing import Any

from ...core.agent import Agent, In, Out, _TRACER
from ...utils.errors import BuildError


_SLUG_RE = re.compile(r"[^0-9a-zA-Z_]+")


def _slug(label: Hashable) -> str:
    s = _SLUG_RE.sub("_", str(label)).strip("_")
    return s or "x"


class Switch(Agent[In, Out]):
    """Route an input to one of several branches based on a ``Router``'s choice.

    ``router`` must be an ``Agent`` whose output is a model with a
    ``label`` field (typically a ``Choice[Literal[...]]`` subclass). Its
    input type must match ``input``. ``branches`` maps the possible
    labels to child agents sharing the same ``(input, output)`` contract
    as the composite.

    At runtime: invoke ``router``, look up the matching branch by
    ``choice.label``, invoke and return its result. Unknown labels raise
    ``BuildError('router_miss', ...)``.

    At build time (tracer active): invoke the router, then invoke every
    branch once with the input sentinel so the graph captures all edges.
    """

    def __init__(
        self,
        *,
        router: Agent[Any, Any],
        branches: Mapping[Hashable, Agent[Any, Any]],
        input: type[In],
        output: type[Out],
    ) -> None:
        if not branches:
            raise ValueError("Switch requires at least one branch")
        super().__init__(config=None, input=input, output=output)
        self.router = router
        self._branches: dict[Hashable, Agent[Any, Any]] = dict(branches)
        self._branch_attrs: dict[Hashable, str] = {}
        seen: set[str] = set()
        for label, br in self._branches.items():
            base = f"branch_{_slug(label)}"
            attr = base
            i = 1
            while attr in seen:
                i += 1
                attr = f"{base}_{i}"
            seen.add(attr)
            self._branch_attrs[label] = attr
            setattr(self, attr, br)

    async def forward(self, x: In) -> Out:  # type: ignore[override]
        tracer = _TRACER.get()
        if tracer is not None:
            await self.router(x)
            for br in self._branches.values():
                await br(x)
            first = next(iter(self._branches.values()))
            return first.output.model_construct()  # type: ignore[return-value]

        choice = await self.router(x)
        label = getattr(choice, "label", None)
        branch = self._branches.get(label)
        if branch is None:
            raise BuildError(
                "router_miss",
                f"router emitted {label!r} with no matching branch; "
                f"known labels: {sorted(self._branches, key=repr)}",
                agent=type(self).__name__,
            )
        return await branch(x)


__all__ = ["Switch"]
