"""Tests for `Agent.freeze` / `Agent.thaw`."""

from __future__ import annotations

import json
import pickle

import pytest

from operad import Agent, BuildError, Configuration
from operad.agents.pipelines import Sequential

from ..conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_freeze_thaw_roundtrip_skips_tracing(
    cfg: Configuration, tmp_path, monkeypatch
) -> None:
    p = await Sequential(
        FakeLeaf(config=cfg, input=A, output=B, canned={"value": 7}),
        FakeLeaf(config=cfg, input=B, output=C, canned={"label": "ok"}),
        input=A,
        output=C,
    ).abuild()

    path = tmp_path / "agent.json"
    p.freeze(str(path))

    # The tracer must not run during thaw — monkeypatch it to fail loudly.
    import operad.core.build as build_mod

    async def _should_not_trace(*_a, **_k):
        raise AssertionError("thaw should not invoke the symbolic tracer")

    monkeypatch.setattr(build_mod, "_trace", _should_not_trace)

    restored = Sequential.thaw(str(path))
    assert isinstance(restored, Sequential)
    assert restored._built
    out = await restored(A(text="hi"))
    assert out.response.label == "ok"


async def test_freeze_redacts_api_key(cfg: Configuration, tmp_path) -> None:
    secret_cfg = cfg.model_copy(update={"api_key": "secret-123"})
    leaf = FakeLeaf(config=secret_cfg, input=A, output=B)
    await leaf.abuild()
    path = tmp_path / "leaf.json"
    leaf.freeze(str(path))
    raw = path.read_text(encoding="utf-8")
    assert "secret-123" not in raw
    # Live agent's key is untouched.
    assert leaf.config is not None and leaf.config.api_key == "secret-123"


async def test_thaw_rejects_version_mismatch(
    cfg: Configuration, tmp_path
) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()
    path = tmp_path / "leaf.json"
    leaf.freeze(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["operad_version_hash"] = "deadbeef"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(BuildError) as exc:
        FakeLeaf.thaw(str(path))
    assert exc.value.reason == "not_built"
    assert "version" in str(exc.value)


async def test_freeze_rejects_unbuilt(cfg: Configuration, tmp_path) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)  # no .abuild()
    with pytest.raises(BuildError) as exc:
        leaf.freeze(str(tmp_path / "x.json"))
    assert exc.value.reason == "not_built"


async def test_freeze_rejects_non_pickleable_routing(
    cfg: Configuration, tmp_path
) -> None:
    p = await Sequential(
        FakeLeaf(config=cfg, input=A, output=B),
        FakeLeaf(config=cfg, input=B, output=C),
        input=A,
        output=C,
    ).abuild()
    # Attach a non-pickleable closure to the composite. It is not a
    # child Agent and not a known-standard attr, so freeze will try to
    # pickle it and fail.
    p._custom_hook = lambda: 42  # type: ignore[attr-defined]
    with pytest.raises((pickle.PicklingError, BuildError, AttributeError)):
        p.freeze(str(tmp_path / "nope.json"))


async def test_thaw_classmethod_checks_type(
    cfg: Configuration, tmp_path
) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()
    path = tmp_path / "leaf.json"
    leaf.freeze(str(path))
    # Thawing as Sequential when the frozen root is a FakeLeaf must raise.
    with pytest.raises(BuildError) as exc:
        Sequential.thaw(str(path))
    assert exc.value.reason == "not_built"


async def test_freeze_thaw_two_backend_variants(tmp_path) -> None:
    """freeze/thaw round-trips for two backend variants (llamacpp + openai)."""
    llamacpp_cfg = Configuration(backend="llamacpp", host="127.0.0.1:0", model="gemma")
    openai_cfg = Configuration(backend="openai", model="gpt-4o", api_key="sk-test")

    for cfg, label in [(llamacpp_cfg, "llamacpp"), (openai_cfg, "openai")]:
        leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}).abuild()
        path = tmp_path / f"{label}.json"
        leaf.freeze(str(path))
        restored = FakeLeaf.thaw(str(path))
        assert restored._built
        assert restored.config.backend == label
        out = await restored(A(text="hi"))
        assert out.response.value == 1


async def test_freeze_thaw_preserves_custom_name(cfg: Configuration, tmp_path) -> None:
    leaf = FakeLeaf(
        config=cfg,
        input=A,
        output=B,
        canned={"value": 7},
    )
    leaf.name = "named_leaf"
    leaf = await leaf.abuild()
    path = tmp_path / "named.json"
    leaf.freeze(str(path))

    restored = FakeLeaf.thaw(str(path))
    assert restored.name == "named_leaf"

    out = await restored(A(text="hi"))
    assert out.response.value == 7
    assert out.agent_path == "named_leaf"
