"""Tests for the XML-tagged prompt renderer.

The renderer reads directly off `Agent` state (no Prompt wrapper) and
surfaces Pydantic `Field(description=...)` from both `In` and `Out`.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from operad import Agent, Example
from operad.core import render
from typing import ClassVar
from operad import Agent, Configuration
import pytest
from operad import Configuration
from operad.core.config import IOConfig, Sampling
from operad.agents.reasoning.components.reasoner import Reasoner
from operad.utils.errors import BuildError
from .._helpers.spy_strands import StrandsSpy, install_spy
from typing import Any
from pydantic import BaseModel
from operad.agents.reasoning.components.classifier import Classifier
from operad.agents.reasoning.components.critic import Critic
from operad.agents.reasoning.components.router import Router
from ..conftest import A, B, FakeLeaf


# --- from test_rendering.py ---
class _Question(BaseModel):
    """A user question with optional topic hint."""

    text: str = Field(default="", description="The user's question.")
    topic: str = Field(default="", description="Optional topic hint.")


class _Answer(BaseModel):
    """A reasoned answer."""

    reasoning: str = Field(default="", description="Step-by-step deliberation.")
    answer: str = Field(default="", description="Final answer, concise.")


def _agent(**overrides) -> Agent:
    class Leaf(Agent):
        input = _Question
        output = _Answer

    return Leaf(config=None, **overrides)


def test_render_system_omits_empty_sections() -> None:
    out = render.render_system(_agent())
    assert "<role" not in out
    assert "<task" not in out
    assert "<rules" not in out
    assert "<examples" not in out
    assert "<output_schema" in out  # always included


def test_render_system_includes_section_descriptions() -> None:
    out = render.render_system(_agent(role="r", task="t", rules=["a"]))
    assert "<role" in out and 'desc="Persona' in out
    assert "<task" in out and "desc" in out
    assert "<rules" in out
    assert "- a" in out


def test_render_system_includes_output_schema_with_field_descs() -> None:
    out = render.render_system(_agent())
    assert '<output_schema desc="A reasoned answer."' in out
    assert 'name="reasoning"' in out
    assert 'desc="Step-by-step deliberation."' in out
    assert 'name="answer"' in out
    assert 'desc="Final answer, concise."' in out


def test_render_user_surfaces_in_field_descriptions() -> None:
    x = _Question(text="what is 2+2?", topic="math")
    out = render.render_input(x)
    assert 'desc="A user question with optional topic hint."' in out
    assert '<text desc="The user\'s question.">what is 2+2?</text>' in out
    assert '<topic desc="Optional topic hint.">math</topic>' in out


def test_render_user_xml_escapes_values() -> None:
    x = _Question(text="<script>alert('xss')</script>")
    out = render.render_input(x)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_examples_block_serializes_typed_pairs() -> None:
    ex = Example[_Question, _Answer](
        input=_Question(text="q1", topic="t1"),
        output=_Answer(reasoning="r", answer="a"),
    )
    out = render.render_system(_agent(examples=[ex]))
    assert "<examples" in out
    assert "<example>" in out
    assert "<text" in out and "q1" in out
    assert "<reasoning" in out and "a" in out


def test_render_system_joins_sections_with_blank_lines() -> None:
    out = render.render_system(_agent(role="r", task="t"))
    assert "</role>\n\n<task" in out


def test_render_system_includes_context_when_set() -> None:
    out = render.render_system(
        _agent(role="r", task="t", context="user is a senior engineer")
    )
    assert "<context" in out
    assert "user is a senior engineer" in out
    # Context sits between task and rules/examples.
    assert out.index("<task") < out.index("<context")


def test_render_system_omits_context_when_blank() -> None:
    out = render.render_system(_agent(role="r", task="t"))
    assert "<context" not in out


def test_render_system_markdown_includes_context_when_set() -> None:
    from operad.core.render import markdown as md

    out = md.render_system(_agent(role="r", task="t", context="hello"))
    assert "# Context\nhello" in out


def test_agent_context_survives_clone_override() -> None:
    agent = _agent(role="r", task="t", context="initial")
    cloned = agent.clone(context="overridden")
    assert agent.context == "initial"
    assert cloned.context == "overridden"


def test_agent_context_survives_state_round_trip() -> None:
    agent = _agent(role="r", task="t", context="keep me")
    state = agent.state()
    fresh = _agent(role="r", task="t")
    fresh.load_state(state)
    assert fresh.context == "keep me"

# --- from test_renderers.py ---
class _Question_test_renderers(BaseModel):
    """A user question."""

    text: str = Field(default="", description="The user's question.")


class _Answer_test_renderers(BaseModel):
    """A reasoned answer."""

    reasoning: str = Field(default="", description="Step-by-step deliberation.")
    answer: str = Field(default="", description="Final answer, concise.")


def _leaf_cls() -> type[Agent]:
    class Leaf(Agent):
        input = _Question_test_renderers
        output = _Answer_test_renderers
        role = "You are a careful reasoner."
        task = "Work through the problem step-by-step."
        rules = ("Show reasoning before the final answer.",)

    return Leaf


def _cfg(renderer: str = "xml") -> Configuration:
    return Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        io=IOConfig(renderer=renderer),  # type: ignore[arg-type]
    )


def test_markdown_render_surfaces_field_descriptions_and_rules() -> None:
    agent = _leaf_cls()(config=None)
    out = render.markdown.render_system(agent)

    assert "# Role" in out
    assert "# Task" in out
    assert "# Rules" in out
    assert "- Show reasoning before the final answer." in out
    assert "# Output schema" in out
    # every Out Field(description=...) surfaces
    assert "Step-by-step deliberation." in out
    assert "Final answer, concise." in out
    # field names are in the table
    assert "| reasoning |" in out
    assert "| answer |" in out


def test_chat_render_returns_list_with_system_message_carrying_schema() -> None:
    agent = _leaf_cls()(config=None)
    out = render.chat.render_system(agent)

    assert isinstance(out, list)
    assert len(out) >= 1
    first = out[0]
    assert first["role"] == "system"
    assert "<output_schema" in first["content"]


def test_configuration_markdown_selects_markdown_path() -> None:
    agent = _leaf_cls()(config=_cfg("markdown"))
    msg = agent.format_system_message()

    assert isinstance(msg, str)
    assert "# Role" in msg
    assert "<role" not in msg  # not the XML path


def test_classvar_override_wins_over_configuration() -> None:
    class MarkdownLeaf(_leaf_cls()):  # type: ignore[misc,valid-type]
        renderer: ClassVar[str] = "markdown"

    agent = MarkdownLeaf(config=_cfg("xml"))
    msg = agent.format_system_message()

    assert isinstance(msg, str)
    assert "# Role" in msg
    assert "<role" not in msg


def test_default_remains_xml() -> None:
    agent = _leaf_cls()(config=_cfg("xml"))
    msg = agent.format_system_message()
    assert isinstance(msg, str)
    assert "<role" in msg

# --- from test_structuredio.py ---
class Question(BaseModel):
    text: str = Field("", description="The question posed by the user.")


class Answer(BaseModel):
    reasoning: str = Field("", description="Chain-of-thought deliberation.")
    final: str = Field("", description="The final answer committed to.")


FIELD_DESCRIPTIONS = [
    "The question posed by the user.",
    "Chain-of-thought deliberation.",
    "The final answer committed to.",
]


async def _build(structuredio: bool) -> Reasoner:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        sampling=Sampling(temperature=0.0, max_tokens=16),
        io=IOConfig(structuredio=structuredio),
    )
    agent = Reasoner(config=cfg, input=Question, output=Answer)
    return await agent.abuild()


@pytest.mark.asyncio
async def test_structuredio_true_passes_model_and_descriptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = await _build(structuredio=True)
    spy = install_spy(
        monkeypatch,
        StrandsSpy(canned_structured=Answer(reasoning="r", final="42")),
    )

    envelope = await agent(Question(text="q?"))

    assert envelope.response.final == "42"
    assert spy.last_kwargs.get("structured_output_model") is Answer
    user_msg = spy.last_args[0]
    assert isinstance(user_msg, str)
    assert "The question posed by the user." in user_msg


@pytest.mark.asyncio
async def test_structuredio_false_omits_model_keeps_descriptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = await _build(structuredio=False)
    canned = Answer(reasoning="r", final="42").model_dump_json()
    spy = install_spy(monkeypatch, StrandsSpy(canned_text=canned))

    envelope = await agent(Question(text="q?"))

    assert envelope.response.final == "42"
    assert "structured_output_model" not in spy.last_kwargs
    user_msg = spy.last_args[0]
    assert "The question posed by the user." in user_msg

    system_msg = agent.format_system_message()
    for desc in FIELD_DESCRIPTIONS[1:]:
        assert desc in system_msg
    assert "<output_schema" in system_msg


@pytest.mark.asyncio
async def test_structuredio_false_malformed_raises_output_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = await _build(structuredio=False)
    install_spy(monkeypatch, StrandsSpy(canned_text="not json at all"))

    with pytest.raises(BuildError) as exc:
        await agent(Question(text="q?"))
    assert exc.value.reason == "output_mismatch"

# --- from test_default_sampling.py ---
def _bare_cfg(**sampling_overrides: Any) -> Configuration:
    """A Configuration with no sampling fields set unless overridden."""
    if sampling_overrides:
        return Configuration(
            backend="openai",
            model="gpt-4o-mini",
            api_key="sk-test",
            sampling=Sampling(**sampling_overrides),
        )
    return Configuration(backend="openai", model="gpt-4o-mini", api_key="sk-test")


def test_default_sampling_fills_unset_fields() -> None:
    leaf = Classifier(config=_bare_cfg(), input=A, output=B)
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.0
    assert leaf.config.sampling.max_tokens == 128


def test_user_value_wins_over_default() -> None:
    leaf = Classifier(
        config=_bare_cfg(temperature=0.9), input=A, output=B
    )
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.9
    assert leaf.config.sampling.max_tokens == 128


def test_user_max_tokens_wins_over_default() -> None:
    leaf = Classifier(
        config=_bare_cfg(max_tokens=999), input=A, output=B
    )
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.0
    assert leaf.config.sampling.max_tokens == 999


def test_config_none_is_passthrough() -> None:
    class Composite(Agent):
        input = A
        output = B

    node = Composite()
    assert node.config is None


def test_base_agent_has_empty_default_sampling() -> None:
    assert Agent.default_sampling == {}


def test_fakeleaf_inherits_empty_default_sampling() -> None:
    cfg = _bare_cfg(temperature=0.42, max_tokens=7)
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.42
    assert leaf.config.sampling.max_tokens == 7


def test_callers_config_is_not_mutated_in_place() -> None:
    cfg = _bare_cfg()
    original_temp = cfg.sampling.temperature
    original_max = cfg.sampling.max_tokens
    leaf = Classifier(config=cfg, input=A, output=B)
    assert cfg.sampling.temperature == original_temp
    assert cfg.sampling.max_tokens == original_max
    assert leaf.config is not cfg


def test_reasoner_default_temperature() -> None:
    leaf = Reasoner(config=_bare_cfg(), input=A, output=B)
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.7


def test_critic_defaults() -> None:
    leaf = Critic(config=_bare_cfg())
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.0
    assert leaf.config.sampling.max_tokens == 512


def test_router_defaults() -> None:
    leaf = Router(config=_bare_cfg())
    assert leaf.config is not None
    assert leaf.config.sampling.temperature == 0.0
    assert leaf.config.sampling.max_tokens == 64
