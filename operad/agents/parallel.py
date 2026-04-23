"""Fan-out composition: run N children on the same input concurrently."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel

from ..core.agent import Agent, In, Out


class Parallel(Agent[In, Out]):
    """Invoke each child with the same input via `asyncio.gather`; combine.

    `children` is a mapping from an attribute name (becomes part of the
    graph path, e.g. `Parallel.french`) to the child ``Agent``. Every child
    must accept ``input`` as its input type. ``combine`` receives a dict
    keyed by the same names and must return an ``output`` instance.

    As a composite, ``Parallel`` is a pure router: ``config`` is
    ``None`` because it never contacts a model on its own — children do.
    """

    def __init__(
        self,
        children: Mapping[str, Agent[In, Any]],
        *,
        input: type[In],
        output: type[Out],
        combine: Callable[[dict[str, BaseModel]], Out],
    ) -> None:
        if not children:
            raise ValueError("Parallel requires at least one child")
        super().__init__(config=None, input=input, output=output)
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
