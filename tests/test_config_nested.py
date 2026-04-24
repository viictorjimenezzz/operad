"""Contract tests for the nested `Configuration` shape (Wave 3 brief 3-4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from operad import Configuration
from operad.core.config import IOConfig, Resilience, Runtime, Sampling
from operad.utils.hashing import hash_config


def test_construct_from_nested_json() -> None:
    payload = {
        "backend": "openai",
        "model": "gpt-4o-mini",
        "api_key": "sk-x",
        "sampling": {"temperature": 0.3, "max_tokens": 128},
        "resilience": {"timeout": 1.5, "max_retries": 2, "backoff_base": 0.25},
        "io": {"stream": True, "structuredio": False, "renderer": "markdown"},
        "runtime": {"extra": {"grammar": "root ::= ."}},
    }
    cfg = Configuration(**payload)
    assert cfg.sampling.temperature == 0.3
    assert cfg.sampling.max_tokens == 128
    assert cfg.resilience.timeout == 1.5
    assert cfg.io.stream is True
    assert cfg.io.renderer == "markdown"
    assert cfg.runtime.extra["grammar"] == "root ::= ."


def test_flat_construction_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Configuration(
            backend="openai",
            model="gpt-4o-mini",
            api_key="sk-x",
            temperature=0.5,  # type: ignore[call-arg]
        )


def test_default_factories_populate_subblocks() -> None:
    cfg = Configuration(backend="openai", model="gpt-4o-mini", api_key="sk-x")
    assert isinstance(cfg.sampling, Sampling)
    assert cfg.sampling.temperature == 0.7
    assert cfg.sampling.max_tokens == 2048
    assert isinstance(cfg.resilience, Resilience)
    assert cfg.resilience.max_retries == 0
    assert cfg.resilience.backoff_base == 0.5
    assert isinstance(cfg.io, IOConfig)
    assert cfg.io.stream is False
    assert cfg.io.structuredio is True
    assert cfg.io.renderer == "xml"
    assert isinstance(cfg.runtime, Runtime)
    assert cfg.runtime.extra == {}


def test_host_validator_still_runs() -> None:
    with pytest.raises(ValidationError):
        Configuration(backend="llamacpp", model="x")
    with pytest.raises(ValidationError):
        Configuration(
            backend="openai", model="x", api_key="y", host="example.com"
        )


def test_extra_field_rejection_inside_subblocks() -> None:
    with pytest.raises(ValidationError):
        Configuration(
            backend="openai",
            model="gpt-4o-mini",
            api_key="sk-x",
            sampling={"temparature": 0.7},  # typo
        )
    with pytest.raises(ValidationError):
        Configuration(
            backend="openai",
            model="gpt-4o-mini",
            api_key="sk-x",
            io={"strem": True},  # typo
        )


def test_hash_config_stable_under_round_trip() -> None:
    cfg = Configuration(
        backend="openai",
        model="gpt-4o-mini",
        api_key="sk-x",
        sampling=Sampling(temperature=0.4, max_tokens=256),
        resilience=Resilience(timeout=2.0, max_retries=1),
    )
    dumped = cfg.model_dump(mode="json")
    roundtripped = Configuration.model_validate(dumped)
    assert hash_config(cfg) == hash_config(roundtripped)


def test_local_config_round_trip() -> None:
    import importlib.util
    import sys
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "examples._config",
        Path(__file__).resolve().parent.parent / "examples" / "_config.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["examples._config"] = module
    spec.loader.exec_module(module)
    local_config = module.local_config

    cfg = local_config(sampling=Sampling(temperature=0.25))
    assert cfg.backend == "llamacpp"
    assert cfg.sampling.temperature == 0.25
    assert cfg.sampling.max_tokens == 2048
