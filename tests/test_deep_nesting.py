"""Deep-nesting sanity: the build tracer and exporters handle tall trees.

A 10-level-deep nested `Pipeline` exercises the recursive trace, the
build-time type checker, and the Mermaid / JSON graph exporters far past
what unit tests in `test_build.py` reach. A second test pins down that
`_warn_shared_children`'s BFS walk still fires exactly once when the
shared leaf is buried inside two separate composite parents (the existing
shared-child test in `test_build.py` only covers depth-1 sharing).
"""

from __future__ import annotations

import pytest

from operad import Agent, Parallel, Pipeline, to_json, to_mermaid

from .conftest import A, FakeLeaf


pytestmark = pytest.mark.asyncio


def _nested_pipeline(depth: int, leaf: Agent) -> Agent:
    current: Agent = leaf
    for _ in range(depth):
        current = Pipeline(current, input=A, output=A)
    return current


async def test_ten_level_pipeline_builds_and_exports(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=A)
    root = _nested_pipeline(10, leaf)

    await root.abuild()

    mermaid = to_mermaid(root._graph)
    assert mermaid.startswith("flowchart")

    payload = to_json(root._graph)
    assert payload["root"]
    # 10 Pipeline composites + 1 leaf = 11 nodes in the captured graph.
    assert len(payload["nodes"]) >= 11
    # Each composite invokes its single stage; 10 edges chain the tree.
    assert len(payload["edges"]) >= 10


async def test_shared_leaf_across_deep_branches_warns_once(cfg) -> None:
    shared = FakeLeaf(config=cfg, input=A, output=A)

    class Branch(Agent):
        input = A
        output = A

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=A)
            self.leaf = shared

        async def forward(self, x: A) -> A:  # type: ignore[override]
            return await self.leaf(x)

    root = Parallel(
        {"left": Branch(), "right": Branch()},
        input=A,
        output=A,
        combine=lambda r: next(iter(r.values())),
    )

    with pytest.warns(UserWarning, match="shared") as records:
        await root.abuild()
    assert len(records) == 1
