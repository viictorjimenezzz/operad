"""Tests for the `Talker` composition."""

from __future__ import annotations

import pytest

from operad import (
    RefusalLeaf,
    SafeguardVerdict,
    StyledUtterance,
    Talker,
    TurnChoice,
    Utterance,
)

from .conftest import FakeLeaf


pytestmark = pytest.mark.asyncio


def _make_talker(cfg, *, label: str, response: str = "hello") -> Talker:
    """Build a Talker with every model-facing leaf replaced by a FakeLeaf.

    The RefusalLeaf is left alone since it never contacts a model.
    """
    talker = Talker(config=cfg)
    talker.safeguard = FakeLeaf(
        config=cfg,
        input=Utterance,
        output=SafeguardVerdict,
        canned={"label": label, "reason": "test"},
    )
    talker.turn_taker = FakeLeaf(
        config=cfg,
        input=Utterance,
        output=TurnChoice,
        canned={"action": "respond", "prompt": ""},
    )
    talker.persona = FakeLeaf(
        config=cfg,
        input=Utterance,
        output=StyledUtterance,
        canned={"response": response},
    )
    return talker


class _SpyLeaf(FakeLeaf):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.calls = 0

    async def forward(self, x):  # type: ignore[override]
        self.calls += 1
        return await super().forward(x)


async def test_allow_path_invokes_turn_taker_and_persona(cfg) -> None:
    talker = _make_talker(cfg, label="allow", response="ok then")
    # Swap in spies so we can count calls.
    talker.turn_taker = _SpyLeaf(
        config=cfg, input=Utterance, output=TurnChoice,
        canned={"action": "respond", "prompt": ""},
    )
    talker.persona = _SpyLeaf(
        config=cfg, input=Utterance, output=StyledUtterance,
        canned={"response": "ok then"},
    )
    await talker.abuild()

    out = await talker(Utterance(user_message="hi"))
    assert isinstance(out, StyledUtterance)
    assert out.response == "ok then"
    assert talker.turn_taker.calls == 1
    assert talker.persona.calls == 1


async def test_block_path_short_circuits_to_refusal(cfg) -> None:
    talker = _make_talker(cfg, label="block")
    talker.turn_taker = _SpyLeaf(
        config=cfg, input=Utterance, output=TurnChoice,
        canned={"action": "respond", "prompt": ""},
    )
    talker.persona = _SpyLeaf(
        config=cfg, input=Utterance, output=StyledUtterance,
        canned={"response": "should not fire"},
    )
    await talker.abuild()

    out = await talker(Utterance(user_message="disallowed"))
    assert isinstance(out, StyledUtterance)
    assert "can't help" in out.response
    # Refusal path bypasses the other two leaves at runtime. They are
    # visited once during build() (trace), so the counter must be 0 here.
    assert talker.turn_taker.calls == 0
    assert talker.persona.calls == 0


async def test_graph_records_both_branches(cfg) -> None:
    talker = _make_talker(cfg, label="allow")
    await talker.abuild()
    callees = {e.callee for e in talker._graph.edges}
    # All four children must appear — both allow-branch legs plus refusal.
    assert "Talker.safeguard" in callees
    assert "Talker.turn_taker" in callees
    assert "Talker.persona" in callees
    assert "Talker.refusal" in callees


async def test_refusal_leaf_does_not_need_config() -> None:
    refusal = RefusalLeaf()
    await refusal.abuild()
    out = await refusal(SafeguardVerdict(label="block", reason="nope"))
    assert isinstance(out, StyledUtterance)
    assert out.response
