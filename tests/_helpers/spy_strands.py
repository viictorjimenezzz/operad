"""Test spy for ``strands.Agent.invoke_async``.

Monkeypatches the upstream method so offline tests can assert on the
exact arguments a leaf's default ``forward`` passes to strands, and feed
a canned ``AgentResult`` back without any network call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import strands
from strands.agent.agent_result import AgentResult


@dataclass
class StrandsSpy:
    """Captures the last call to ``strands.Agent.invoke_async``."""

    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    system_prompts: list[str | None] = field(default_factory=list)
    canned_text: str = "{}"
    canned_structured: Any = None

    @property
    def last_args(self) -> tuple[Any, ...]:
        return self.calls[-1][0]

    @property
    def last_kwargs(self) -> dict[str, Any]:
        return self.calls[-1][1]

    @property
    def last_system_prompt(self) -> str | None:
        return self.system_prompts[-1]

    def _result(self) -> AgentResult:
        message = {"role": "assistant", "content": [{"text": self.canned_text}]}
        return AgentResult(
            stop_reason="end_turn",
            message=message,  # type: ignore[arg-type]
            metrics=None,  # type: ignore[arg-type]
            state={},
            interrupts=[],
            structured_output=self.canned_structured,
        )


def install_spy(monkeypatch: Any, spy: StrandsSpy) -> StrandsSpy:
    """Patch ``strands.Agent.invoke_async`` to record + return ``spy``'s result."""

    async def _fake_invoke_async(
        self: Any, *args: Any, **kwargs: Any
    ) -> AgentResult:
        spy.calls.append((args, kwargs))
        spy.system_prompts.append(getattr(self, "system_prompt", None))
        return spy._result()

    monkeypatch.setattr(strands.Agent, "invoke_async", _fake_invoke_async)
    return spy
