"""Coverage for `OperadOutput[Out]` — the canonical return envelope.

Exercises: shape, determinism, sensitivity (prompt vs. graph vs.
schema), secret-exclusion in `hash_model`, `run_id` / `agent_path`
correlation with observer events, leaf-root build, composite envelope
hashes coming from the composite (not the last stage), and `None`
defaults for usage fields when the backend doesn't populate them.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from pydantic import BaseModel

from operad import Agent, Configuration, OperadOutput, observers
from operad.core.output import hash_configuration
from operad.runtime.observers.base import AgentEvent, Observer

from .conftest import A, B, C, D, FakeLeaf


_HEX16 = re.compile(r"^[0-9a-f]{16}$")


async def _built(factory):
    agent = factory()
    return await agent.abuild()


async def test_envelope_shape_and_hashes_are_well_formed(cfg: Configuration) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 7})
    await leaf.abuild()

    out = await leaf(A(text="hi"))

    assert isinstance(out, OperadOutput)
    assert isinstance(out.response, B)
    assert out.response.value == 7
    for field in (
        "hash_operad_version",
        "hash_python_version",
        "hash_model",
        "hash_prompt",
        "hash_graph",
        "hash_input",
        "hash_output_schema",
    ):
        value = getattr(out, field)
        if field in ("hash_operad_version", "hash_python_version"):
            assert value  # version strings, not hex
        else:
            assert _HEX16.match(value), f"{field}={value!r}"
    assert out.run_id
    assert out.agent_path == "FakeLeaf"
    assert out.finished_at >= out.started_at
    assert out.latency_ms >= 0.0
    assert out.prompt_tokens is None
    assert out.completion_tokens is None
    assert out.cost_usd is None


async def test_hashes_are_deterministic_across_runs(cfg: Configuration) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    await leaf.abuild()

    out1 = await leaf(A(text="same"))
    out2 = await leaf(A(text="same"))

    assert out1.hash_input == out2.hash_input
    assert out1.hash_prompt == out2.hash_prompt
    assert out1.hash_graph == out2.hash_graph
    assert out1.hash_output_schema == out2.hash_output_schema
    assert out1.hash_model == out2.hash_model
    assert out1.run_id != out2.run_id  # run_id must be per-call


async def test_changing_task_changes_hash_prompt_not_hash_graph(
    cfg: Configuration,
) -> None:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B, task="first", canned={"value": 1})
    leaf2 = FakeLeaf(config=cfg, input=A, output=B, task="second", canned={"value": 1})
    await leaf1.abuild()
    await leaf2.abuild()

    out1 = await leaf1(A(text="x"))
    out2 = await leaf2(A(text="x"))

    assert out1.hash_prompt != out2.hash_prompt
    assert out1.hash_graph == out2.hash_graph
    assert out1.hash_input == out2.hash_input


async def test_changing_output_schema_changes_hash_output_schema(
    cfg: Configuration,
) -> None:
    leaf_b = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    leaf_c = FakeLeaf(config=cfg, input=A, output=C, canned={"label": "x"})
    await leaf_b.abuild()
    await leaf_c.abuild()

    out_b = await leaf_b(A(text="same"))
    out_c = await leaf_c(A(text="same"))

    assert out_b.hash_output_schema != out_c.hash_output_schema
    assert out_b.hash_input == out_c.hash_input


async def test_changing_input_payload_changes_hash_input(cfg: Configuration) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    await leaf.abuild()

    out1 = await leaf(A(text="alpha"))
    out2 = await leaf(A(text="beta"))

    assert out1.hash_input != out2.hash_input
    assert out1.hash_prompt != out2.hash_prompt  # prompt contains rendered input
    assert out1.hash_graph == out2.hash_graph


def test_hash_model_excludes_api_key() -> None:
    with_key = Configuration(
        backend="openai", model="gpt-4o", api_key="SECRET_A", temperature=0.0
    )
    other_key = Configuration(
        backend="openai", model="gpt-4o", api_key="SECRET_B", temperature=0.0
    )
    different_model = Configuration(
        backend="openai", model="gpt-4.1", api_key="SECRET_A", temperature=0.0
    )

    assert hash_configuration(with_key) == hash_configuration(other_key)
    assert hash_configuration(with_key) != hash_configuration(different_model)


async def test_run_id_and_agent_path_match_observer_event(cfg: Configuration) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    await leaf.abuild()

    captured: list[AgentEvent] = []

    class _Capture(Observer):
        async def on_event(self, event: AgentEvent) -> None:
            captured.append(event)

    obs = _Capture()
    observers.register(obs)
    try:
        out = await leaf(A(text="hi"))
    finally:
        observers.unregister(obs)

    end_events = [e for e in captured if e.kind == "end"]
    assert end_events, "observer never saw an 'end' event"
    assert end_events[-1].run_id == out.run_id
    assert end_events[-1].agent_path == out.agent_path


async def test_leaf_as_root_produces_well_formed_envelope(cfg: Configuration) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 42})
    await leaf.abuild()

    out = await leaf(A(text="hi"))

    assert isinstance(out, OperadOutput)
    assert out.response.value == 42
    assert out.agent_path == "FakeLeaf"
    for field in (
        "hash_model",
        "hash_prompt",
        "hash_input",
        "hash_output_schema",
        "hash_graph",
    ):
        assert _HEX16.match(getattr(out, field))


async def test_pipeline_envelope_is_the_composites_own(cfg: Configuration) -> None:
    from operad import Pipeline

    first = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 3})
    second = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "done"})
    pipe = Pipeline(first, second, input=A, output=C)
    await pipe.abuild()

    out = await pipe(A(text="go"))

    assert isinstance(out, OperadOutput)
    assert out.response.label == "done"
    # Composite's hash_model is the sentinel value for composites.
    assert out.hash_model == "composite"
    assert out.agent_path == "Pipeline"
    # Pipeline's own hash_output_schema matches C, not B.
    from operad.core.output import hash_output_schema

    assert out.hash_output_schema == hash_output_schema(C)


async def test_usage_fields_default_to_none_for_composites(
    cfg: Configuration,
) -> None:
    from operad import Pipeline

    first = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    pipe = Pipeline(first, input=A, output=B)
    await pipe.abuild()

    out = await pipe(A(text="x"))

    assert out.prompt_tokens is None
    assert out.completion_tokens is None
    assert out.cost_usd is None


async def test_envelope_json_serialises(cfg: Configuration) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 99})
    await leaf.abuild()

    out = await leaf(A(text="hi"))
    dumped = out.model_dump(mode="json")

    assert dumped["response"] == {"value": 99}
    assert "hash_input" in dumped
    assert "api_key" not in out.model_dump_json()  # secret never leaks
