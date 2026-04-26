"""Offline tests for `operad.optim.PromptTraceback`.

Covers `PromptTraceback` construction (explicit gradients and `from_run`),
frame ordering (reverse-call order), plain-text stanza rendering, Markdown
rendering, NDJSON persistence, payload redaction and truncation, and the
`TracebackOnFailure` callback (tape-absent no-op and tape-present save).
"""

from __future__ import annotations

import json
import logging
import types
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from operad.agents.core.pipelines import Sequential
from operad.optim import (
    PromptTraceback,
    Tape,
    TextualGradient,
    tape,
    traceback,
)
from operad.runtime.observers import registry as obs_registry
from operad.train.callbacks_traceback import TracebackOnFailure

from tests._helpers.fake_leaf import A, B, C, D, FakeLeaf


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_registry():
    obs_registry.clear()
    yield
    obs_registry.clear()


# ---------------------------------------------------------------------------
# Sequential builders
# ---------------------------------------------------------------------------


async def _build_3stage(cfg: Any) -> Sequential[A, D]:
    leaf1 = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    leaf2 = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "ok"})
    leaf3 = FakeLeaf(config=cfg, input=C, output=D, canned={"payload": ["x"]})
    return await Sequential(leaf1, leaf2, leaf3, input=A, output=D).abuild()


async def _record_3stage(cfg: Any) -> tuple[Sequential[A, D], Tape]:
    pipe = await _build_3stage(cfg)
    async with tape() as t:
        await pipe(A(text="start"))
    return pipe, t


# ---------------------------------------------------------------------------
# Frame ordering
# ---------------------------------------------------------------------------


async def test_frames_are_in_reverse_call_order(cfg) -> None:
    pipe, t = await _record_3stage(cfg)
    tb = PromptTraceback(t)

    paths = [f.agent_path for f in tb.frames()]
    assert paths == [
        "Sequential.stage_2",
        "Sequential.stage_1",
        "Sequential.stage_0",
        "Sequential",
    ]


async def test_leaf_frames_flagged(cfg) -> None:
    pipe, t = await _record_3stage(cfg)
    tb = PromptTraceback(t)

    leaf_flags = {f.agent_path: f.is_leaf for f in tb.frames()}
    assert leaf_flags["Sequential"] is False
    assert leaf_flags["Sequential.stage_0"] is True
    assert leaf_flags["Sequential.stage_1"] is True
    assert leaf_flags["Sequential.stage_2"] is True


# ---------------------------------------------------------------------------
# Plain-text rendering
# ---------------------------------------------------------------------------


async def test_str_contains_stanza_per_node(cfg) -> None:
    pipe, t = await _record_3stage(cfg)
    grads = {
        "Sequential": TextualGradient(message="root critique", severity=1.0),
        "Sequential.stage_2": TextualGradient(
            message="answer is correct but too long", severity=0.4
        ),
    }
    tb = PromptTraceback(t, grads)
    rendered = str(tb)

    assert rendered.startswith("Traceback (most recent agent call last):")
    for path in [
        "Sequential",
        "Sequential.stage_0",
        "Sequential.stage_1",
        "Sequential.stage_2",
    ]:
        assert f'File "agent://{path}"' in rendered
    assert "answer is correct but too long" in rendered
    assert "root critique" in rendered
    assert "severity=0.40" in rendered


async def test_str_leaf_stanza_shows_input_output_and_gradient(cfg) -> None:
    pipe, t = await _record_3stage(cfg)
    grads = {
        "Sequential.stage_0": TextualGradient(message="stage-0 critique", severity=0.5),
    }
    tb = PromptTraceback(t, grads)
    rendered = str(tb)

    # The innermost leaf (Sequential.stage_0) should show its canned output
    # ({"value": 1}) and the gradient we seeded.
    assert '"value": 1' in rendered
    assert "stage-0 critique" in rendered


# ---------------------------------------------------------------------------
# from_run
# ---------------------------------------------------------------------------


async def test_from_run_matches_explicit_gradients_via_pipeline_split(cfg) -> None:
    pipe, t = await _record_3stage(cfg)
    loss = TextualGradient(message="final answer is bad", severity=0.9)

    from_run_tb = PromptTraceback.from_run(t, loss)

    # The pipeline split rule hands `loss` (same object) to the last stage
    # and a copy to the earlier stages and to the pipeline itself. Rebuild
    # the expected dict and compare frame-by-frame.
    expected = {
        "Sequential": loss,
        "Sequential.stage_0": loss.model_copy(),
        "Sequential.stage_1": loss.model_copy(),
        "Sequential.stage_2": loss,
    }
    explicit_tb = PromptTraceback(t, expected)

    for a, b in zip(from_run_tb.frames(), explicit_tb.frames()):
        assert a.agent_path == b.agent_path
        assert a.gradient is not None
        assert b.gradient is not None
        assert a.gradient.model_dump() == b.gradient.model_dump()


async def test_from_run_last_stage_gradient_is_loss_instance(cfg) -> None:
    pipe, t = await _record_3stage(cfg)
    loss = TextualGradient(message="oops", severity=1.0)
    tb = PromptTraceback.from_run(t, loss)

    # The pipeline split gives the *identical* loss object to the last
    # stage (no copy). This documents the structural-split reuse.
    grads = tb.gradients
    assert grads["Sequential.stage_2"] is loss
    assert grads["Sequential.stage_0"] is not loss
    assert grads["Sequential.stage_0"].model_dump() == loss.model_dump()


async def test_traceback_function_dispatches_to_from_run(cfg) -> None:
    pipe, t = await _record_3stage(cfg)
    loss = TextualGradient(message="bad", severity=1.0)

    tb = traceback(t, loss=loss)
    assert isinstance(tb, PromptTraceback)
    assert tb.gradients["Sequential.stage_2"] is loss


async def test_traceback_function_rejects_both_inputs(cfg) -> None:
    pipe, t = await _record_3stage(cfg)
    loss = TextualGradient(message="bad", severity=1.0)
    with pytest.raises(ValueError):
        traceback(t, loss=loss, gradients={"Sequential": loss})


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


async def test_to_markdown_uses_fenced_blocks_and_headings(cfg) -> None:
    pipe, t = await _record_3stage(cfg)
    grads = {
        "Sequential.stage_2": TextualGradient(message="too verbose", severity=0.6),
    }
    tb = PromptTraceback(t, grads)
    md = tb.to_markdown()

    assert md.startswith("# PromptTraceback")
    assert '### File "agent://Sequential.stage_2"' in md
    assert '### File "agent://Sequential"' in md
    assert "```text" in md
    assert "```" in md
    assert "too verbose" in md


# ---------------------------------------------------------------------------
# NDJSON persistence
# ---------------------------------------------------------------------------


async def test_save_produces_valid_ndjson(cfg, tmp_path: Path) -> None:
    pipe, t = await _record_3stage(cfg)
    grads = {
        "Sequential.stage_1": TextualGradient(message="mid critique", severity=0.3),
    }
    tb = PromptTraceback(t, grads)

    out = tmp_path / "sub" / "tb.ndjson"
    tb.save(out)

    assert out.exists()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(list(tb.frames())) == 4

    records = [json.loads(ln) for ln in lines]
    paths = [r["agent_path"] for r in records]
    assert paths == [
        "Sequential.stage_2",
        "Sequential.stage_1",
        "Sequential.stage_0",
        "Sequential",
    ]

    mid = next(r for r in records if r["agent_path"] == "Sequential.stage_1")
    assert mid["gradient"]["message"] == "mid critique"
    assert mid["gradient"]["severity"] == 0.3
    assert mid["is_leaf"] is True

    root = next(r for r in records if r["agent_path"] == "Sequential")
    assert root["gradient"] is None
    assert root["is_leaf"] is False


# ---------------------------------------------------------------------------
# Redaction & truncation
# ---------------------------------------------------------------------------


async def test_redact_callable_scrubs_payloads(cfg) -> None:
    # Use a unique sentinel that cannot collide with OperadOutput envelope
    # field names (e.g. "started_at", "agent_path").
    sentinel = "SECRET-USER-INPUT-XYZ"
    pipe = await _build_3stage(cfg)
    async with tape() as t:
        await pipe(A(text=sentinel))

    def _redact(m: BaseModel) -> BaseModel:
        if isinstance(m, A):
            return A(text="<redacted>")
        return m

    tb = PromptTraceback(t, redact=_redact)
    rendered = str(tb)

    assert sentinel not in rendered
    assert "<redacted>" in rendered
    _ = pipe


async def test_long_values_are_truncated_with_marker(cfg) -> None:
    pipe, t = await _record_3stage(cfg)
    huge = "x" * 5000
    grads = {
        "Sequential.stage_2": TextualGradient(message=huge, severity=1.0),
    }
    tb = PromptTraceback(t, grads, max_value_chars=200)
    rendered = str(tb)

    assert "[truncated" in rendered
    # The raw 5000-char message should never appear in full.
    assert huge not in rendered


# ---------------------------------------------------------------------------
# TracebackOnFailure callback
# ---------------------------------------------------------------------------


async def test_callback_noops_when_trainer_lacks_tape(
    cfg, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cb = TracebackOnFailure(loss_threshold=0.5, save_dir=tmp_path)
    fake_trainer = types.SimpleNamespace()  # no _last_tape, no _last_loss_grad

    with caplog.at_level(logging.DEBUG, logger="operad.train"):
        await cb.on_batch_end(fake_trainer, batch=None, step=3, loss=1.0)

    # Never raised; no NDJSON file written.
    assert not any(tmp_path.glob("*.ndjson"))
    assert any("does not expose" in r.getMessage() for r in caplog.records)


async def test_callback_saves_ndjson_when_tape_present(
    cfg, tmp_path: Path
) -> None:
    pipe, t = await _record_3stage(cfg)
    loss = TextualGradient(message="final answer is bad", severity=0.9)
    fake_trainer = types.SimpleNamespace(_last_tape=t, _last_loss_grad=loss)

    cb = TracebackOnFailure(loss_threshold=0.5, save_dir=tmp_path)
    await cb.on_batch_end(fake_trainer, batch=None, step=7, loss=1.2)

    files = sorted(tmp_path.glob("*.ndjson"))
    assert len(files) == 1
    assert files[0].name == "step-00007.ndjson"
    lines = files[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4  # one per tape entry
    # Gradient for the last stage must be the seeded loss.
    records = [json.loads(ln) for ln in lines]
    last = next(r for r in records if r["agent_path"] == "Sequential.stage_2")
    assert last["gradient"]["message"] == "final answer is bad"


async def test_callback_below_threshold_is_silent(
    cfg, tmp_path: Path
) -> None:
    pipe, t = await _record_3stage(cfg)
    loss = TextualGradient(message="irrelevant", severity=1.0)
    fake_trainer = types.SimpleNamespace(_last_tape=t, _last_loss_grad=loss)

    cb = TracebackOnFailure(loss_threshold=1.0, save_dir=tmp_path)
    await cb.on_batch_end(fake_trainer, batch=None, step=1, loss=0.5)

    assert not any(tmp_path.glob("*.ndjson"))
