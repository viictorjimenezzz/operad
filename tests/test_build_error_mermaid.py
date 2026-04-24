"""`BuildError.__str__` augments graph-local reasons with a Mermaid footer."""

from __future__ import annotations

import re

import pytest

from operad import Agent, BuildError, Configuration

from .conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_input_mismatch_has_mermaid_footer(cfg: Configuration) -> None:
    class Wrong(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            await self.first(x)
            return (await self.second(x)).response  # wrong type: A into B

    with pytest.raises(BuildError) as exc:
        await Wrong().abuild()
    assert exc.value.reason == "input_mismatch"
    rendered = str(exc.value)
    assert "--- mermaid ---" in rendered
    assert "flowchart LR" in rendered
    assert "Wrong" in rendered and "second" in rendered
    # First line preserved for log regex consumers.
    first_line = rendered.split("\n", 1)[0]
    assert re.match(r"^\[input_mismatch\]", first_line)


async def test_not_built_has_no_mermaid_footer(cfg: Configuration) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)  # unbuilt
    with pytest.raises(BuildError) as exc:
        await leaf(A(text="hi"))
    assert exc.value.reason == "not_built"
    assert "--- mermaid ---" not in str(exc.value)


async def test_payload_branch_has_mermaid_footer(cfg: Configuration) -> None:
    class Brancher(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.leaf = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> B:  # type: ignore[override]
            if x.text == "yes":  # reads payload field → trace guard
                return B(value=1)
            return (await self.leaf(x)).response

    with pytest.raises(BuildError) as exc:
        await Brancher().abuild()
    assert exc.value.reason == "payload_branch"
    assert "--- mermaid ---" in str(exc.value)
    assert "flowchart LR" in str(exc.value)
