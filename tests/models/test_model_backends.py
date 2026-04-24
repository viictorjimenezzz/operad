"""Offline tests for Wave 2 backends: Gemini, HuggingFace, Batch."""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from operad import Configuration
from operad.core.models import BatchHandle, resolve_model
from operad.utils.hashing import hash_config


def _install_fake_google_genai(monkeypatch: pytest.MonkeyPatch) -> None:
    google_pkg = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")

    class _Client:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    genai_mod.Client = _Client  # type: ignore[attr-defined]
    # strands.models.gemini accesses many symbols off `google.genai.types`
    # at import time; MagicMock lets any attribute access succeed.
    genai_types: Any = MagicMock()
    genai_mod.types = genai_types  # type: ignore[attr-defined]
    google_pkg.genai = genai_mod  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", genai_types)
    # strands.models.gemini is cached after a first successful import;
    # drop it so our fake google.genai is used.
    monkeypatch.delitem(sys.modules, "strands.models.gemini", raising=False)


def test_gemini_resolver_returns_gemini_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("strands.models")
    # If strands.models.gemini was already imported, honor that path.
    # Otherwise stand up a fake google.genai so the import in strands works.
    if "strands.models.gemini" not in sys.modules:
        _install_fake_google_genai(monkeypatch)

    cfg = Configuration(
        backend="gemini",
        model="gemini-1.5-pro",
        api_key="sk-fake",
        temperature=0.2,
        max_tokens=64,
        top_p=0.9,
    )
    model = resolve_model(cfg)
    assert model.__class__.__name__ == "GeminiModel"
    assert model.client_args["api_key"] == "sk-fake"
    assert model.config["model_id"] == "gemini-1.5-pro"
    params = model.config["params"]
    assert params["temperature"] == 0.2
    assert params["max_output_tokens"] == 64
    assert params["top_p"] == 0.9


def test_gemini_missing_extra_raises_clear_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "strands.models.gemini", raising=False)
    monkeypatch.delitem(sys.modules, "google.genai", raising=False)
    monkeypatch.delitem(sys.modules, "google", raising=False)

    # Block future imports of google.genai.
    import builtins

    real_import = builtins.__import__

    def _blocked(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "google" or name.startswith("google."):
            raise ImportError(f"blocked: {name}")
        if name == "strands.models.gemini":
            raise ImportError("blocked: strands.models.gemini")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)

    cfg = Configuration(
        backend="gemini", model="gemini-1.5-pro", api_key="x"
    )
    with pytest.raises(ImportError, match=r"\[gemini\]"):
        resolve_model(cfg)


def test_huggingface_resolver_returns_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_pipeline = MagicMock(return_value=[{"generated_text": "hi"}])
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.pipeline = MagicMock(return_value=fake_pipeline)  # type: ignore[attr-defined]
    fake_transformers.set_seed = MagicMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    cfg = Configuration(
        backend="huggingface",
        model="sshleifer/tiny-gpt2",
        temperature=0.0,
        max_tokens=8,
        seed=42,
    )
    model = resolve_model(cfg)
    assert model.__class__.__name__ == "_HuggingFaceModel"
    assert model.config["model_id"] == "sshleifer/tiny-gpt2"
    fake_transformers.set_seed.assert_called_once_with(42)  # type: ignore[attr-defined]


def test_huggingface_missing_extra_raises_clear_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "transformers", raising=False)

    import builtins

    real_import = builtins.__import__

    def _blocked(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "transformers" or name.startswith("transformers."):
            raise ImportError(f"blocked: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)

    cfg = Configuration(backend="huggingface", model="tiny")
    with pytest.raises(ImportError, match=r"\[huggingface\]"):
        resolve_model(cfg)


def test_batch_flag_requires_batch_backend() -> None:
    with pytest.raises(ValidationError, match="batch=True"):
        Configuration(
            backend="llamacpp",
            host="127.0.0.1:8080",
            model="gemma",
            batch=True,
        )


async def test_batch_handle_shape_from_openai_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_batch = MagicMock()
    fake_batch.model_dump.return_value = {
        "id": "batch_abc123",
        "status": "validating",
    }
    client = MagicMock()
    client.batches.create = AsyncMock(return_value=fake_batch)

    import openai

    monkeypatch.setattr(openai, "AsyncOpenAI", MagicMock(return_value=client))

    cfg = Configuration(
        backend="openai",
        model="gpt-4o-mini",
        api_key="sk-fake",
        batch=True,
    )
    model = resolve_model(cfg)
    handle = await model.forward(
        {
            "input_file_id": "file_abc",
            "endpoint": "/v1/chat/completions",
        }
    )
    assert isinstance(handle, BatchHandle)
    assert handle.provider == "openai"
    assert handle.provider_batch_id == "batch_abc123"
    assert handle.endpoint == "/v1/chat/completions"


def test_backend_literal_includes_gemini_and_huggingface() -> None:
    cfg_g = Configuration(backend="gemini", model="gemini-1.5-pro", api_key="x")
    cfg_h = Configuration(backend="huggingface", model="sshleifer/tiny-gpt2")
    assert cfg_g.backend == "gemini"
    assert cfg_h.backend == "huggingface"


def test_hash_config_distinguishes_batch_mode() -> None:
    cfg_live = Configuration(
        backend="openai", model="gpt-4o-mini", api_key="sk-x"
    )
    cfg_batch = Configuration(
        backend="openai", model="gpt-4o-mini", api_key="sk-x", batch=True
    )
    assert hash_config(cfg_live) != hash_config(cfg_batch)
