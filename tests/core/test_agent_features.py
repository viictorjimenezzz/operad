"""Tests for stream 2-1: the Agent feature bundle.

Covers `hash_content`, `forward_in`/`forward_out`, `validate`, `explain`,
`__rich__`, `summary`, and the `>>` operator.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from operad.core.agent import Agent
from operad.utils.errors import BuildError
from operad.utils.ops import AppendRule

from tests.conftest import A, B, C, FakeLeaf


# --- C1: hash_content stability --------------------------------------------


async def test_hash_content_equal_for_equal_state(cfg) -> None:
    one = FakeLeaf(config=cfg, input=A, output=B, task="same")
    two = FakeLeaf(config=cfg, input=A, output=B, task="same")
    assert one.hash_content == two.hash_content


async def test_hash_content_changes_on_mutation(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, task="t")
    before = leaf.hash_content
    AppendRule(path="", rule="be concise").apply(leaf)
    after = leaf.hash_content
    assert before != after


async def test_hash_content_stable_across_build(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()
    before = leaf.hash_content
    await leaf.abuild()
    assert leaf.hash_content == before


# --- C2: forward_in / forward_out hooks ------------------------------------


class _RecordingLeaf(FakeLeaf):
    def forward_in(self, x: Any) -> Any:
        x = A(text=x.text.upper())
        self._last_seen = x.text
        return x


async def test_forward_in_mutates_before_forward(cfg) -> None:
    leaf = await _RecordingLeaf(
        config=cfg, input=A, output=B, canned={"value": 1}
    ).abuild()
    await leaf(A(text="hello"))
    assert leaf._last_seen == "HELLO"


class _RepairingLeaf(FakeLeaf):
    def forward_out(self, x: Any, y: Any) -> Any:
        return B(value=y.value + 100)


async def test_forward_out_repairs_after_forward(cfg) -> None:
    leaf = await _RepairingLeaf(
        config=cfg, input=A, output=B, canned={"value": 5}
    ).abuild()
    env = await leaf(A(text="hi"))
    assert env.response.value == 105


# --- C3: validate -----------------------------------------------------------


async def test_validate_unbuilt_raises_not_built(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    with pytest.raises(BuildError) as exc:
        leaf.validate(A(text="x"))
    assert exc.value.reason == "not_built"


async def test_validate_wrong_input_type_raises_input_mismatch(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()

    class Wrong(BaseModel):
        z: int = 0

    with pytest.raises(BuildError) as exc:
        leaf.validate(Wrong())
    assert exc.value.reason == "input_mismatch"


async def test_invoke_on_unbuilt_routes_through_validate(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    with pytest.raises(BuildError) as exc:
        await leaf(A(text="x"))
    assert exc.value.reason == "not_built"


def test_no_inline_input_isinstance_outside_validate() -> None:
    from pathlib import Path

    text = Path("operad/core/agent.py").read_text()
    # grep-style check demanded by the brief
    count = text.count("isinstance(x, self.input)")
    assert count == 1, (
        f"expected exactly one `isinstance(x, self.input)` (inside validate), "
        f"got {count}"
    )


# --- O2: explain ------------------------------------------------------------


class _OutWithScratch(BaseModel):
    scratchpad: str = ""
    value: int = 0


async def test_explain_prints_scratchpad_and_output(cfg, capsys) -> None:
    leaf = await FakeLeaf(
        config=cfg,
        input=A,
        output=_OutWithScratch,
        canned={"scratchpad": "thinking hard", "value": 7},
    ).abuild()
    await leaf.explain(A(text="hi"))
    captured = capsys.readouterr().out
    assert "=== " in captured
    assert "scratchpad: thinking hard" in captured
    assert "output:" in captured
    # scratchpad should be stripped from the output: payload
    assert "'value': 7" in captured
    assert '"scratchpad"' not in captured.split("output:")[1]


# --- O6: __rich__ -----------------------------------------------------------


def test_rich_render(cfg) -> None:
    pytest.importorskip("rich")
    from rich.console import Console

    leaf = FakeLeaf(config=cfg, input=A, output=B).build()
    console = Console(record=True, width=120)
    console.print(leaf)
    text = console.export_text()
    assert "leaves" in text
    assert "hash" in text


def test_rich_render_unbuilt_does_not_raise(cfg) -> None:
    pytest.importorskip("rich")
    from rich.console import Console

    leaf = FakeLeaf(config=cfg, input=A, output=B)
    console = Console(record=True, width=120)
    console.print(leaf)
    text = console.export_text()
    assert "FakeLeaf" in text


# --- E3: summary ------------------------------------------------------------


def test_summary_prebuild_omits_graph_hash(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    s = leaf.summary()
    assert isinstance(s, str)
    assert "graph_hash=" not in s
    assert "hash_content=" in s
    assert "FakeLeaf" in s


def test_summary_postbuild_includes_graph_hash(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B).build()
    s = leaf.summary()
    assert "graph_hash=" in s
    assert "hash_content=" in s


# --- E1: __rshift__ ---------------------------------------------------------


def test_rshift_two_stages(cfg) -> None:
    from operad.agents.pipeline import Pipeline

    a = FakeLeaf(config=cfg, input=A, output=B)
    b = FakeLeaf(config=cfg, input=B, output=C)
    p = a >> b
    assert isinstance(p, Pipeline)
    assert p._stages == [a, b]


def test_rshift_flattens_three_stages(cfg) -> None:
    from operad.agents.pipeline import Pipeline

    class D_(BaseModel):
        d: str = ""

    a = FakeLeaf(config=cfg, input=A, output=B)
    b = FakeLeaf(config=cfg, input=B, output=C)
    c = FakeLeaf(config=cfg, input=C, output=D_)
    p = a >> b >> c
    assert isinstance(p, Pipeline)
    assert len(p._stages) == 3
    assert p._stages == [a, b, c]
