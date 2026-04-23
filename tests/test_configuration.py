"""Tests for `operad.Configuration`: backend + host validation, extras."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from operad import Configuration


def test_configuration_minimal_llamacpp() -> None:
    cfg = Configuration(backend="llamacpp", host="127.0.0.1:9000", model="gemma")
    assert cfg.backend == "llamacpp"
    assert cfg.host == "127.0.0.1:9000"
    assert cfg.model == "gemma"
    assert cfg.temperature == 0.7
    assert cfg.max_tokens == 2048


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
        extra={"grammar": "root ::= .", "custom_param": 42},
    )
    assert cfg.extra["grammar"] == "root ::= ."
    assert cfg.extra["custom_param"] == 42


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
    cfg.temperature = 0.2
    assert cfg.temperature == 0.2
