"""`operad.optim.lr_scheduler` — PyTorch-style LR scheduler zoo.

In operad an optimizer's "learning rate" is the knob a `RewriteAgent`
reads to decide how aggressive an edit to make on a `Parameter`. Low
`lr` nudges the value; high `lr` rewrites it. Schedulers anneal that
knob over an epoch budget, mirroring the `torch.optim.lr_scheduler`
surface so users can port intuition directly.

Base contract: `LRScheduler.step()` takes no args, bumps `last_epoch`,
computes one lr per param group via `get_lr()`, and writes the result
back into `optimizer.param_groups[i].lr`. `ReduceLROnPlateau` is a
sibling class (not a subclass) because its `step(metric)` signature
would otherwise break Liskov on the base. Downstream `Trainer`
dispatches on type.
"""

from __future__ import annotations

import bisect
import math
from abc import ABC, abstractmethod
from typing import Any, Literal, Sequence

from operad.optim.optimizer import Optimizer


class LRScheduler(ABC):
    """Abstract scheduler base. Concrete subclasses implement `get_lr`.

    `base_lrs` is snapshotted at construction: schedulers read from it,
    never from live `optimizer.param_groups[i].lr` (which they themselves
    mutate). `last_epoch` starts at -1 so that the first `step()` advances
    to epoch 0 and yields the "epoch-0" lr — matching PyTorch's convention.
    No auto-step in `__init__`; callers must `step()` explicitly.
    """

    def __init__(self, optimizer: Optimizer, last_epoch: int = -1) -> None:
        self.optimizer = optimizer
        self.base_lrs: list[float] = [float(g.lr) for g in optimizer.param_groups]
        self.last_epoch = int(last_epoch)

    @abstractmethod
    def get_lr(self) -> list[float]:
        """Compute the next lr per param group. Pure; no side effects."""

    def step(self) -> None:
        self.last_epoch += 1
        lrs = self.get_lr()
        for group, lr in zip(self.optimizer.param_groups, lrs, strict=True):
            group.lr = float(lr)

    def state_dict(self) -> dict[str, Any]:
        sd: dict[str, Any] = {
            "last_epoch": self.last_epoch,
            "base_lrs": list(self.base_lrs),
        }
        sd.update(self._extra_state())
        return sd

    def load_state_dict(self, sd: dict[str, Any]) -> None:
        self.last_epoch = int(sd["last_epoch"])
        self.base_lrs = [float(x) for x in sd["base_lrs"]]
        self._load_extra_state(sd)

    def _extra_state(self) -> dict[str, Any]:
        return {}

    def _load_extra_state(self, sd: dict[str, Any]) -> None:
        del sd


class ConstantLR(LRScheduler):
    """Holds every group at its base lr forever."""

    def get_lr(self) -> list[float]:
        return list(self.base_lrs)


class StepLR(LRScheduler):
    """Decay lr by `gamma` every `step_size` epochs."""

    def __init__(
        self,
        optimizer: Optimizer,
        step_size: int,
        gamma: float = 0.5,
        last_epoch: int = -1,
    ) -> None:
        if step_size < 1:
            raise ValueError(f"step_size must be >= 1, got {step_size}")
        super().__init__(optimizer, last_epoch)
        self.step_size = int(step_size)
        self.gamma = float(gamma)

    def get_lr(self) -> list[float]:
        t = max(self.last_epoch, 0)
        factor = self.gamma ** (t // self.step_size)
        return [base * factor for base in self.base_lrs]


class MultiStepLR(LRScheduler):
    """Decay lr by `gamma` at each of the listed epoch milestones."""

    def __init__(
        self,
        optimizer: Optimizer,
        milestones: Sequence[int],
        gamma: float = 0.5,
        last_epoch: int = -1,
    ) -> None:
        super().__init__(optimizer, last_epoch)
        self.milestones = sorted(set(int(m) for m in milestones))
        self.gamma = float(gamma)

    def get_lr(self) -> list[float]:
        n = bisect.bisect_right(self.milestones, self.last_epoch)
        factor = self.gamma ** n
        return [base * factor for base in self.base_lrs]


class ExponentialLR(LRScheduler):
    """Multiply lr by `gamma` every epoch: `lr = base * gamma ** last_epoch`."""

    def __init__(
        self,
        optimizer: Optimizer,
        gamma: float,
        last_epoch: int = -1,
    ) -> None:
        super().__init__(optimizer, last_epoch)
        self.gamma = float(gamma)

    def get_lr(self) -> list[float]:
        t = max(self.last_epoch, 0)
        factor = self.gamma ** t
        return [base * factor for base in self.base_lrs]


class CosineExplorationLR(LRScheduler):
    """Cosine anneal from `base` to `eta_min` over `T_max` epochs.

    At epoch 0: lr == base. At epoch `T_max`: lr == eta_min. Past
    `T_max` the lr is clamped at `eta_min`.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        T_max: int,
        eta_min: float = 0.0,
        last_epoch: int = -1,
    ) -> None:
        if T_max < 1:
            raise ValueError(f"T_max must be >= 1, got {T_max}")
        super().__init__(optimizer, last_epoch)
        self.T_max = int(T_max)
        self.eta_min = float(eta_min)

    def get_lr(self) -> list[float]:
        t = min(max(self.last_epoch, 0), self.T_max)
        cos = 0.5 * (1.0 + math.cos(math.pi * t / self.T_max))
        return [self.eta_min + (base - self.eta_min) * cos for base in self.base_lrs]


class WarmupLR(LRScheduler):
    """Linear ramp from 0 to `final_lr` over `warmup_epochs`, then hold.

    Note on semantics: every param group ramps toward the shared
    `final_lr` target, not toward its own `base_lr`. Per-group `base_lrs`
    are still snapshotted for `state_dict` symmetry but are not used in
    the formula.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        warmup_epochs: int,
        final_lr: float,
        last_epoch: int = -1,
    ) -> None:
        if warmup_epochs < 1:
            raise ValueError(f"warmup_epochs must be >= 1, got {warmup_epochs}")
        super().__init__(optimizer, last_epoch)
        self.warmup_epochs = int(warmup_epochs)
        self.final_lr = float(final_lr)

    def get_lr(self) -> list[float]:
        n = len(self.base_lrs)
        if self.last_epoch < 0:
            return [0.0] * n
        if self.last_epoch < self.warmup_epochs:
            lr = self.final_lr * (self.last_epoch + 1) / self.warmup_epochs
            return [lr] * n
        return [self.final_lr] * n


class ReduceLROnPlateau:
    """Reduce lr when a monitored metric stops improving.

    Sibling of `LRScheduler`, not a subclass: `step(metric)` breaks the
    zero-arg base contract. The `Trainer` dispatches on type. Uses
    PyTorch's relative threshold mode: a metric is "better" if it beats
    `best * (1 ± threshold)`.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        mode: Literal["min", "max"],
        factor: float = 0.5,
        patience: int = 2,
        threshold: float = 1e-4,
    ) -> None:
        if mode not in ("min", "max"):
            raise ValueError(f"mode must be 'min' or 'max', got {mode!r}")
        self.optimizer = optimizer
        self.mode: Literal["min", "max"] = mode
        self.factor = float(factor)
        self.patience = int(patience)
        self.threshold = float(threshold)
        self.base_lrs: list[float] = [float(g.lr) for g in optimizer.param_groups]
        self.last_epoch = -1
        self.best: float | None = None
        self.num_bad_epochs = 0

    def step(self, metric: float) -> None:
        self.last_epoch += 1
        current = float(metric)
        if self.best is None or self._is_better(current, self.best):
            self.best = current
            self.num_bad_epochs = 0
        else:
            self.num_bad_epochs += 1
        if self.num_bad_epochs > self.patience:
            for group in self.optimizer.param_groups:
                group.lr = float(group.lr) * self.factor
            self.num_bad_epochs = 0

    def _is_better(self, current: float, best: float) -> bool:
        if self.mode == "min":
            return current < best * (1.0 - self.threshold)
        return current > best * (1.0 + self.threshold)

    def state_dict(self) -> dict[str, Any]:
        return {
            "last_epoch": self.last_epoch,
            "base_lrs": list(self.base_lrs),
            "best": self.best,
            "num_bad_epochs": self.num_bad_epochs,
            "mode": self.mode,
            "factor": self.factor,
            "patience": self.patience,
            "threshold": self.threshold,
        }

    def load_state_dict(self, sd: dict[str, Any]) -> None:
        self.last_epoch = int(sd["last_epoch"])
        self.base_lrs = [float(x) for x in sd["base_lrs"]]
        best = sd.get("best")
        self.best = None if best is None else float(best)
        self.num_bad_epochs = int(sd["num_bad_epochs"])
        if "mode" in sd:
            self.mode = sd["mode"]
        if "factor" in sd:
            self.factor = float(sd["factor"])
        if "patience" in sd:
            self.patience = int(sd["patience"])
        if "threshold" in sd:
            self.threshold = float(sd["threshold"])


class ChainedScheduler:
    """Apply a list of schedulers in order on every `step()`.

    Each child mutates the same optimizer's param groups; the last
    child's write wins. Children advance their own `last_epoch`
    independently.
    """

    def __init__(self, schedulers: Sequence[LRScheduler]) -> None:
        if not schedulers:
            raise ValueError("ChainedScheduler requires at least one scheduler")
        self.schedulers: list[LRScheduler] = list(schedulers)

    def step(self) -> None:
        for sched in self.schedulers:
            sched.step()

    def state_dict(self) -> dict[str, Any]:
        return {"children": [s.state_dict() for s in self.schedulers]}

    def load_state_dict(self, sd: dict[str, Any]) -> None:
        children = sd["children"]
        if len(children) != len(self.schedulers):
            raise ValueError(
                f"state_dict has {len(children)} children but "
                f"ChainedScheduler has {len(self.schedulers)}"
            )
        for sched, child_sd in zip(self.schedulers, children, strict=True):
            sched.load_state_dict(child_sd)


class SequentialLR:
    """Switch between child schedulers at fixed epoch milestones.

    Owns its own `last_epoch`; delegates `step()` to whichever child is
    active for the current epoch. `milestones` has length
    `len(schedulers) - 1` and is sorted ascending.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        schedulers: Sequence[LRScheduler],
        milestones: Sequence[int],
    ) -> None:
        if not schedulers:
            raise ValueError("SequentialLR requires at least one scheduler")
        if len(milestones) != len(schedulers) - 1:
            raise ValueError(
                f"SequentialLR expected {len(schedulers) - 1} milestones, "
                f"got {len(milestones)}"
            )
        self.optimizer = optimizer
        self.schedulers: list[LRScheduler] = list(schedulers)
        self.milestones: list[int] = sorted(int(m) for m in milestones)
        self.last_epoch = -1

    def step(self) -> None:
        self.last_epoch += 1
        idx = bisect.bisect_right(self.milestones, self.last_epoch)
        self.schedulers[idx].step()

    def state_dict(self) -> dict[str, Any]:
        return {
            "last_epoch": self.last_epoch,
            "milestones": list(self.milestones),
            "children": [s.state_dict() for s in self.schedulers],
        }

    def load_state_dict(self, sd: dict[str, Any]) -> None:
        self.last_epoch = int(sd["last_epoch"])
        self.milestones = [int(m) for m in sd["milestones"]]
        children = sd["children"]
        if len(children) != len(self.schedulers):
            raise ValueError(
                f"state_dict has {len(children)} children but "
                f"SequentialLR has {len(self.schedulers)}"
            )
        for sched, child_sd in zip(self.schedulers, children, strict=True):
            sched.load_state_dict(child_sd)


__all__ = [
    "ChainedScheduler",
    "ConstantLR",
    "CosineExplorationLR",
    "ExponentialLR",
    "LRScheduler",
    "MultiStepLR",
    "ReduceLROnPlateau",
    "SequentialLR",
    "StepLR",
    "WarmupLR",
]
