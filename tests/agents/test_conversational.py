"""Tests for the leaf agents under `operad.agents.conversational.components`."""

from __future__ import annotations
import pytest
from operad.agents import Persona, Safeguard, SafeguardVerdict, StyledUtterance, TurnChoice, TurnTaker, Utterance
from operad.agents import RefusalLeaf, SafeguardVerdict, StyledUtterance, Talker, TurnChoice, Utterance
from ..conftest import FakeLeaf


# --- from test_conversational_components.py ---
LEAF_SPECS = [
    (Safeguard, Utterance, SafeguardVerdict),
    (TurnTaker, Utterance, TurnChoice),
    (Persona, Utterance, StyledUtterance),
]


@pytest.mark.parametrize("cls,in_cls,out_cls", LEAF_SPECS)
def test_leaf_contract_is_fixed(cfg, cls, in_cls, out_cls) -> None:
    leaf = cls(config=cfg)
    assert leaf.input is in_cls
    assert leaf.output is out_cls


@pytest.mark.parametrize("cls,_,__", LEAF_SPECS)
def test_leaf_defaults_are_populated(cfg, cls, _, __) -> None:
    leaf = cls(config=cfg)
    assert leaf.role, f"{cls.__name__}.role is empty"
    assert leaf.task, f"{cls.__name__}.task is empty"
    assert leaf.rules, f"{cls.__name__}.rules is empty"
    assert leaf.examples, f"{cls.__name__}.examples is empty"


@pytest.mark.parametrize("cls,_,__", LEAF_SPECS)
def test_leaf_task_override_wins(cfg, cls, _, __) -> None:
    leaf = cls(config=cfg, task="custom-task")
    assert leaf.task == "custom-task"


def test_persona_role_is_generic(cfg) -> None:
    """Users subclass (or override) for specific voices; ship a neutral default."""
    leaf = Persona(config=cfg)
    assert "helpful" in leaf.role.lower()


def test_safeguard_example_is_allow(cfg) -> None:
    leaf = Safeguard(config=cfg)
    example = leaf.examples[0]
    assert isinstance(example.input, Utterance)
    assert isinstance(example.output, SafeguardVerdict)
    assert example.output.label == "allow"

# --- from test_talker.py ---
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

    out = (await talker(Utterance(user_message="hi"))).response
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

    out = (await talker(Utterance(user_message="disallowed"))).response
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
    out = (await refusal(SafeguardVerdict(label="block", reason="nope"))).response
    assert isinstance(out, StyledUtterance)
    assert out.response
