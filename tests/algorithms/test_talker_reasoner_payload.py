from __future__ import annotations

import pytest

from operad.algorithms.talker_reasoner import (
    ScenarioNode,
    ScenarioTree,
    TalkerReasoner,
)
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers import registry as obs_registry


pytestmark = pytest.mark.asyncio


class _Collector:
    def __init__(self) -> None:
        self.events: list[AlgorithmEvent] = []

    async def on_event(self, event: object) -> None:
        if isinstance(event, AlgorithmEvent):
            self.events.append(event)


@pytest.fixture
def col():
    obs_registry.clear()
    c = _Collector()
    obs_registry.register(c)
    yield c
    obs_registry.clear()


async def test_talker_reasoner_algo_start_carries_tree(col: _Collector) -> None:
    tree = ScenarioTree(
        name="Intake",
        purpose="Route a user to the right next step.",
        root=ScenarioNode(
            id="root",
            title="Root",
            prompt="Start here.",
            children=[
                ScenarioNode(
                    id="done",
                    title="Done",
                    prompt="Finish.",
                    terminal=True,
                )
            ],
        ),
    )
    tr = TalkerReasoner(tree=tree)

    await tr.run([])

    start = next(e for e in col.events if e.kind == "algo_start")
    payload = start.payload
    assert payload["purpose"] == "Route a user to the right next step."
    assert payload["tree"]["rootId"] == "root"
    assert len(payload["tree"]["nodes"]) == 2
    assert payload["tree"]["nodes"][1]["parent_id"] == "root"
