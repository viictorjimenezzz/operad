"""Tests for `operad.Configuration`: backend + host validation, extras."""

from __future__ import annotations
import pytest
from pydantic import ValidationError
from operad import Configuration
from pathlib import Path
import yaml
from operad.agents.reasoning.react import ReAct
from operad.configs import ConfigError, RunConfig, instantiate, load
from operad.configs.loader import _import_by_path
from operad.core.config import Resilience, Runtime, Sampling


# --- from test_configuration.py ---
def test_configuration_minimal_llamacpp() -> None:
    cfg = Configuration(backend="llamacpp", host="127.0.0.1:9000", model="gemma")
    assert cfg.backend == "llamacpp"
    assert cfg.host == "127.0.0.1:9000"
    assert cfg.model == "gemma"
    assert cfg.sampling.temperature == 0.7
    assert cfg.sampling.max_tokens == 2048


def test_configuration_openai_forbids_host() -> None:
    with pytest.raises(ValidationError):
        Configuration(backend="openai", model="gpt-4o", host="example.com")


def test_configuration_llamacpp_requires_host() -> None:
    with pytest.raises(ValidationError):
        Configuration(backend="llamacpp", model="gemma")


def test_configuration_extra_goes_through_extra_field() -> None:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:9000",
        model="x",
        runtime=Runtime(extra={"grammar": "root ::= .", "custom_param": 42}),
    )
    assert cfg.runtime.extra["grammar"] == "root ::= ."
    assert cfg.runtime.extra["custom_param"] == 42


def test_configuration_forbids_unknown_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        Configuration(
            backend="llamacpp",
            host="127.0.0.1:9000",
            model="x",
            grammar="root ::= .",  # type: ignore[call-arg]
        )


def test_configuration_is_mutable() -> None:
    cfg = Configuration(backend="openai", model="gpt-4o")
    cfg.sampling.temperature = 0.2
    assert cfg.sampling.temperature == 0.2


def test_configuration_new_fields_round_trip() -> None:
    cfg = Configuration(
        backend="openai",
        model="gpt-4o",
        resilience=Resilience(timeout=1.5, max_retries=3, backoff_base=1.0),
    )
    assert cfg.resilience.timeout == 1.5
    assert cfg.resilience.max_retries == 3
    assert cfg.resilience.backoff_base == 1.0


def test_configuration_new_fields_defaults() -> None:
    cfg = Configuration(backend="openai", model="gpt-4o")
    assert cfg.resilience.timeout is None
    assert cfg.resilience.max_retries == 0
    assert cfg.resilience.backoff_base == 0.5


def test_configuration_anthropic_forbids_host() -> None:
    with pytest.raises(ValidationError):
        Configuration(
            backend="anthropic",
            model="claude-haiku-4-5",
            host="api.anthropic.com",
        )


def test_configuration_anthropic_accepts_api_key() -> None:
    cfg = Configuration(
        backend="anthropic",
        model="claude-haiku-4-5",
        api_key="sk-ant-test",
        sampling=Sampling(reasoning_tokens=512),
    )
    assert cfg.backend == "anthropic"
    assert cfg.api_key == "sk-ant-test"
    assert cfg.sampling.reasoning_tokens == 512


def test_configuration_still_forbids_unknown_after_new_fields() -> None:
    with pytest.raises(ValidationError):
        Configuration(
            backend="openai",
            model="gpt-4o",
            resilience=Resilience(timeout=1.0, max_retries=2),
            totally_unknown=True,  # type: ignore[call-arg]
        )

# --- from test_configs.py ---
VALID_YAML = {
    "agent": "operad.agents.reasoning.react.ReAct",
    "config": {
        "backend": "llamacpp",
        "host": "127.0.0.1:8080",
        "model": "test-model",
        "sampling": {"temperature": 0.3},
    },
    "runtime": {
        "slots": [
            {"backend": "llamacpp", "host": "127.0.0.1:8080", "limit": 8},
        ]
    },
}


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_load_valid(tmp_path: Path) -> None:
    rc = load(_write(tmp_path, VALID_YAML))
    assert isinstance(rc, RunConfig)
    assert rc.agent == "operad.agents.reasoning.react.ReAct"
    assert rc.config.backend == "llamacpp"
    assert rc.runtime.slots[0].limit == 8


def test_load_example_yaml() -> None:
    root = Path(__file__).resolve().parent.parent.parent
    rc = load(root / "examples" / "config-react.yaml")
    assert rc.agent == "operad.agents.reasoning.react.ReAct"


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load(tmp_path / "does-not-exist.yaml")


def test_load_invalid_yaml(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("key: value:\n  - : bad")
    with pytest.raises(ConfigError):
        load(p)


def test_load_rejects_unknown_keys(tmp_path: Path) -> None:
    bad = dict(VALID_YAML, unknown_key="x")
    with pytest.raises(ConfigError, match="schema error"):
        load(_write(tmp_path, bad))


def test_load_top_level_not_mapping(tmp_path: Path) -> None:
    p = tmp_path / "list.yaml"
    p.write_text("- a\n- b\n")
    with pytest.raises(ConfigError, match="must be a mapping"):
        load(p)


def test_instantiate_returns_react(tmp_path: Path) -> None:
    rc = load(_write(tmp_path, VALID_YAML))
    agent = instantiate(rc)
    assert isinstance(agent, ReAct)
    # ReAct's root carries no config; it's threaded to sub-agents.
    assert agent.reasoner.config is not None
    assert agent.reasoner.config.model == "test-model"


def test_import_by_path_bad_module() -> None:
    with pytest.raises(ConfigError, match="cannot import"):
        _import_by_path("nonexistent_pkg_xyz.SomeClass")


def test_import_by_path_bad_attr() -> None:
    with pytest.raises(ConfigError, match="no attribute"):
        _import_by_path("operad.agents.reasoning.react.NoSuchClass")


def test_import_by_path_not_agent() -> None:
    with pytest.raises(ConfigError, match="not an Agent"):
        _import_by_path("operad.core.config.Configuration")


def test_import_by_path_unqualified() -> None:
    with pytest.raises(ConfigError, match="fully-qualified"):
        _import_by_path("Foo")
