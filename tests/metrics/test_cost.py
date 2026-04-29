"""Tests for `cost_estimate`: fallback heuristic + custom pricing/tokenizer."""

from __future__ import annotations
import pytest
from operad import OperadOutput, Trace
from operad.runtime.trace import TraceObserver, TraceStep
from operad.metrics.cost import CostObserver, CostTracker, Pricing, cost_estimate
from operad.runtime.observers import base as _obs
from tests.conftest import A, B, FakeLeaf


# --- from test_cost.py ---
def _trace_with_tokens(*, prompt: int, completion: int) -> Trace:
    env = OperadOutput[B].model_construct(
        response=B(value=1),
        run_id="r",
        agent_path="X",
        prompt_tokens=prompt,
        completion_tokens=completion,
    )
    return Trace(
        run_id="r",
        steps=[TraceStep(agent_path="X", output=env)],
        root_output={"value": 1},
    )


def test_cost_estimate_sums_tokens_and_defaults_cost_zero() -> None:
    t = _trace_with_tokens(prompt=100, completion=50)
    report = cost_estimate(t)
    assert report.prompt_tokens == 100
    assert report.completion_tokens == 50
    assert report.cost_usd == 0.0  # unknown backend:model → free


def test_cost_estimate_uses_envelope_backend_and_model() -> None:
    env = OperadOutput[B].model_construct(
        response=B(value=1),
        run_id="r",
        agent_path="X",
        backend="openai",
        model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    t = Trace(
        run_id="r",
        steps=[TraceStep(agent_path="X", output=env)],
        root_output={"value": 1},
    )
    report = cost_estimate(t)
    # openai:gpt-4o-mini → 0.00015/1k prompt + 0.0006/1k completion
    expected = (1000 * 0.00015 + 500 * 0.0006) / 1000.0
    assert report.cost_usd == pytest.approx(expected)


def test_cost_estimate_honours_custom_pricing() -> None:
    t = _trace_with_tokens(prompt=1000, completion=500)
    pricing = {"unknown:unknown": Pricing(prompt_per_1k=0.01, completion_per_1k=0.02)}
    report = cost_estimate(t, pricing=pricing)
    assert report.cost_usd == pytest.approx(0.01 + 0.01)


def test_cost_estimate_falls_back_when_tokens_absent() -> None:
    env = OperadOutput[B].model_construct(response=B(value=1), run_id="r", agent_path="X")
    t = Trace(run_id="r", steps=[TraceStep(agent_path="X", output=env)])
    report = cost_estimate(t, tokenizer=lambda s: 42)
    # No prompt text is retained, so tokenizer is invoked with "" → 42.
    assert report.prompt_tokens == 42


@pytest.mark.asyncio
async def test_cost_estimate_on_real_trace(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}).abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)
    try:
        await leaf(A(text="x"))
    finally:
        _obs.registry.clear()
    t = obs.last()
    assert t is not None
    report = cost_estimate(t)
    assert report.run_id == t.run_id
    assert len(report.per_step) == len(t.steps)

async def test_cost_tracker_accumulates_per_run() -> None:
    tracker = CostTracker()
    tracker.add(
        run_id="r1",
        backend="anthropic",
        model="claude-haiku-4-5",
        prompt_tokens=100,
        completion_tokens=50,
    )
    tracker.add(
        run_id="r1",
        backend="anthropic",
        model="claude-haiku-4-5",
        prompt_tokens=10,
        completion_tokens=10,
    )
    tracker.add(
        run_id="r2",
        backend="llamacpp",
        model="default",
        prompt_tokens=100,
        completion_tokens=0,
    )

    totals = tracker.totals()
    assert set(totals.keys()) == {"r1", "r2"}
    assert totals["r1"]["prompt_tokens"] == 110
    assert totals["r1"]["completion_tokens"] == 60
    # claude-haiku: 0.001/1k prompt + 0.005/1k completion
    expected = (110 * 0.001 + 60 * 0.005) / 1000.0
    assert abs(totals["r1"]["cost_usd"] - expected) < 1e-12
    assert totals["r2"]["cost_usd"] == 0.0


async def test_cost_tracker_unknown_model_is_free() -> None:
    tracker = CostTracker()
    tracker.add(
        run_id="x",
        backend="nobody",
        model="whoknows",
        prompt_tokens=2,
        completion_tokens=0,
    )
    assert tracker.totals()["x"]["cost_usd"] == 0.0


async def test_cost_tracker_prices_gemini_25_flash() -> None:
    tracker = CostTracker()
    tracker.add(
        run_id="gemini-run",
        backend="gemini",
        model="gemini-2.5-flash",
        prompt_tokens=1000,
        completion_tokens=1000,
    )
    expected = (1000 * 0.0003 + 1000 * 0.0025) / 1000.0
    assert tracker.totals()["gemini-run"]["cost_usd"] == pytest.approx(expected)


async def test_cost_tracker_empty_before_events() -> None:
    assert CostTracker().totals() == {}


# --- CostObserver: live AgentEvent wiring (brief 4-3) ---
def _end_event(
    *,
    run_id: str = "run-1",
    backend: str = "openai",
    model: str = "gpt-4o-mini",
    prompt_tokens: int = 1000,
    completion_tokens: int = 500,
) -> _obs.AgentEvent:
    env = OperadOutput[B].model_construct(
        response=B(value=1),
        run_id=run_id,
        agent_path="X",
        backend=backend,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    return _obs.AgentEvent(
        run_id=run_id,
        agent_path="X",
        kind="end",
        input=None,
        output=env,
        error=None,
        started_at=0.0,
        finished_at=1.0,
    )


async def test_cost_observer_accumulates_on_end_event() -> None:
    observer = CostObserver()
    await observer.on_event(_end_event(prompt_tokens=1000, completion_tokens=500))
    totals = observer.totals()
    expected = (1000 * 0.00015 + 500 * 0.0006) / 1000.0
    assert totals["run-1"]["prompt_tokens"] == 1000
    assert totals["run-1"]["completion_tokens"] == 500
    assert totals["run-1"]["cost_usd"] == pytest.approx(expected)


@pytest.mark.parametrize("kind", ["start", "chunk", "error"])
async def test_cost_observer_ignores_non_end_events(kind: str) -> None:
    observer = CostObserver()
    event = _end_event()
    event.kind = kind  # type: ignore[assignment]
    await observer.on_event(event)
    assert observer.totals() == {}


async def test_cost_observer_unknown_backend_model_zero_cost() -> None:
    observer = CostObserver()
    await observer.on_event(
        _end_event(backend="nonexistent", model="ghost", prompt_tokens=100, completion_tokens=50)
    )
    totals = observer.totals()
    assert totals["run-1"]["prompt_tokens"] == 100
    assert totals["run-1"]["completion_tokens"] == 50
    assert totals["run-1"]["cost_usd"] == 0.0


async def test_cost_observer_integrates_with_registry() -> None:
    observer = CostObserver()
    _obs.registry.register(observer)
    try:
        await _obs.registry.notify(_end_event(prompt_tokens=2000, completion_tokens=1000))
    finally:
        _obs.registry.unregister(observer)
    totals = observer.totals()
    assert totals["run-1"]["prompt_tokens"] == 2000
    assert totals["run-1"]["completion_tokens"] == 1000
    expected = (2000 * 0.00015 + 1000 * 0.0006) / 1000.0
    assert totals["run-1"]["cost_usd"] == pytest.approx(expected)
