"""Tests for `build_agent`: graph capture, type checks, rebuild behavior."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad import Agent, AgentGraph, BuildError

from ..conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_leaf_build_produces_empty_graph(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()
    g: AgentGraph = leaf._graph
    assert g.root == "FakeLeaf"
    assert [n.path for n in g.nodes] == ["FakeLeaf"]
    assert g.nodes[0].kind == "leaf"
    assert g.nodes[0].input_type is A and g.nodes[0].output_type is B
    assert g.edges == []


async def test_pipeline_build_captures_edges(cfg) -> None:
    class Pipeline(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            mid = (await self.first(x)).response
            return (await self.second(mid)).response

    p = await Pipeline().abuild()
    g: AgentGraph = p._graph
    assert g.root == "Pipeline"
    assert len(g.edges) == 2

    e1, e2 = g.edges
    assert e1.caller == "Pipeline" and e1.callee == "Pipeline.first"
    assert e1.input_type is A and e1.output_type is B
    assert e2.caller == "Pipeline" and e2.callee == "Pipeline.second"
    assert e2.input_type is B and e2.output_type is C


async def test_build_catches_edge_input_mismatch_before_llm(cfg) -> None:
    class Wrong(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            # second expects B but we'll pass A into it
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            await self.first(x)
            return (await self.second(x)).response  # type: ignore[arg-type]

    with pytest.raises(BuildError) as exc:
        await Wrong().abuild()
    assert exc.value.reason == "input_mismatch"
    assert exc.value.agent is not None and "second" in exc.value.agent


async def test_build_catches_leaf_root_broken_output(cfg) -> None:
    class _Broken(BaseModel):
        @classmethod
        def model_construct(cls, *a, **kw) -> "_Broken":  # type: ignore[override]
            raise RuntimeError("broken output class")

    class DefaultLeaf(Agent[A, _Broken]):
        input = A
        output = _Broken
        role = "r"
        task = "t"

    leaf = DefaultLeaf(config=cfg, input=A, output=_Broken)
    with pytest.raises(BuildError) as exc:
        await leaf.abuild()
    assert exc.value.reason == "output_mismatch"
    assert "DefaultLeaf" in str(exc.value)


async def test_build_catches_root_output_mismatch(cfg) -> None:
    class BadRoot(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.only = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            # Returns a B but declared Out is C.
            return (await self.only(x)).response  # type: ignore[return-value]

    with pytest.raises(BuildError) as exc:
        await BadRoot().abuild()
    assert exc.value.reason == "output_mismatch"


async def test_build_is_idempotent_after_mutation(cfg) -> None:
    class Pipeline(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            return (await self.second((await self.first(x)).response)).response

    p = await Pipeline().abuild()
    assert p._built is True

    p.first.task = "updated"
    p.first.config.sampling.temperature = 0.0
    await p.abuild()
    assert p._built is True
    assert p.first.task == "updated"


async def test_build_marks_all_descendants_built(cfg) -> None:
    class Pipeline(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            return (await self.second((await self.first(x)).response)).response

    p = await Pipeline().abuild()
    assert p._built is True
    assert p.first._built is True
    assert p.second._built is True


async def test_build_requires_input_output(cfg) -> None:
    class NoTypesLeaf(Agent):
        pass  # no class-level input/output

    with pytest.raises(BuildError) as exc:
        NoTypesLeaf(config=cfg)
    assert exc.value.reason == "prompt_incomplete"


async def test_payload_branch_raises(cfg) -> None:
    class Brancher(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.a = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> B:  # type: ignore[override]
            if x.text:
                return (await self.a(x)).response
            return (await self.a(x)).response

    with pytest.raises(BuildError) as exc:
        await Brancher().abuild()
    assert exc.value.reason == "payload_branch"
    assert "text" in str(exc.value)
    assert "Brancher" in str(exc.value)


async def test_payload_branch_raises_in_nested_composite(cfg) -> None:
    class Inner(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.leaf = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> B:  # type: ignore[override]
            _ = x.text  # payload read in nested composite
            return (await self.leaf(x)).response

    class Outer(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.inner = Inner()

        async def forward(self, x: A) -> B:  # type: ignore[override]
            return (await self.inner(x)).response

    with pytest.raises(BuildError) as exc:
        await Outer().abuild()
    assert exc.value.reason == "payload_branch"
    assert exc.value.agent == "Outer.inner"


async def test_payload_branch_bool_dunder(cfg) -> None:
    class Bool(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.a = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> B:  # type: ignore[override]
            if x:
                return (await self.a(x)).response
            return (await self.a(x)).response

    with pytest.raises(BuildError) as exc:
        await Bool().abuild()
    assert exc.value.reason == "payload_branch"
    assert "__bool__" in str(exc.value)
    assert "test_build.py" in str(exc.value)


async def test_payload_branch_eq_dunder(cfg) -> None:
    class Eq(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.a = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> B:  # type: ignore[override]
            if x == A(text="z"):
                return (await self.a(x)).response
            return (await self.a(x)).response

    with pytest.raises(BuildError) as exc:
        await Eq().abuild()
    assert exc.value.reason == "payload_branch"
    assert "__eq__" in str(exc.value)


async def test_payload_branch_iter_dunder(cfg) -> None:
    class Iter(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.a = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> B:  # type: ignore[override]
            for _item in x:  # type: ignore[attr-defined]
                pass
            return (await self.a(x)).response

    with pytest.raises(BuildError) as exc:
        await Iter().abuild()
    assert exc.value.reason == "payload_branch"
    assert "__iter__" in str(exc.value)


async def test_payload_branch_len_dunder(cfg) -> None:
    class Len(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.a = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> B:  # type: ignore[override]
            if len(x) > 0:  # type: ignore[arg-type]
                return (await self.a(x)).response
            return (await self.a(x)).response

    with pytest.raises(BuildError) as exc:
        await Len().abuild()
    assert exc.value.reason == "payload_branch"
    assert "__len__" in str(exc.value)


async def test_payload_branch_field_read_has_line_info(cfg) -> None:
    class FieldRead(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.a = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> B:  # type: ignore[override]
            _ = x.text
            return (await self.a(x)).response

    with pytest.raises(BuildError) as exc:
        await FieldRead().abuild()
    assert exc.value.reason == "payload_branch"
    assert "text" in str(exc.value)
    assert "test_build.py" in str(exc.value)


async def test_payload_branch_exec_defined_degrades_gracefully(cfg) -> None:
    source = (
        "class ExecComposite(Agent):\n"
        "    input = A\n"
        "    output = B\n"
        "    def __init__(self):\n"
        "        super().__init__(config=None, input=A, output=B)\n"
        "        self.a = FakeLeaf(config=cfg, input=A, output=B)\n"
        "    async def forward(self, x):\n"
        "        if x:\n"
        "            return (await self.a(x)).response\n"
        "        return (await self.a(x)).response\n"
    )
    ns: dict = {"Agent": Agent, "A": A, "B": B, "FakeLeaf": FakeLeaf, "cfg": cfg}
    exec(source, ns)
    composite = ns["ExecComposite"]()

    with pytest.raises(BuildError) as exc:
        await composite.abuild()
    assert exc.value.reason == "payload_branch"
    assert "__bool__" in str(exc.value)


async def test_init_strands_skipped_on_trace_failure(cfg, monkeypatch) -> None:
    from operad.core import build as build_mod

    calls: list[str] = []

    def tracker(a: Agent) -> None:
        calls.append(type(a).__name__)

    monkeypatch.setattr(build_mod, "_init_strands", tracker)

    class Brancher(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.a = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> B:  # type: ignore[override]
            _ = x.text  # triggers payload_branch
            return (await self.a(x)).response

    with pytest.raises(BuildError):
        await Brancher().abuild()
    assert calls == []


async def test_init_strands_runs_after_successful_trace(cfg, monkeypatch) -> None:
    from operad.core import build as build_mod

    calls: list[str] = []

    def tracker(a: Agent) -> None:
        calls.append(type(a).__name__)

    monkeypatch.setattr(build_mod, "_init_strands", tracker)

    class Pipeline(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            return (await self.second((await self.first(x)).response)).response

    await Pipeline().abuild()
    assert set(calls) == {"Pipeline", "FakeLeaf"}


async def test_shared_child_warning(cfg) -> None:
    shared = FakeLeaf(config=cfg, input=A, output=B)

    class TwoSlots(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.first = shared
            self.second = shared

        async def forward(self, x: A) -> B:  # type: ignore[override]
            return (await self.first(x)).response

    with pytest.warns(UserWarning, match="shared"):
        await TwoSlots().abuild()


async def test_unshared_children_emit_no_warning(cfg) -> None:
    import warnings as _warnings

    class Pipeline(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(config=cfg, input=A, output=B)
            self.second = FakeLeaf(config=cfg, input=B, output=C)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            return (await self.second((await self.first(x)).response)).response

    with _warnings.catch_warnings():
        _warnings.simplefilter("error")
        await Pipeline().abuild()


async def test_sentinel_is_instance_of_input() -> None:
    from operad.core.build import _PayloadBranchAccess, _make_sentinel

    sentinel = _make_sentinel(A)
    assert isinstance(sentinel, A)
    with pytest.raises(_PayloadBranchAccess) as exc:
        _ = sentinel.text
    assert exc.value.cls_name == "A"
    assert exc.value.field_name == "text"
