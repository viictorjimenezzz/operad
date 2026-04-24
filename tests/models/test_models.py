"""Tests for the backend resolver.

Each backend's `build(cfg)` should hand back the right strands class with
sampling params threaded through — no silent drops.
"""

from __future__ import annotations
import pytest
from operad import Configuration
from operad.core.models import resolve_model
import importlib


# --- from test_models.py ---
def test_llamacpp_resolver_threads_params() -> None:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:9000",
        model="gemma-3-27b",
        temperature=0.1,
        max_tokens=128,
        top_p=0.9,
        top_k=40,
        seed=7,
        stop=["</end>"],
        extra={"mirostat": 2},
    )
    model = resolve_model(cfg)
    assert model.__class__.__name__ == "LlamaCppModel"
    assert model.base_url == "http://127.0.0.1:9000"
    assert model.config["model_id"] == "gemma-3-27b"
    params = model.config["params"]
    assert params["temperature"] == 0.1
    assert params["max_tokens"] == 128
    assert params["top_p"] == 0.9
    assert params["top_k"] == 40
    assert params["seed"] == 7
    assert params["stop"] == ["</end>"]
    assert params["mirostat"] == 2


def test_lmstudio_resolver_appends_v1() -> None:
    cfg = Configuration(
        backend="lmstudio",
        host="127.0.0.1:1234",
        model="qwen",
        temperature=0.2,
    )
    model = resolve_model(cfg)
    assert model.__class__.__name__ == "OpenAIModel"
    assert model.client_args["base_url"] == "http://127.0.0.1:1234/v1"
    assert model.client_args["api_key"] == "lm-studio"
    assert model.config["model_id"] == "qwen"
    assert model.config["params"]["temperature"] == 0.2


def test_lmstudio_resolver_preserves_v1_suffix() -> None:
    cfg = Configuration(
        backend="lmstudio",
        host="http://10.0.0.5:1234/v1",
        model="qwen",
    )
    model = resolve_model(cfg)
    assert model.client_args["base_url"] == "http://10.0.0.5:1234/v1"


def test_ollama_resolver_uses_flat_kwargs() -> None:
    pytest.importorskip("ollama")
    cfg = Configuration(
        backend="ollama",
        host="127.0.0.1:11434",
        model="llama3",
        temperature=0.3,
        max_tokens=512,
        top_p=0.8,
        stop=["STOP"],
    )
    model = resolve_model(cfg)
    assert model.__class__.__name__ == "OllamaModel"
    assert model.host == "http://127.0.0.1:11434"
    cfg_dict = dict(model.config)
    assert cfg_dict["model_id"] == "llama3"
    assert cfg_dict["temperature"] == 0.3
    assert cfg_dict["max_tokens"] == 512
    assert cfg_dict["top_p"] == 0.8
    assert cfg_dict["stop_sequences"] == ["STOP"]


def test_openai_resolver_threads_api_key() -> None:
    cfg = Configuration(
        backend="openai",
        model="gpt-4o",
        api_key="sk-test",
        temperature=0.0,
    )
    model = resolve_model(cfg)
    assert model.__class__.__name__ == "OpenAIModel"
    assert model.client_args["api_key"] == "sk-test"
    assert model.config["model_id"] == "gpt-4o"


def test_http_url_passes_through_verbatim() -> None:
    cfg = Configuration(
        backend="llamacpp",
        host="https://secure.example.com:9443",
        model="m",
    )
    model = resolve_model(cfg)
    assert model.base_url == "https://secure.example.com:9443"


def test_unknown_backend_is_prevented_by_configuration() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Configuration(backend="cohere", model="command-r")  # type: ignore[arg-type]

# --- from test_schema_deprecation.py ---
def test_coding_types_deprecated_shim() -> None:
    import operad.agents.coding.types as old_mod
    import operad.agents.coding.schemas as new_mod

    # Force re-execution of the shim so the warning is observable.
    with pytest.warns(DeprecationWarning, match="coding.types"):
        importlib.reload(old_mod)

    for name in ("DiffChunk", "PRDiff", "PRSummary", "ReviewComment", "ReviewReport"):
        assert getattr(old_mod, name) is getattr(new_mod, name)


def test_memory_shapes_deprecated_shim() -> None:
    import operad.agents.memory.shapes as old_mod
    import operad.agents.memory.schemas as new_mod

    with pytest.warns(DeprecationWarning, match="memory.shapes"):
        importlib.reload(old_mod)

    for name in ("Belief", "Beliefs", "Conversation", "Summary", "Turn", "UserModel"):
        assert getattr(old_mod, name) is getattr(new_mod, name)
