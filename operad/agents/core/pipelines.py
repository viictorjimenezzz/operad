"""Domain-agnostic composition primitives.

`Sequential` chains stages end-to-end.
`Parallel` fans out a shared input to multiple children and combines results.
`Loop` repeats a full `Sequential` pass `n_loops` times.
`Router` dispatches to one branch chosen by a typed selector output.
"""

from __future__ import annotations

import asyncio
import re
import warnings
from collections.abc import Callable, Mapping
from typing import Any, Hashable

from pydantic import BaseModel

from ...core.agent import Agent, In, Out, _TRACER
from ...utils.errors import BuildError, SideEffectDuringTrace


class Sequential(Agent[In, Out]):
    """Chain stages end-to-end; `build()` type-checks each handoff."""

    def __init__(
        self,
        *stages: Agent[Any, Any],
        input: type[In],
        output: type[Out],
        name: str | None = None,
    ) -> None:
        if not stages:
            raise ValueError("Sequential requires at least one stage")
        super().__init__(config=None, input=input, output=output, name=name)
        self._stages: list[Agent[Any, Any]] = list(stages)
        for i, stage in enumerate(stages):
            setattr(self, f"stage_{i}", stage)

    async def forward(self, x: In) -> Out:  # type: ignore[override]
        current: BaseModel = x
        for stage in self._stages:
            current = (await stage(current)).response
        return current  # type: ignore[return-value]


class Parallel(Agent[In, Out]):
    """Invoke each child with the same input via `asyncio.gather`; combine."""

    def __init__(
        self,
        children: Mapping[str, Agent[In, Any]],
        *,
        input: type[In],
        output: type[Out],
        combine: Callable[[dict[str, BaseModel]], Out],
        name: str | None = None,
    ) -> None:
        if not children:
            raise ValueError("Parallel requires at least one child")
        super().__init__(config=None, input=input, output=output, name=name)
        self._keys: list[str] = list(children)
        for key, child in children.items():
            setattr(self, key, child)
        self._combine = combine

    async def forward(self, x: In) -> Out:  # type: ignore[override]
        wrapped = await asyncio.gather(
            *(getattr(self, key)(x) for key in self._keys)
        )
        results = [w.response for w in wrapped]
        return self._combine(dict(zip(self._keys, results, strict=True)))


class Loop(Sequential[In, In]):
    """Repeat a full `Sequential` pass `n_loops` times."""

    def __init__(
        self,
        *stages: Agent[Any, Any],
        input: type[In],
        output: type[In],
        n_loops: int,
        name: str | None = None,
    ) -> None:
        if input is not output:
            raise ValueError("Loop requires `input` and `output` to be the same type")
        if n_loops < 1:
            raise ValueError("Loop requires n_loops >= 1")
        super().__init__(*stages, input=input, output=output, name=name)
        self.n_loops = n_loops

    async def forward(self, x: In) -> In:  # type: ignore[override]
        current: BaseModel = x
        for _ in range(self.n_loops):
            for stage in self._stages:
                current = (await stage(current)).response
        return current  # type: ignore[return-value]


_SLUG_RE = re.compile(r"[^0-9a-zA-Z_]+")


def _slug(label: Hashable) -> str:
    s = _SLUG_RE.sub("_", str(label)).strip("_")
    return s or "x"


class Router(Agent[In, Out]):
    """Route an input to one branch based on a selector's typed output.

    ``router`` must emit a typed output carrying a ``label`` attribute.
    ``branches`` maps those labels to child agents.

    ``branch_input`` is optional. When provided, it adapts the runtime
    input forwarded to the selected branch (for example passing the
    selector output to some branches and raw input to others).
    """

    def __init__(
        self,
        *,
        router: Agent[Any, Any],
        branches: Mapping[Hashable, Agent[Any, Any]],
        input: type[In],
        output: type[Out],
        key_field: str = "label",
        branch_input: (
            Callable[[In, BaseModel, Agent[Any, Any]], BaseModel] | None
        ) = None,
    ) -> None:
        if not branches:
            raise ValueError("Router requires at least one branch")
        super().__init__(config=None, input=input, output=output)
        self.router = router
        self._branches: dict[Hashable, Agent[Any, Any]] = dict(branches)
        self._branch_attrs: dict[Hashable, str] = {}
        self._key_field = key_field
        self._branch_input = branch_input
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
            warnings.warn(
                "Router is tracing all branches; ensure they are "
                "side-effect-free.",
                SideEffectDuringTrace,
                stacklevel=3,
            )
            await self.router(x)
            for br in self._branches.values():
                if self._branch_input is None:
                    await br(x)
                else:
                    await br(br.input.model_construct())
            first = next(iter(self._branches.values()))
            return first.output.model_construct()  # type: ignore[return-value]

        choice = (await self.router(x)).response
        label = getattr(choice, self._key_field, None)
        branch = self._branches.get(label)
        if branch is None:
            from ...core.graph import to_mermaid_node

            raise BuildError(
                "router_miss",
                f"router emitted {label!r} with no matching branch; "
                f"known labels: {sorted(self._branches, key=repr)}",
                agent=type(self).__name__,
                mermaid=to_mermaid_node(
                    type(self).__name__,
                    (self.input, self.output),  # type: ignore[arg-type]
                    note=f"router emitted {label!r}, no branch matched",
                ),
            )
        payload: BaseModel
        if self._branch_input is None:
            payload = x
        else:
            payload = self._branch_input(x, choice, branch)
        return (await branch(payload)).response
