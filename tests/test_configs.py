"""Tests for `operad.configs` schema + loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from operad.agents.reasoning.react import ReAct
from operad.configs import ConfigError, RunConfig, instantiate, load
from operad.configs.loader import _import_by_path


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
    root = Path(__file__).resolve().parent.parent
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
