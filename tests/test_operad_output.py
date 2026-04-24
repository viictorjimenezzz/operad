"""Tests for `OperadOutput`: hash stability, envelope shape, run correlation."""

from __future__ import annotations

import pytest

from operad import Configuration, OperadOutput
from operad.utils.hashing import hash_config, hash_json, hash_schema, hash_str
from operad.runtime.observers import base as _obs

from tests.conftest import A, B, FakeLeaf




def test_hash_str_deterministic_and_16_hex() -> None:
    h = hash_str("hello")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)
    assert h == hash_str("hello")
    assert h != hash_str("world")


def test_hash_config_excludes_api_key() -> None:
    a = Configuration(backend="openai", model="gpt-4o", api_key="sk-a")
    b = Configuration(backend="openai", model="gpt-4o", api_key="sk-b")
    assert hash_config(a) == hash_config(b)
    c = Configuration(backend="openai", model="gpt-4o-mini", api_key="sk-a")
    assert hash_config(a) != hash_config(c)


def test_hash_config_strips_host_auth() -> None:
    auth = Configuration(backend="llamacpp", model="m", host="u:p@127.0.0.1:9000")
    plain = Configuration(backend="llamacpp", model="m", host="127.0.0.1:9000")
    assert hash_config(auth) == hash_config(plain)

    scheme_auth = Configuration(backend="llamacpp", model="m", host="http://u:p@host/x")
    scheme_plain = Configuration(backend="llamacpp", model="m", host="http://host/x")
    assert hash_config(scheme_auth) == hash_config(scheme_plain)


def test_hash_schema_is_stable() -> None:
    assert hash_schema(A) == hash_schema(A)
    assert hash_schema(A) != hash_schema(B)


def test_hash_json_is_key_order_insensitive() -> None:
    assert hash_json({"a": 1, "b": 2}) == hash_json({"b": 2, "a": 1})


def test_envelope_roundtrips_via_pydantic() -> None:
    env = OperadOutput[B].model_construct(response=B(value=7), run_id="r1")
    dumped = env.model_dump(mode="json")
    loaded = OperadOutput[B].model_validate(dumped)
    assert loaded.response.value == 7
    assert loaded.run_id == "r1"


@pytest.mark.asyncio
async def test_envelope_is_populated_by_invoke(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 3}).abuild()
    out = await leaf(A(text="hi"))
    assert isinstance(out, OperadOutput)
    assert out.response.value == 3
    assert out.run_id
    assert out.agent_path == "FakeLeaf"
    assert out.hash_operad_version
    assert out.hash_python_version
    assert out.hash_graph
    assert out.hash_input
    assert out.hash_output_schema
    assert out.started_at > 0
    assert out.finished_at >= out.started_at
    assert out.latency_ms >= 0


@pytest.mark.asyncio
async def test_same_input_yields_same_hashes(cfg) -> None:
    leaf1 = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}).abuild()
    leaf2 = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}).abuild()
    x = A(text="same")
    a = await leaf1(x)
    b = await leaf2(x)
    assert a.hash_input == b.hash_input
    assert a.hash_graph == b.hash_graph
    assert a.hash_output_schema == b.hash_output_schema
    assert a.run_id != b.run_id


@pytest.mark.asyncio
async def test_task_override_changes_hash_prompt(cfg) -> None:
    l1 = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}, task="t1").abuild()
    l2 = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}, task="t2").abuild()
    a = await l1(A(text="x"))
    b = await l2(A(text="x"))
    assert a.hash_prompt != b.hash_prompt
    assert a.hash_graph == b.hash_graph


@pytest.mark.asyncio
async def test_run_id_correlates_with_observer(cfg) -> None:
    seen: list[str] = []

    class _Collector:
        async def on_event(self, event: _obs.AgentEvent) -> None:
            seen.append(event.run_id)

    _obs.registry.register(_Collector())
    try:
        leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}).abuild()
        out = await leaf(A(text="x"))
        assert len(seen) == 2
        assert seen[0] == seen[1] == out.run_id
    finally:
        _obs.registry.clear()
