"""`Trainer` — the PyTorch-Lightning-style `fit / evaluate / predict` loop.

Composes `DataLoader`, `Loss`, `Optimizer`, optional `scheduler`, and a
list of `Callback`s. Each training sample opens its own `tape()`,
computes the loss, and calls `backward()`; per-sample gradients are
merged onto each `Parameter.grad` before `optimizer.step()` fires
(every ``accumulation_steps`` batches, with a residual flush at
epoch end).

Textual-gradient accumulation semantics: when ``N`` samples touch the
same `Parameter`, their gradients are folded into one — messages
concatenated (``\\n---\\n``), ``target_paths`` unioned, ``by_field``
entries concatenated, ``severity`` taken as the maximum. This matches
the "pick one clear semantics and document" requirement in the stream
brief; `Momentum` optimizers fold the merged grad into their summary.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Generic

from ..benchmark.dataset import Dataset
from ..benchmark.evaluate import EvalReport, evaluate
from ..core.agent import Agent, In, Out
from ..core.freeze import freeze_agent, thaw_pair
from ..core.output import OPERAD_VERSION_HASH, PYTHON_VERSION_HASH, OperadOutput
from ..data.loader import Batch, DataLoader
from ..metrics.base import Metric
from ..optim.backward import backward
from ..optim.context import no_grad
from ..optim.loss import Loss
from ..optim.lr_scheduler import LRScheduler
from ..optim.optimizer import Optimizer
from ..optim.parameter import Parameter, TextualGradient
from ..optim.tape import tape
from ..runtime.events import set_current_epoch
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event
from ..utils.cassette import (
    TrainCassetteMiss,
    _compose_train_key,
    _hash_train_inputs,
    _hash_train_params,
    get_train_ctx,
    record_train_step,
)
from ..utils.errors import BuildError
from .callbacks import Callback, EarlyStopping, GradClip
from .report import EpochReport, TrainingReport


def _merge_grads(grads: list[TextualGradient]) -> TextualGradient:
    """Fold a list of `TextualGradient`s into one.

    - ``message`` values joined with ``\\n---\\n``.
    - ``target_paths`` de-duplicated preserving order.
    - ``by_field`` values concatenated per key with the same separator.
    - ``severity`` becomes the max over the inputs.
    """
    if not grads:
        return TextualGradient.null_gradient()
    if len(grads) == 1:
        return grads[0]
    messages = [g.message for g in grads if g.message]
    merged_message = "\n---\n".join(messages)
    paths: list[str] = []
    seen: set[str] = set()
    for g in grads:
        for p in g.target_paths:
            if p not in seen:
                seen.add(p)
                paths.append(p)
    by_field: dict[str, list[str]] = {}
    for g in grads:
        for k, v in g.by_field.items():
            by_field.setdefault(k, []).append(v)
    merged_by_field = {k: "\n---\n".join(v) for k, v in by_field.items()}
    severity = max(g.severity for g in grads)
    return TextualGradient(
        message=merged_message,
        by_field=merged_by_field,
        severity=severity,
        target_paths=paths,
    )


def _flatten_params(optimizer: Optimizer) -> list[Parameter[Any]]:
    """Flatten every parameter across every group into a list."""
    out: list[Parameter[Any]] = []
    for group in optimizer.param_groups:
        out.extend(group.params)
    return out


class Trainer(Generic[In, Out]):
    """Orchestrates fit / evaluate / predict over a built `Agent`.

    The trainer never auto-builds the agent (same rule as
    `benchmark.evaluate`). Callbacks are invoked in insertion order
    for every lifecycle hook; a callback can halt training by setting
    ``trainer._should_stop = True``.
    """

    def __init__(
        self,
        agent: Agent[In, Out],
        optimizer: Optimizer,
        loss_fn: Loss,
        *,
        scheduler: Any | None = None,
        callbacks: list[Callback] | None = None,
        metrics: list[Metric] | None = None,
        max_grad_norm: float | None = None,
        accumulation_steps: int = 1,
    ) -> None:
        if accumulation_steps < 1:
            raise ValueError("accumulation_steps must be >= 1")
        if max_grad_norm is not None and max_grad_norm <= 0:
            raise ValueError("max_grad_norm must be positive")
        self.agent = agent
        self.optimizer = optimizer
        self.loss_fn = loss_fn
        self.scheduler = scheduler
        self.metrics: list[Metric] = list(metrics or [])
        self.accumulation_steps = accumulation_steps
        self.max_grad_norm = max_grad_norm
        self._callbacks: list[Callback] = list(callbacks or [])
        if max_grad_norm is not None:
            self._callbacks.append(GradClip(max_severity=max_grad_norm))
        self._should_stop: bool = False
        self._last_batch_tape_entries: int = 0
        self._last_report: TrainingReport | None = None
        self.last_epoch_per_sample_severity: dict[int, float] = {}
        self.loader: DataLoader[In, Out] | None = None

        # Optional wave-4 optimizer hook: OPRO/APE need an evaluator closure.
        if getattr(optimizer, "needs_evaluator", False):
            optimizer.evaluator = self._quick_evaluator  # type: ignore[attr-defined]

    # --- public API -------------------------------------------------------

    async def fit(
        self,
        loader: DataLoader[In, Out],
        val_ds: Dataset[In, Out] | None = None,
        *,
        epochs: int,
        early_stopping: EarlyStopping | None = None,
    ) -> TrainingReport:
        """Run the training loop for ``epochs`` epochs.

        **Gradient accumulation contract** (``accumulation_steps > 1``):
        Per-sample gradients are collected in an internal accumulator across
        ``accumulation_steps`` consecutive batches. Immediately before
        ``optimizer.step()`` fires, the accumulated per-sample gradients are
        merged once into a single ``TextualGradient`` per parameter — each
        original sample's gradient message appears exactly once in the merged
        result, regardless of batch boundaries. ``severity`` is the maximum
        across all samples; ``target_paths`` are de-duplicated in arrival
        order.
        """
        if not self.agent._built:
            raise BuildError(
                "not_built",
                "call .build() before Trainer.fit()",
                agent=type(self.agent).__name__,
            )
        if epochs < 1:
            raise ValueError("epochs must be >= 1")

        cbs = list(self._callbacks)
        if early_stopping is not None:
            cbs.append(early_stopping)
        self._callbacks = cbs
        self._should_stop = False

        seed_hash = self.agent.hash_content
        epoch_reports: list[EpochReport] = []
        batch_counter = 0

        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path="Trainer",
                payload={
                    "epochs": int(epochs),
                    "seed_hash_content": seed_hash,
                    "batch_size": getattr(loader, "batch_size", None),
                },
            )
            training = await self._fit_loop(
                loader=loader,
                val_ds=val_ds,
                epochs=epochs,
                cbs=cbs,
                seed_hash=seed_hash,
                early_stopping=early_stopping,
                epoch_reports=epoch_reports,
                batch_counter=batch_counter,
            )
            await emit_algorithm_event(
                "algo_end",
                algorithm_path="Trainer",
                payload={
                    "epochs_completed": len(epoch_reports),
                    "final_hash_content": self.agent.hash_content,
                },
            )
        self._last_report = training
        return training

    async def _fit_loop(
        self,
        *,
        loader: DataLoader[In, Out],
        val_ds: Dataset[In, Out] | None,
        epochs: int,
        cbs: list[Callback],
        seed_hash: str,
        early_stopping: EarlyStopping | None,
        epoch_reports: list[EpochReport],
        batch_counter: int,
    ) -> TrainingReport:
        self.loader = loader
        for cb in cbs:
            await cb.on_fit_start(self)

        for epoch in range(epochs):
            await emit_algorithm_event(
                "iteration",
                algorithm_path="Trainer",
                payload={"phase": "epoch_start", "epoch": epoch},
            )
            for cb in cbs:
                await cb.on_epoch_start(self, epoch)

            set_current_epoch(epoch)
            self.last_epoch_per_sample_severity = {}
            try:
                sampler = getattr(loader, "_sampler", None)
                if sampler is not None and hasattr(sampler, "refresh"):
                    async with no_grad():
                        await sampler.refresh()

                t0 = time.monotonic()
                epoch_loss_sum = 0.0
                epoch_sample_count = 0
                step_idx = 0
                epoch_batch = 0
                window_inputs: list[Any] = []
                tc = get_train_ctx()
                all_params = _flatten_params(self.optimizer)

                async for batch in loader:
                    step = batch_counter
                    for cb in cbs:
                        await cb.on_batch_start(self, batch, step)

                    window_inputs.extend(batch.inputs)
                    batch_counter += 1
                    epoch_batch += 1
                    should_step = batch_counter % self.accumulation_steps == 0

                    if tc is not None and tc.mode == "replay" and should_step:
                        h_agent = self.agent.hash_content
                        h_inputs = _hash_train_inputs(window_inputs)
                        h_params = _hash_train_params(all_params)
                        key = _compose_train_key(epoch, step_idx, h_agent, h_inputs, h_params)
                        entry = tc.entries.get(key)
                        if entry is None:
                            raise TrainCassetteMiss(
                                key,
                                epoch=epoch,
                                step_idx=step_idx,
                                hash_agent=h_agent,
                                hash_inputs=h_inputs,
                                hash_params=h_params,
                                path=tc.path,
                            )
                        mean_loss = entry["mean_loss"]
                        n = entry["n_samples"]
                        epoch_loss_sum += mean_loss * n
                        epoch_sample_count += n
                        for path, val in entry["post_step_params"].items():
                            for p in all_params:
                                if p.path == path:
                                    p.write(val)
                                    break
                        lr_state_json = entry.get("lr_state_json")
                        if lr_state_json is not None and self.scheduler is not None:
                            self.scheduler.load_state_dict(json.loads(lr_state_json))
                        window_inputs.clear()
                        step_idx += 1
                        lrs = self._current_lrs()
                        await emit_algorithm_event(
                            "batch_end",
                            algorithm_path="Trainer",
                            payload={
                                "phase": "batch_end",
                                "epoch": epoch,
                                "batch": epoch_batch,
                                "step": step,
                                "train_loss": mean_loss,
                                "lr": lrs[0] if lrs else None,
                                "lr_groups": lrs,
                            },
                        )
                        for cb in cbs:
                            await cb.on_batch_end(self, batch, step, mean_loss)
                    else:
                        batch_loss, n = await self._run_batch(batch)
                        epoch_loss_sum += batch_loss * n
                        epoch_sample_count += n

                        for cb in cbs:
                            await cb.on_batch_end(self, batch, step, batch_loss)

                        lrs = self._current_lrs()
                        await emit_algorithm_event(
                            "batch_end",
                            algorithm_path="Trainer",
                            payload={
                                "phase": "batch_end",
                                "epoch": epoch,
                                "batch": epoch_batch,
                                "step": step,
                                "train_loss": batch_loss,
                                "lr": lrs[0] if lrs else None,
                                "lr_groups": lrs,
                            },
                        )

                        if should_step:
                            grad_payload = self._prepare_gradient_payload(
                                params=all_params, epoch=epoch, batch=epoch_batch
                            )
                            if tc is not None and tc.mode == "record":
                                h_agent = self.agent.hash_content
                                h_inputs = _hash_train_inputs(window_inputs)
                                h_params = _hash_train_params(all_params)
                                key = _compose_train_key(epoch, step_idx, h_agent, h_inputs, h_params)
                            await self.optimizer.step()
                            if grad_payload is not None:
                                payload = self._finalize_gradient_payload(
                                    grad_payload, params=all_params
                                )
                                await emit_algorithm_event(
                                    "gradient_applied",
                                    algorithm_path="Trainer",
                                    payload=payload,
                                )
                            self.optimizer.zero_grad()
                            if tc is not None and tc.mode == "record":
                                post_params = {p.path: p.value for p in all_params}
                                lr_state = (
                                    self.scheduler.state_dict()
                                    if self.scheduler is not None
                                    else None
                                )
                                record_train_step(
                                    tc,
                                    key=key,
                                    hash_agent=h_agent,
                                    hash_inputs=h_inputs,
                                    hash_params=h_params,
                                    epoch=epoch,
                                    step_idx=step_idx,
                                    mean_loss=batch_loss,
                                    n_samples=n,
                                    post_step_params=post_params,
                                    lr_state=lr_state,
                                )
                            window_inputs.clear()
                            step_idx += 1

                # Residual flush: some accumulated grads may still be on params.
                if tc is None or tc.mode != "replay":
                    if self._has_pending_grad():
                        grad_payload = self._prepare_gradient_payload(
                            params=all_params, epoch=epoch, batch=epoch_batch
                        )
                        if tc is not None and tc.mode == "record":
                            h_agent = self.agent.hash_content
                            h_inputs = _hash_train_inputs(window_inputs)
                            h_params = _hash_train_params(all_params)
                            key = _compose_train_key(epoch, step_idx, h_agent, h_inputs, h_params)
                        await self.optimizer.step()
                        if grad_payload is not None:
                            payload = self._finalize_gradient_payload(
                                grad_payload, params=all_params
                            )
                            await emit_algorithm_event(
                                "gradient_applied",
                                algorithm_path="Trainer",
                                payload=payload,
                            )
                        self.optimizer.zero_grad()
                        if tc is not None and tc.mode == "record":
                            post_params = {p.path: p.value for p in all_params}
                            lr_state = (
                                self.scheduler.state_dict()
                                if self.scheduler is not None
                                else None
                            )
                            record_train_step(
                                tc,
                                key=key,
                                hash_agent=h_agent,
                                hash_inputs=h_inputs,
                                hash_params=h_params,
                                epoch=epoch,
                                step_idx=step_idx,
                                mean_loss=0.0,
                                n_samples=len(window_inputs),
                                post_step_params=post_params,
                                lr_state=lr_state,
                            )

                val_report: EvalReport | None = None
                if val_ds is not None:
                    val_report = await self.evaluate(val_ds)
                    for cb in cbs:
                        await cb.on_validation_end(self, val_report)
            finally:
                set_current_epoch(None)

            if self.scheduler is not None:
                self.scheduler.step()

            train_loss = (
                epoch_loss_sum / epoch_sample_count
                if epoch_sample_count > 0
                else 0.0
            )
            val_loss = (
                float(val_report.summary.get(self.loss_fn.name, float("nan")))
                if val_report is not None
                else None
            )
            val_metrics = dict(val_report.summary) if val_report is not None else {}

            report = EpochReport(
                epoch=epoch,
                train_loss=train_loss,
                train_metrics={},
                val_loss=val_loss,
                val_metrics=val_metrics,
                lr=[g.lr for g in self.optimizer.param_groups],
                duration_s=time.monotonic() - t0,
                hash_content=self.agent.hash_content,
            )
            epoch_reports.append(report)

            for cb in cbs:
                await cb.on_epoch_end(self, report)

            await emit_algorithm_event(
                "iteration",
                algorithm_path="Trainer",
                payload={
                    "phase": "epoch_end",
                    "epoch": epoch,
                    "train_loss": train_loss,
                    "val_loss": val_loss,
                    "lr": report.lr[0] if report.lr else None,
                    "lr_groups": list(report.lr),
                    "hash_content": report.hash_content,
                    "checkpoint_score": val_loss if val_loss is not None else train_loss,
                    "parameter_snapshot": self._snapshot_named_parameters(),
                },
            )

            if self._should_stop:
                break

        training = self._build_training_report(
            epoch_reports,
            seed_hash=seed_hash,
            es_monitor=early_stopping.monitor if early_stopping else None,
            es_mode=early_stopping.mode if early_stopping else None,
        )

        for cb in cbs:
            await cb.on_fit_end(self, training)

        return training

    def save(self, path: str | Path) -> None:
        """Persist agent + optimizer + scheduler + report to a single JSON file.

        Reuses `freeze_agent(optimizer=)` for the agent/optimizer bundle,
        then merges in the scheduler state, the last `TrainingReport`
        (if any), and a small metadata block (operad/python version
        hashes, UTC ISO timestamp). API keys are scrubbed by
        `freeze_agent`'s existing redaction path.
        """
        out = Path(path)
        freeze_agent(self.agent, out, optimizer=self.optimizer)
        data = json.loads(out.read_text(encoding="utf-8"))
        data["scheduler_state"] = (
            self.scheduler.state_dict()
            if isinstance(self.scheduler, LRScheduler)
            else None
        )
        data["report"] = (
            self._last_report.model_dump(mode="json")
            if self._last_report is not None
            else None
        )
        data["metadata"] = {
            "operad_version": OPERAD_VERSION_HASH,
            "python_version": PYTHON_VERSION_HASH,
            "saved_at_iso": datetime.now(timezone.utc).isoformat(),
        }
        out.write_text(
            json.dumps(data, sort_keys=True, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        loss_fn: Loss,
        optimizer_factory: Callable[[Agent[Any, Any]], Optimizer],
        agent: Agent[Any, Any] | None = None,
        scheduler_factory: Callable[[Optimizer], LRScheduler] | None = None,
        callbacks: list[Callback] | None = None,
    ) -> "Trainer[Any, Any]":
        """Restore a Trainer from a `save()` bundle.

        `loss_fn` and `optimizer_factory` are required: losses and
        optimizers typically hold references to rewriter / critic agents
        and closures, which cannot be safely round-tripped through JSON.
        When `agent` is provided, it is used verbatim (overlay mode) and
        the frozen agent bundle is discarded; otherwise the agent is
        thawed from `path`.
        """
        bundle_path = Path(path)
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
        loaded_agent, opt_state = thaw_pair(bundle_path)
        actual_agent = agent if agent is not None else loaded_agent

        optimizer = optimizer_factory(actual_agent)
        if opt_state is not None:
            optimizer.load_state_dict(opt_state)

        scheduler: LRScheduler | None = None
        if scheduler_factory is not None:
            scheduler = scheduler_factory(optimizer)
            sd = data.get("scheduler_state")
            if sd is not None:
                scheduler.load_state_dict(sd)

        trainer = cls(
            actual_agent,
            optimizer,
            loss_fn,
            scheduler=scheduler,
            callbacks=callbacks,
        )
        report_data = data.get("report")
        if report_data is not None:
            trainer._last_report = TrainingReport.model_validate(report_data)
        return trainer

    async def evaluate(self, ds: Dataset[In, Out]) -> EvalReport:
        metrics: list[Metric] = [self.loss_fn, *self.metrics]  # type: ignore[list-item]
        return await evaluate(self.agent, ds, metrics=metrics)

    async def predict(self, x: In) -> OperadOutput[Out]:
        return await self.agent(x)

    # --- internals --------------------------------------------------------

    async def _run_batch(self, batch: Batch[In, Out]) -> tuple[float, int]:
        """Process every sample in ``batch``; return (mean loss, count).

        Each sample gets its own tape + backward; per-sample grads are
        merged with any gradient already accumulated on ``p.grad`` from
        prior batches, so ``optimizer.step`` sees a single merged gradient
        per parameter that covers every sample across the accumulation window.
        """
        params = _flatten_params(self.optimizer)
        # Capture any gradient accumulated from previous batches before
        # backward() overwrites p.grad with the first sample's gradient.
        pre_batch: dict[int, TextualGradient | None] = {}
        for p in params:
            pre_batch[id(p)] = p.grad
            p.grad = None

        per_sample: dict[int, list[TextualGradient]] = {id(p): [] for p in params}
        loss_sum = 0.0
        sample_count = 0
        tape_entries_total = 0

        for idx, x, y in zip(batch.indices, batch.inputs, batch.expected):
            async with tape() as t:
                output = await self.agent(x)
            tape_entries_total += len(t.entries)
            score, grad = await self.loss_fn.compute(output.response, y)
            loss_sum += score
            sample_count += 1
            self.last_epoch_per_sample_severity[idx] = grad.severity
            if grad.severity <= 0:
                continue
            await backward(t, grad, parameters=params)
            for p in params:
                if p.grad is not None and p.grad.severity > 0:
                    per_sample[id(p)].append(p.grad)
                    p.grad = None

        self._last_batch_tape_entries = tape_entries_total

        for p in params:
            grads = per_sample[id(p)]
            if not grads:
                continue
            prev = pre_batch[id(p)]
            pending = [prev] if prev is not None and prev.severity > 0 else []
            p.grad = _merge_grads(grads + pending)

        mean_loss = loss_sum / sample_count if sample_count > 0 else 0.0
        return mean_loss, sample_count

    def _has_pending_grad(self) -> bool:
        for group in self.optimizer.param_groups:
            for p in group.params:
                if p.grad is not None and p.grad.severity > 0:
                    return True
        return False

    def _current_lrs(self) -> list[float]:
        return [float(g.lr) for g in self.optimizer.param_groups]

    def _snapshot_named_parameters(self) -> dict[str, str]:
        named = getattr(self.agent, "named_parameters", None)
        if not callable(named):
            return {}
        return {
            path: repr(getattr(param, "value", None))
            for path, param in named()
        }

    def _prepare_gradient_payload(
        self,
        *,
        params: list[Parameter[Any]],
        epoch: int,
        batch: int,
    ) -> dict[str, Any] | None:
        active: list[tuple[Parameter[Any], TextualGradient]] = []
        for p in params:
            g = p.grad
            if g is not None and g.severity > 0:
                active.append((p, g))
        if not active:
            return None

        target_paths: list[str] = []
        seen: set[str] = set()
        by_field: dict[str, str] = {}
        messages: list[str] = []
        severity = 0.0
        before_values: dict[str, str] = {}
        for p, g in active:
            before_values[p.path] = repr(p.value)
            if g.message:
                messages.append(g.message)
            severity = max(severity, float(g.severity))
            paths = g.target_paths or [p.path]
            for path in paths:
                if path in seen:
                    continue
                seen.add(path)
                target_paths.append(path)
            if g.by_field:
                for field, critique in g.by_field.items():
                    by_field[field] = critique
            elif g.message:
                by_field[p.path] = g.message

        return {
            "epoch": int(epoch),
            "batch": int(batch),
            "message": "\n\n".join(messages),
            "severity": float(severity),
            "target_paths": target_paths,
            "by_field": by_field,
            "_before_values": before_values,
        }

    def _finalize_gradient_payload(
        self,
        payload: dict[str, Any],
        *,
        params: list[Parameter[Any]],
    ) -> dict[str, Any]:
        before_values = dict(payload.pop("_before_values", {}))
        after_values: dict[str, str] = {}
        for p in params:
            if p.path in before_values:
                after_values[p.path] = repr(p.read())

        changes = []
        for path, before in before_values.items():
            after = after_values.get(path, before)
            if before != after:
                changes.append(f"{path}\n- {before}\n+ {after}")
        payload["applied_diff"] = "\n\n".join(changes)
        return payload

    def _build_training_report(
        self,
        epochs: list[EpochReport],
        *,
        seed_hash: str,
        es_monitor: str | None,
        es_mode: str | None,
    ) -> TrainingReport:
        """Assemble the final report; pick the best epoch by val_loss.

        If early stopping supplied a monitor, use that; otherwise fall
        back to ``val_loss`` (lower is better). If no val data ran, use
        the last epoch.
        """
        if not epochs:
            return TrainingReport(
                epochs=[],
                best_epoch=-1,
                best_val_metric=float("nan"),
                best_hash_content="",
                seed_hash_content=seed_hash,
            )

        monitor = es_monitor or "val_loss"
        mode = es_mode or "min"

        def _value(r: EpochReport) -> float:
            if monitor == "val_loss":
                return (
                    r.val_loss if r.val_loss is not None else float("nan")
                )
            return float(r.val_metrics.get(monitor, float("nan")))

        best_idx = 0
        best_val: float = _value(epochs[0])
        for i, r in enumerate(epochs[1:], start=1):
            v = _value(r)
            if _is_better(v, best_val, mode):
                best_idx = i
                best_val = v

        best_epoch = epochs[best_idx]
        return TrainingReport(
            epochs=epochs,
            best_epoch=best_epoch.epoch,
            best_val_metric=best_val,
            best_hash_content=best_epoch.hash_content,
            seed_hash_content=seed_hash,
        )

    async def _quick_evaluator(self, param: Any, value: Any) -> float:
        """Single-input evaluator closure for OPRO/APE-style optimizers.

        Wave 4-1 defines the exact contract; for now this is a no-op
        fallback returning NaN so the attribute exists even if no wave-4
        optimizer ever calls it.
        """
        del param, value
        return float("nan")


def _is_better(a: float, b: float, mode: str) -> bool:
    import math as _math

    if _math.isnan(a):
        return False
    if _math.isnan(b):
        return True
    return a < b if mode == "min" else a > b


__all__ = ["Trainer"]
