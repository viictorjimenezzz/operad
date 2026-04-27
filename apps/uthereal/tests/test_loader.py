from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest
from operad import Agent
from pydantic import BaseModel

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from apps_uthereal.leaves._common import (  # noqa: E402
    CLOSURE_SEPARATOR,
    LoaderError,
    dump_yaml,
    load_yaml,
    parse_examples,
    split_closure_from_task,
)


FIXTURES = Path(__file__).parent / "fixtures" / "yamls"


class FakeLeafIn(BaseModel):
    question: str = ""


class FakeLeafOut(BaseModel):
    answer: str = ""


class FakeLeaf(Agent[FakeLeafIn, FakeLeafOut]):
    input = FakeLeafIn
    output = FakeLeafOut


class StrictLeafOut(BaseModel):
    answer: str


class StrictLeaf(Agent[FakeLeafIn, StrictLeafOut]):
    input = FakeLeafIn
    output = StrictLeafOut


class MultiFieldIn(BaseModel):
    question: str = ""
    context: str = ""
    note: str = "default"


class MultiFieldLeaf(Agent[MultiFieldIn, FakeLeafOut]):
    input = MultiFieldIn
    output = FakeLeafOut


def test_load_minimal_yaml_returns_typed_agent() -> None:
    agent = load_yaml(FIXTURES / "fake_leaf.yaml", FakeLeaf)

    assert isinstance(agent, FakeLeaf)
    assert agent.role == "You are a fake.\n"
    assert agent.task.startswith("Do fake things.")
    assert list(agent.rules) == ["Always be fake.", "Never be real."]
    assert agent.examples[0].input == FakeLeafIn(
        question="<question>What is fake?</question>"
    )
    assert agent.examples[0].output == FakeLeafOut(answer="Everything fake.")
    assert agent.config is not None
    assert agent.config.backend == "gemini"


def test_closure_merged_into_task() -> None:
    agent = load_yaml(FIXTURES / "fake_leaf_with_closure.yaml", FakeLeaf)

    assert CLOSURE_SEPARATOR in agent.task
    assert agent.task.endswith("Return an answer field.\nDo not include extra keys.\n")


def test_split_closure_inverse() -> None:
    task = f"Do the work.{CLOSURE_SEPARATOR}Return JSON."

    assert split_closure_from_task(task) == ("Do the work.", "Return JSON.")
    assert split_closure_from_task("Do the work.") == ("Do the work.", "")


def test_round_trip_preserves_hash_content(tmp_path: Path) -> None:
    source = FIXTURES / "fake_leaf.yaml"
    agent = load_yaml(source, FakeLeaf)
    out = tmp_path / "round_trip.yaml"

    dump_yaml(agent, out)
    loaded = load_yaml(out, FakeLeaf)

    assert loaded.hash_content == agent.hash_content


def test_round_trip_preserves_byte_equality_when_unchanged(tmp_path: Path) -> None:
    source = FIXTURES / "fake_leaf.yaml"
    agent = load_yaml(source, FakeLeaf)
    out = tmp_path / "unchanged.yaml"

    dump_yaml(agent, out, source_path=source)

    assert out.read_bytes().rstrip(b"\n") == source.read_bytes().rstrip(b"\n")


def test_round_trip_preserves_comments(tmp_path: Path) -> None:
    source = FIXTURES / "fake_leaf.yaml"
    agent = load_yaml(source, FakeLeaf)
    out = tmp_path / "comments.yaml"

    dump_yaml(agent, out, source_path=source)

    text = out.read_text()
    assert "# fixture comment" in text
    assert "# prompt comment" in text


def test_round_trip_preserves_block_style(tmp_path: Path) -> None:
    source = FIXTURES / "fake_leaf.yaml"
    agent = load_yaml(source, FakeLeaf)
    out = tmp_path / "block_style.yaml"

    dump_yaml(agent, out, source_path=source)

    assert "role: |" in out.read_text()


def test_unknown_tier_raises_LoaderError(tmp_path: Path) -> None:
    source = FIXTURES / "fake_leaf.yaml"
    bad = tmp_path / "unknown_tier.yaml"
    bad.write_text(source.read_text().replace('"fast"', '"slow"'))

    with pytest.raises(LoaderError) as exc_info:
        load_yaml(bad, FakeLeaf)

    assert exc_info.value.reason == "unknown_tier"
    assert exc_info.value.tier == "slow"


def test_missing_prompt_raises_LoaderError(tmp_path: Path) -> None:
    bad = tmp_path / "missing_prompt.yaml"
    bad.write_text('config:\n  llm_tier: "fast"\n')

    with pytest.raises(LoaderError) as exc_info:
        load_yaml(bad, FakeLeaf)

    assert exc_info.value.reason == "missing_field"
    assert exc_info.value.field == "prompt"


def test_examples_with_invalid_output_dropped_in_non_strict(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = FIXTURES / "fake_leaf.yaml"
    bad = tmp_path / "invalid_example.yaml"
    bad.write_text(
        source.read_text().replace('answer: "Everything fake."', 'wrong: "x"')
    )

    with caplog.at_level(logging.WARNING, logger="apps_uthereal.leaves._common"):
        agent = load_yaml(bad, StrictLeaf)

    assert agent.examples == []
    assert "Dropping YAML example 0" in caplog.text


def test_examples_with_invalid_output_raise_in_strict(tmp_path: Path) -> None:
    source = FIXTURES / "fake_leaf.yaml"
    bad = tmp_path / "invalid_example.yaml"
    bad.write_text(
        source.read_text().replace('answer: "Everything fake."', 'wrong: "x"')
    )

    with pytest.raises(LoaderError) as exc_info:
        load_yaml(bad, StrictLeaf, strict_examples=True)

    assert exc_info.value.reason == "example_validation_failed"
    assert exc_info.value.index == 0


@pytest.mark.parametrize(
    ("raw_input", "expected"),
    [
        (
            "<question>What?</question><context>Here.</context>",
            {"question": "What?", "context": "Here.", "note": "default"},
        ),
        (
            "<context>Line 1\nLine 2</context>\n<question>Why?</question>",
            {"question": "Why?", "context": "Line 1\nLine 2", "note": "default"},
        ),
        (
            "<ignored>x</ignored><question>Only this</question>",
            {"question": "Only this", "context": "", "note": "default"},
        ),
    ],
)
def test_example_tag_parser_extracts_fields_correctly(
    raw_input: str,
    expected: dict[str, str],
) -> None:
    examples = parse_examples(
        [{"input": raw_input, "output": {"answer": "ok"}}],
        MultiFieldLeaf,
    )

    assert examples[0].input.model_dump() == expected


def test_example_tag_parser_handles_missing_fields_with_defaults() -> None:
    examples = parse_examples(
        [{"input": "<context>Only context</context>", "output": {"answer": "ok"}}],
        MultiFieldLeaf,
    )

    assert examples[0].input == MultiFieldIn(context="Only context")


def test_dump_includes_unrecognized_yaml_keys(tmp_path: Path) -> None:
    source = FIXTURES / "fake_leaf.yaml"
    agent = load_yaml(source, FakeLeaf)
    agent.role = "Updated role."
    out = tmp_path / "metadata.yaml"

    dump_yaml(agent, out)

    text = out.read_text()
    assert "agent_name: FakeLeaf" in text
    assert "instrument: true" in text
    assert "tracer_inputs:" in text
    assert "Updated role." in text


def test_load_propagates_config_overrides() -> None:
    agent = load_yaml(
        FIXTURES / "fake_leaf.yaml",
        FakeLeaf,
        config_overrides={"sampling": {"temperature": 0.2}},
    )

    assert agent.config is not None
    assert agent.config.sampling.temperature == 0.2
