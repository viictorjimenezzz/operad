"""Offline tests for `operad.train.Trainer`.

Every test uses `FakeLeaf`, a stubbed `Optimizer`, a stubbed `Loss`,
and a monkeypatched `backward` when grads are needed. No real LLM
call ever fires.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from operad.benchmark.dataset import Dataset
from operad.benchmark.entry import Entry
from operad.benchmark.evaluate import EvalReport
from operad.core.freeze import thaw_agent
from operad.data.loader import DataLoader
from operad.metrics.base import MetricBase
from operad.optim.optimizers.optimizer import Optimizer, ParamGroup
from operad.optim.parameter import Parameter, TextualGradient
from operad.runtime.events import AlgorithmEvent, get_current_epoch
from operad.runtime.observers import registry as obs_registry
from operad.train import (
    BestCheckpoint,
    Callback,
    EarlyStopping,
    EpochReport,
    GradClip,
    Trainer,
    TrainingReport,
)
from tests._helpers.fake_leaf import A, B, FakeLeaf


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    obs_registry.clear()
    yield
    obs_registry.clear()


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class StubLoss(MetricBase):
    """Loss that returns canned (score, grad) tuples, round-robin."""

    def __init__(
        self,
        scores: list[float] | None = None,
        severities: list[float] | None = None,
        *,
        name: str = "stub_loss",
    ) -> None:
        self.name = name
        self._scores = list(scores or [0.5])
        self._severities = list(severities or [0.0])
        self._i = 0
        self.calls: list[tuple[BaseModel, BaseModel | None]] = []

    def _next(self) -> tuple[float, float]:
        s = self._scores[self._i % len(self._scores)]
        sev = self._severities[self._i % len(self._severities)]
        self._i += 1
        return s, sev

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        s, _ = self._next()
        return s

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]:
        self.calls.append((predicted, expected))
        s, sev = self._next()
        if sev <= 0:
            return s, TextualGradient.null_gradient()
        return s, TextualGradient(message=f"score={s}", severity=sev)


class StubOptimizer(Optimizer):
    """Records `step` calls; optionally mutates `agent.role` each step."""

    def __init__(
        self,
        params: Any,
        *,
        mutate_agent: Any = None,
        lr: float = 1.0,
    ) -> None:
        super().__init__(params, defaults={"lr": lr})
        self.step_calls: int = 0
        self._mutate_agent = mutate_agent

    async def step(self) -> None:
        self.step_calls += 1
        if self._mutate_agent is not None:
            self._mutate_agent.role = f"role-{self.step_calls}"

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        return None


async def _stub_backward_severity_one(
    _t: Any,
    _loss: TextualGradient,
    *,
    parameters: Any = None,
    **_: Any,
) -> None:
    """Stub `backward` that writes severity=1.0 grad onto each param."""
    if parameters is None:
        return
    for p in parameters:
        p.grad = TextualGradient(message="bad", severity=1.0)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


async def _built_leaf(cfg: Any, role: str = "initial") -> FakeLeaf:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 0})
    leaf.role = role
    leaf.mark_trainable(role=True)
    await leaf.abuild()
    return leaf


def _dataset(n: int = 3) -> Dataset[A, B]:
    entries = [
        Entry(input=A(text=f"x{i}"), expected_output=B(value=i))
        for i in range(n)
    ]
    return Dataset(entries, name="stub", version="v1")


def _loader(ds: Dataset[A, B], *, batch_size: int = 1) -> DataLoader[A, B]:
    return DataLoader(ds, batch_size=batch_size)


# ---------------------------------------------------------------------------
# Loop structure
# ---------------------------------------------------------------------------


async def test_fit_runs_declared_number_of_epochs(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss()
    opt = StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, loss)

    report = await trainer.fit(_loader(_dataset()), epochs=3)

    assert isinstance(report, TrainingReport)
    assert len(report.epochs) == 3
    assert all(isinstance(r, EpochReport) for r in report.epochs)


class _RecordingCallback(Callback):
    def __init__(self) -> None:
        self.events: list[str] = []

    async def on_fit_start(self, trainer: Any) -> None:
        self.events.append("fit_start")

    async def on_epoch_start(self, trainer: Any, epoch: int) -> None:
        self.events.append(f"epoch_start:{epoch}")

    async def on_batch_start(
        self, trainer: Any, batch: Any, step: int
    ) -> None:
        self.events.append(f"batch_start:{step}")

    async def on_batch_end(
        self, trainer: Any, batch: Any, step: int, loss: float
    ) -> None:
        self.events.append(f"batch_end:{step}")

    async def on_epoch_end(self, trainer: Any, report: EpochReport) -> None:
        self.events.append(f"epoch_end:{report.epoch}")

    async def on_validation_end(self, trainer: Any, report: Any) -> None:
        self.events.append("validation_end")

    async def on_fit_end(self, trainer: Any, report: TrainingReport) -> None:
        self.events.append("fit_end")


async def test_callback_ordering_and_lifecycle(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss()
    opt = StubOptimizer(list(leaf.parameters()))
    cb1 = _RecordingCallback()
    cb2 = _RecordingCallback()
    trainer = Trainer(leaf, opt, loss, callbacks=[cb1, cb2])

    await trainer.fit(_loader(_dataset(n=2)), epochs=1)

    # Both callbacks see the same event prefixes.
    assert cb1.events[0] == "fit_start"
    assert cb2.events[0] == "fit_start"
    assert cb1.events[-1] == "fit_end"
    # Insertion order: cb1's fit_start fires before cb2's fit_start.
    # (Check via trainer's internal list ordering indirectly: both have
    # parallel event streams, which is the contract we promise.)
    assert cb1.events == cb2.events


async def test_training_report_tracks_hash_content(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss()
    opt = StubOptimizer(list(leaf.parameters()), mutate_agent=leaf)
    trainer = Trainer(leaf, opt, loss)
    seed = leaf.hash_content

    report = await trainer.fit(_loader(_dataset()), epochs=3)

    hashes = [r.hash_content for r in report.epochs]
    assert report.seed_hash_content == seed
    assert len({*hashes}) > 1  # mutated across epochs
    # Each epoch_end hash equals agent.hash_content after that epoch.
    assert hashes[-1] == leaf.hash_content


class _EpochEventCollector:
    def __init__(self) -> None:
        self.batch_starts: list[int | None] = []

    async def on_event(self, event: object) -> None:
        if isinstance(event, AlgorithmEvent) and event.kind == "batch_start":
            self.batch_starts.append(event.payload.get("epoch"))


class _AlgoEventCollector:
    def __init__(self) -> None:
        self.events: list[AlgorithmEvent] = []

    async def on_event(self, event: object) -> None:
        if isinstance(event, AlgorithmEvent):
            self.events.append(event)


async def test_fit_propagates_epoch_via_context_var(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss()
    opt = StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, loss)

    col = _EpochEventCollector()
    obs_registry.register(col)
    try:
        await trainer.fit(_loader(_dataset(n=2)), epochs=2)
    finally:
        obs_registry.unregister(col)

    assert set(col.batch_starts) == {0, 1}
    # After fit, the ContextVar resets to None.
    assert get_current_epoch() is None


async def test_fit_emits_batch_gradient_and_checkpoint_payloads(
    cfg: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss(severities=[1.0])
    opt = StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, loss)
    monkeypatch.setattr("operad.train.trainer.backward", _stub_backward_severity_one)

    col = _AlgoEventCollector()
    obs_registry.register(col)
    try:
        await trainer.fit(_loader(_dataset(n=1)), epochs=1)
    finally:
        obs_registry.unregister(col)

    batch_events = [
        e
        for e in col.events
        if e.algorithm_path == "Trainer" and e.kind == "batch_end"
    ]
    assert batch_events
    assert isinstance(batch_events[0].payload["train_loss"], float)
    assert "lr" in batch_events[0].payload

    grad_events = [
        e
        for e in col.events
        if e.algorithm_path == "Trainer" and e.kind == "gradient_applied"
    ]
    assert grad_events
    assert isinstance(grad_events[0].payload["message"], str)
    assert isinstance(grad_events[0].payload["severity"], float)
    assert isinstance(grad_events[0].payload["target_paths"], list)
    assert isinstance(grad_events[0].payload["by_field"], dict)
    assert "applied_diff" in grad_events[0].payload

    epoch_end = [
        e
        for e in col.events
        if e.algorithm_path == "Trainer"
        and e.kind == "iteration"
        and e.payload.get("phase") == "epoch_end"
    ]
    assert epoch_end
    assert "lr" in epoch_end[0].payload
    assert isinstance(epoch_end[0].payload["parameter_snapshot"], dict)


async def test_validation_runs_when_val_ds_supplied(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss(scores=[0.7])
    opt = StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, loss)

    val = _dataset(n=2)
    report = await trainer.fit(_loader(_dataset()), val_ds=val, epochs=2)

    assert all(r.val_loss is not None for r in report.epochs)
    assert all("stub_loss" in r.val_metrics for r in report.epochs)


# ---------------------------------------------------------------------------
# Early stopping
# ---------------------------------------------------------------------------


async def test_early_stopping_halts_after_patience(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    # Constant val_loss → no improvement ever.
    loss = StubLoss(scores=[0.5])
    opt = StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, loss)

    es = EarlyStopping(monitor="stub_loss", mode="min", patience=1, min_delta=1e-4)
    report = await trainer.fit(
        _loader(_dataset(n=1)),
        val_ds=_dataset(n=1),
        epochs=10,
        early_stopping=es,
    )

    # patience=1 + the initial "first" epoch that sets the best → halts early.
    assert len(report.epochs) < 10


# ---------------------------------------------------------------------------
# Best checkpoint
# ---------------------------------------------------------------------------


async def test_best_checkpoint_writes_on_improvement(
    cfg: Any, tmp_path: Path
) -> None:
    leaf = await _built_leaf(cfg)
    # Decreasing val_loss → every epoch is an improvement.
    loss = StubLoss(scores=[0.9, 0.5, 0.1])
    opt = StubOptimizer(list(leaf.parameters()))
    ckpt_path = tmp_path / "best.json"
    trainer = Trainer(
        leaf,
        opt,
        loss,
        callbacks=[BestCheckpoint(ckpt_path, monitor="stub_loss", mode="min")],
    )

    await trainer.fit(
        _loader(_dataset(n=1)), val_ds=_dataset(n=1), epochs=3
    )

    assert ckpt_path.exists()
    thawed = thaw_agent(ckpt_path)
    assert thawed.role == leaf.role


# ---------------------------------------------------------------------------
# GradClip + backward stub
# ---------------------------------------------------------------------------


async def test_gradclip_clips_severity(
    cfg: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss(severities=[1.0])  # always non-null grad
    opt = StubOptimizer(list(leaf.parameters()))

    monkeypatch.setattr(
        "operad.train.trainer.backward", _stub_backward_severity_one
    )

    captured: list[float] = []

    class _CaptureSeverity(Callback):
        async def on_batch_end(
            self, trainer: Any, batch: Any, step: int, loss: float
        ) -> None:
            for g in trainer.optimizer.param_groups:
                for p in g.params:
                    if p.grad is not None:
                        captured.append(p.grad.severity)

    trainer = Trainer(
        leaf,
        opt,
        loss,
        callbacks=[GradClip(max_severity=0.2), _CaptureSeverity()],
    )

    await trainer.fit(_loader(_dataset(n=1)), epochs=1)

    assert captured
    assert max(captured) <= 0.2 + 1e-9


# ---------------------------------------------------------------------------
# Accumulation
# ---------------------------------------------------------------------------


async def test_accumulation_steps_triggers_step_every_n(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss()
    opt = StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, loss, accumulation_steps=4)

    # 8 samples, batch_size=1 → 8 batches → step fires at batches 4 and 8.
    await trainer.fit(_loader(_dataset(n=8), batch_size=1), epochs=1)

    assert opt.step_calls == 2


async def test_residual_grads_flush_step_at_epoch_end(
    cfg: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss(severities=[1.0])  # non-null grads
    opt = StubOptimizer(list(leaf.parameters()))
    monkeypatch.setattr(
        "operad.train.trainer.backward", _stub_backward_severity_one
    )
    # 3 batches + accumulation_steps=4 → no mid-epoch step; residual flush.
    trainer = Trainer(leaf, opt, loss, accumulation_steps=4)

    await trainer.fit(_loader(_dataset(n=3), batch_size=1), epochs=1)

    assert opt.step_calls == 1


async def test_accumulation_preserves_each_sample_once(
    cfg: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each per-sample message must appear exactly once in the merged grad.

    Regression for the bug where backward() overwrote p.grad (which held
    the prior-batch accumulated gradient) before the old pending-capture
    code could read it, silently dropping earlier samples.
    """
    leaf = await _built_leaf(cfg)
    loss = StubLoss(severities=[1.0])
    params = list(leaf.parameters())
    opt = StubOptimizer(params)

    call_count = 0

    async def _stub_backward_unique(
        _t: Any,
        _loss: TextualGradient,
        *,
        parameters: Any = None,
        **_: Any,
    ) -> None:
        nonlocal call_count
        for p in parameters or []:
            p.grad = TextualGradient(
                message=f"sample-{call_count}", severity=1.0
            )
        call_count += 1

    monkeypatch.setattr("operad.train.trainer.backward", _stub_backward_unique)

    captured_grads: list[TextualGradient] = []

    async def _capturing_step() -> None:
        opt.step_calls += 1
        for p in params:
            if p.grad is not None and p.grad.severity > 0:
                captured_grads.append(p.grad)

    opt.step = _capturing_step  # type: ignore[method-assign]

    # 3 batches of 1 sample each; step fires once after all 3.
    trainer = Trainer(leaf, opt, loss, accumulation_steps=3)
    await trainer.fit(_loader(_dataset(n=3), batch_size=1), epochs=1)

    assert opt.step_calls == 1
    assert len(captured_grads) > 0
    merged_message = captured_grads[0].message
    for i in range(3):
        assert f"sample-{i}" in merged_message, (
            f"sample-{i} missing from merged gradient message: {merged_message!r}"
        )
        assert merged_message.count(f"sample-{i}") == 1, (
            f"sample-{i} appears more than once: {merged_message!r}"
        )


# ---------------------------------------------------------------------------
# max_grad_norm auto-install
# ---------------------------------------------------------------------------


async def test_max_grad_norm_autoinstalls_gradclip(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss()
    opt = StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, loss, max_grad_norm=0.3)

    installed = [cb for cb in trainer._callbacks if isinstance(cb, GradClip)]
    assert len(installed) == 1
    assert installed[0].max_severity == 0.3


# ---------------------------------------------------------------------------
# predict / evaluate
# ---------------------------------------------------------------------------


async def test_predict_delegates_to_agent(cfg: Any) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 42})
    await leaf.abuild()
    trainer = Trainer(leaf, StubOptimizer([_role_param(leaf)]), StubLoss())

    out = await trainer.predict(A(text="hi"))
    assert out.response.value == 42


async def test_evaluate_returns_evalreport(cfg: Any) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    await leaf.abuild()
    trainer = Trainer(
        leaf,
        StubOptimizer([_role_param(leaf)]),
        StubLoss(scores=[0.7]),
    )

    report = await trainer.evaluate(_dataset(n=2))

    assert isinstance(report, EvalReport)
    assert "stub_loss" in report.summary


# ---------------------------------------------------------------------------
# batch_size > 1
# ---------------------------------------------------------------------------


async def test_batch_size_gt_one_processes_samples_sequentially(
    cfg: Any,
) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss()
    opt = StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, loss)

    await trainer.fit(_loader(_dataset(n=6), batch_size=3), epochs=1)

    # 6 samples → 6 loss.compute calls regardless of batch_size.
    assert len(loss.calls) == 6


# ---------------------------------------------------------------------------
# Guard rails
# ---------------------------------------------------------------------------


async def test_fit_raises_when_agent_not_built(cfg: Any) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)  # not built
    leaf.mark_trainable(role=True)
    loss = StubLoss()
    opt = StubOptimizer([_role_param(leaf)])
    trainer = Trainer(leaf, opt, loss)

    with pytest.raises(Exception):  # BuildError subclass
        await trainer.fit(_loader(_dataset()), epochs=1)


def test_invalid_accumulation_steps(cfg: Any) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.mark_trainable(role=True)
    with pytest.raises(ValueError):
        Trainer(leaf, StubOptimizer([_role_param(leaf)]), StubLoss(), accumulation_steps=0)


def test_invalid_max_grad_norm(cfg: Any) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.mark_trainable(role=True)
    with pytest.raises(ValueError):
        Trainer(leaf, StubOptimizer([_role_param(leaf)]), StubLoss(), max_grad_norm=0)


def _role_param(leaf: FakeLeaf) -> Parameter[Any]:
    from operad.optim.parameter import TextParameter

    leaf.role = leaf.role or "r"
    return TextParameter.from_agent(leaf, "role", "role")
