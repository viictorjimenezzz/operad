"""Offline benchmark agents that never contact a model provider."""

from __future__ import annotations

from operad import Agent, Configuration
from operad.core.config import Sampling

from ._data import (
    _INTENTS,
    _TOOLS,
    _stable_hash,
    DocIn,
    IntentIn,
    IntentOut,
    SummaryOut,
    ToolIn,
    ToolOut,
)


OFFLINE_CFG = Configuration(
    backend="llamacpp",
    host="127.0.0.1:0",
    model="offline-stub",
    sampling=Sampling(temperature=0.0, max_tokens=2048),
)


class OfflineIntentLeaf(Agent[IntentIn, IntentOut]):
    input = IntentIn
    output = IntentOut

    async def forward(self, x: IntentIn) -> IntentOut:
        text = x.text.lower()
        for intent in _INTENTS:
            keyword = intent.replace("_", " ").split()[0]
            if keyword in text:
                return IntentOut(intent=intent)
        idx = _stable_hash(x.text) % len(_INTENTS)
        return IntentOut(intent=_INTENTS[idx])


class OfflineSummaryLeaf(Agent[DocIn, SummaryOut]):
    input = DocIn
    output = SummaryOut

    async def forward(self, x: DocIn) -> SummaryOut:
        sentences = x.text.split(".")
        summary = sentences[0].strip() + "." if sentences else x.text[:80]
        return SummaryOut(summary=summary[:120])


class OfflineToolLeaf(Agent[ToolIn, ToolOut]):
    input = ToolIn
    output = ToolOut

    async def forward(self, x: ToolIn) -> ToolOut:
        instr = x.instruction.lower()
        if any(w in instr for w in ["weather", "temperature", "rain", "sunny", "forecast"]):
            return ToolOut(tool_name="get_weather", tool_args='{"city": "Unknown"}')
        if any(w in instr for w in ["remind", "reminder", "alarm", "schedule"]):
            return ToolOut(tool_name="set_reminder", tool_args='{"message": "Reminder", "time": "TBD"}')
        if any(w in instr for w in ["search", "find", "look up", "latest"]):
            return ToolOut(tool_name="search_web", tool_args='{"query": "query"}')
        if any(w in instr for w in ["email", "send", "mail", "forward"]):
            return ToolOut(tool_name="send_email", tool_args='{"to": "user@example.com", "subject": "Message"}')
        if any(w in instr for w in ["calculate", "what is", "multiply", "divide", "convert", "area", "power", "sqrt", "interest", "factorial", "percent"]):
            return ToolOut(tool_name="calculate", tool_args='{"expression": "0"}')
        idx = _stable_hash(x.instruction) % len(_TOOLS)
        return ToolOut(tool_name=_TOOLS[idx], tool_args="{}")
