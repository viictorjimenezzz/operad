"""The single, narrow seam between operad and strands.

`StrandsRunner` owns a `strands.Agent` instance and exposes only what
`operad.core.agent.Agent`'s default forward and stream paths need:
``model``, ``system_prompt`` (read/write), ``invoke_async``,
``stream_async``. Every other Strands attribute stays inside this
module.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator, TYPE_CHECKING
import warnings

import strands
from strands.types.agent import ConcurrentInvocationMode

if TYPE_CHECKING:
    from strands.models.model import Model


# ---------------------------------------------------------------------------
# Strands runner.
# ---------------------------------------------------------------------------


class StrandsRunner:
    """Wraps a `strands.Agent` for one operad leaf.

    Constructed at `build()` time for default-forward leaves and
    afresh per-call by `Agent._build_transient_runner` when
    ``stateless`` is True. ``UNSAFE_REENTRANT`` is the only
    invocation mode operad uses; it makes per-call transients safe
    under concurrent fan-out on a single agent instance.
    """

    __slots__ = ("_agent",)

    def __init__(
        self,
        *,
        model: "Model",
        system_prompt: str | None,
    ) -> None:
        self._agent = strands.Agent(
            model=model,
            system_prompt=system_prompt,
            concurrent_invocation_mode=ConcurrentInvocationMode.UNSAFE_REENTRANT,
        )

    @property
    def model(self) -> "Model":
        return self._agent.model

    @property
    def system_prompt(self) -> str | None:
        return self._agent.system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str | None) -> None:
        self._agent.system_prompt = value

    async def invoke_async(
        self,
        user_msg: Any,
        *,
        structured_output_model: Any = None,
    ) -> Any:
        if structured_output_model is None:
            return await self._agent.invoke_async(user_msg)
        if getattr(self.model, "_operad_native_structured_output", False):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                structured = await self._agent.structured_output_async(
                    structured_output_model,
                    user_msg,
                )
            return SimpleNamespace(structured_output=structured)
        return await self._agent.invoke_async(
            user_msg, structured_output_model=structured_output_model
        )

    def stream_async(
        self,
        user_msg: Any,
        *,
        structured_output_model: Any = None,
    ) -> AsyncIterator[Any]:
        return self._agent.stream_async(
            user_msg, structured_output_model=structured_output_model
        )


__all__ = ["StrandsRunner"]
