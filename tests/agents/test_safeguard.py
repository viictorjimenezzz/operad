"""Tests for the task-agnostic `operad.agents.safeguard` domain."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from operad import Configuration
from operad.agents import Pipeline
from operad.agents.safeguard import (
    InputSanitizer,
    ModerationVerdict,
    OutputModerator,
    SanitizerPolicy,
)
from operad.core.graph import to_mermaid


pytestmark = pytest.mark.asyncio


class Foo(BaseModel):
    text: str = ""
    count: int = 0


class Answer(BaseModel):
    text: str = ""


class _StubModerator(OutputModerator[Any]):
    """Offline stand-in that skips the LLM call."""

    async def forward(self, x: Any) -> ModerationVerdict:  # type: ignore[override]
        return ModerationVerdict(label="allow", reason="benign")


async def test_input_sanitizer_redacts_policy_pattern() -> None:
    san = InputSanitizer(
        schema=Foo,
        policy=SanitizerPolicy(
            strip_pii=False, redact_pattern=r"\bSSN-\d+\b"
        ),
    )
    out = await san.forward(Foo(text="user SSN-12345", count=7))
    assert out.text == "user [REDACTED]"
    assert out.count == 7


async def test_input_sanitizer_truncates_to_max_chars() -> None:
    san = InputSanitizer(
        schema=Foo,
        policy=SanitizerPolicy(strip_pii=False, max_chars=10),
    )
    out = await san.forward(Foo(text="hello world", count=0))
    assert out.text == "hello worl"


async def test_input_sanitizer_preserves_type_and_non_string_fields() -> None:
    san = InputSanitizer(schema=Foo, policy=SanitizerPolicy(strip_pii=False))
    payload = Foo(text="hello", count=42)
    out = await san.forward(payload)
    assert type(out) is Foo
    assert out.count == 42
    assert out.text == "hello"


async def test_output_moderator_build_captures_leaf(cfg: Configuration) -> None:
    mod = OutputModerator(schema=Foo, config=cfg)
    await mod.abuild()
    assert mod._built is True
    graph = mod._graph
    assert graph.root == "OutputModerator"
    assert [n.path for n in graph.nodes] == ["OutputModerator"]
    assert graph.nodes[0].kind == "leaf"
    assert graph.nodes[0].input_type is Foo
    assert graph.nodes[0].output_type is ModerationVerdict


async def test_output_moderator_forward_offline(cfg: Configuration) -> None:
    mod = await _StubModerator(schema=Foo, config=cfg).abuild()
    out = await mod(Foo(text="anything", count=1))
    assert isinstance(out.response, ModerationVerdict)
    assert out.response.label == "allow"
    assert out.response.reason == "benign"


async def test_pipeline_composition_with_sanitizer_and_moderator(
    cfg: Configuration,
) -> None:
    pipe = Pipeline(
        InputSanitizer(schema=Foo),
        _StubModerator(schema=Foo, config=cfg),
        input=Foo,
        output=ModerationVerdict,
    )
    await pipe.abuild()
    graph = pipe._graph
    paths = [n.path for n in graph.nodes]
    assert paths == ["Pipeline", "Pipeline.stage_0", "Pipeline.stage_1"]
    assert graph.nodes[1].input_type is Foo and graph.nodes[1].output_type is Foo
    assert graph.nodes[2].output_type is ModerationVerdict
    rendered = to_mermaid(graph)
    assert "Pipeline.stage_0" in rendered
    assert "Pipeline.stage_1" in rendered
    assert "Foo -> ModerationVerdict" in rendered
