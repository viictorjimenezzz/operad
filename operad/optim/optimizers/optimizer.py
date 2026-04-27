"""`Optimizer` base class — the "apply-gradients" half of the optim loop.

Mirrors `torch.optim.Optimizer`: parameter groups with per-group
overrides (`lr`, `momentum`, `constraint_override`), `zero_grad`,
`state_dict` / `load_state_dict`, and `step()`. Subclasses override
`step` and `_apply_param_update`; the shared `_apply_updates` helper
fans updates out under a concurrency cap and aggregates per-parameter
errors into an `ExceptionGroup` so one bad parameter does not tank a
batched step.

Default concrete subclass: `TextualGradientDescent` in
`operad/optim/optimizers/tgd.py`.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

from operad.optim.parameter import Parameter, ParameterConstraint


@dataclass
class ParamGroup:
    """A set of `Parameter`s sharing a single set of optimizer knobs.

    `constraint_override` and `extras` are accepted but not consulted by
    the base class; individual subclasses decide whether to honour them.
    `momentum` is stored for wave-4 subclasses; `TextualGradientDescent`
    leaves it at the default.
    """

    params: list[Parameter[Any]]
    lr: float = 1.0
    momentum: float = 0.0
    constraint_override: ParameterConstraint | None = None
    extras: dict[str, Any] = field(default_factory=dict)


_RESERVED_GROUP_KEYS = frozenset(
    {"params", "lr", "momentum", "constraint_override"}
)


# ---------------------------------------------------------------------------
# Base optimizer.
# ---------------------------------------------------------------------------


class Optimizer(ABC):
    """Abstract base for every `operad.optim` optimizer.

    The public surface matches PyTorch: pass either a flat iterable of
    `Parameter`s or a list of group dicts. Group dicts accept the keys
    `params`, `lr`, `momentum`, `constraint_override`; anything else is
    preserved on `ParamGroup.extras`.
    """

    max_concurrent_updates: int = 4

    def __init__(
        self,
        params: Iterable[Parameter[Any]] | Iterable[dict[str, Any]],
        defaults: dict[str, Any] | None = None,
    ) -> None:
        self.defaults: dict[str, Any] = dict(defaults or {})
        self.state: dict[str, dict[str, Any]] = {}
        self.param_groups: list[ParamGroup] = []

        items = list(params)
        if not items:
            raise ValueError("optimizer got an empty parameter iterable")

        has_dict = any(isinstance(x, dict) for x in items)
        has_param = any(isinstance(x, Parameter) for x in items)
        if has_dict and has_param:
            raise TypeError(
                "cannot mix Parameter and dict entries; pass either "
                "a flat Parameter iterable or a list of group dicts"
            )

        if has_dict:
            for raw in items:
                self.param_groups.append(self._build_group(raw))
        else:
            self.param_groups.append(
                self._build_group({"params": list(items)})
            )

    def _build_group(self, raw: dict[str, Any]) -> ParamGroup:
        if "params" not in raw:
            raise KeyError("parameter group is missing required key 'params'")
        params = list(raw["params"])
        for p in params:
            if not isinstance(p, Parameter):
                raise TypeError(
                    f"parameter group contains non-Parameter entry {p!r}"
                )

        def _get(key: str, fallback: Any) -> Any:
            if key in raw:
                return raw[key]
            return self.defaults.get(key, fallback)

        extras = {k: v for k, v in raw.items() if k not in _RESERVED_GROUP_KEYS}
        for k, v in self.defaults.items():
            if k in _RESERVED_GROUP_KEYS or k in raw:
                continue
            extras.setdefault(k, v)

        return ParamGroup(
            params=params,
            lr=float(_get("lr", 1.0)),
            momentum=float(_get("momentum", 0.0)),
            constraint_override=_get("constraint_override", None),
            extras=extras,
        )

    def zero_grad(self, *, set_to_none: bool = True) -> None:
        """Clear `.grad` on every parameter in every group.

        `set_to_none` is accepted for PyTorch parity; textual gradients
        have no zero-tensor equivalent, so `False` falls back to the same
        behaviour as `True`.
        """
        del set_to_none  # no alternative behaviour to dispatch
        for group in self.param_groups:
            for p in group.params:
                p.zero_grad()

    def named_parameters(self) -> Iterator[tuple[str, Parameter[Any]]]:
        for group in self.param_groups:
            for p in group.params:
                yield p.path, p

    def add_param_group(self, group: dict[str, Any]) -> None:
        self.param_groups.append(self._build_group(group))

    def state_dict(self) -> dict[str, Any]:
        state: dict[str, dict[str, Any]] = {}
        for _, p in self.named_parameters():
            entry = dict(self.state.get(p.path, {}))
            entry["momentum_state"] = dict(p.momentum_state)
            state[p.path] = entry
        return {
            "state": state,
            "param_groups": [
                {
                    "lr": g.lr,
                    "momentum": g.momentum,
                    "constraint_override": g.constraint_override,
                    "extras": dict(g.extras),
                    "param_paths": [p.path for p in g.params],
                }
                for g in self.param_groups
            ],
        }

    def load_state_dict(self, sd: dict[str, Any]) -> None:
        saved_state: dict[str, dict[str, Any]] = dict(sd.get("state", {}))
        saved_groups: list[dict[str, Any]] = list(sd.get("param_groups", []))

        if len(saved_groups) != len(self.param_groups):
            raise ValueError(
                f"state_dict has {len(saved_groups)} param groups but "
                f"optimizer has {len(self.param_groups)}"
            )

        by_path: dict[str, Parameter[Any]] = {p.path: p for _, p in self.named_parameters()}

        self.state.clear()
        for path, entry in saved_state.items():
            entry = dict(entry)
            momentum_state = entry.pop("momentum_state", {})
            p = by_path.get(path)
            if p is not None:
                p.momentum_state = dict(momentum_state)
            self.state[path] = entry

        for group, saved in zip(self.param_groups, saved_groups, strict=True):
            expected_paths = list(saved.get("param_paths", []))
            actual_paths = [p.path for p in group.params]
            if expected_paths and expected_paths != actual_paths:
                raise ValueError(
                    f"param group membership mismatch: expected {expected_paths}, "
                    f"got {actual_paths}"
                )
            group.lr = float(saved.get("lr", group.lr))
            group.momentum = float(saved.get("momentum", group.momentum))
            group.constraint_override = saved.get(
                "constraint_override", group.constraint_override
            )
            group.extras = dict(saved.get("extras", {}))

    @abstractmethod
    async def step(self) -> None:
        """Apply one optimizer step over every parameter with a live grad."""

    @abstractmethod
    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        """Apply the subclass-specific update rule to a single parameter."""

    async def _apply_updates(
        self, items: list[tuple[Parameter[Any], ParamGroup]]
    ) -> None:
        """Fan `_apply_param_update` out under `max_concurrent_updates`.

        Collects exceptions and re-raises them as a single `ExceptionGroup`
        so one failing parameter does not silently swallow the rest.
        """
        if not items:
            return

        sem = asyncio.Semaphore(max(1, self.max_concurrent_updates))

        async def _run(param: Parameter[Any], group: ParamGroup) -> None:
            async with sem:
                await self._apply_param_update(param, group)

        results = await asyncio.gather(
            *(_run(p, g) for p, g in items), return_exceptions=True
        )
        errors = [r for r in results if isinstance(r, BaseException)]
        if errors:
            raise ExceptionGroup("optimizer step failed", errors)


__all__ = ["Optimizer", "ParamGroup"]
