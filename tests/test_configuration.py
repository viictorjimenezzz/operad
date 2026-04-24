"""Tests for `operad.Configuration`: backend + host validation, extras."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from operad import Configuration
from operad.core.config import Resilience, Runtime, Sampling


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
