"""Offline helpers for `examples/train_demo.py` (and wave 5-5 cassette replay).

The training story in 5-1 runs deterministically with no LLM and no
network. That requires stubs at every place the default stack would
otherwise call a provider:

- the target leaf (`KeywordLeaf`) — custom `forward`, no strands
- the critic (`FakeCritic`) — custom `forward`, scores by keyword presence
- the propagator + parameter-grad agent (`FakeBackpropAgent`,
  `FakeTextParameterGrad`) — the Trainer does not forward the factory
  kwargs `backward()` accepts (trainer.py:268), so we swap the classes
  in `operad.optim.backward`'s namespace for the lifetime of `fit()` via
  the `offline_backward()` context manager
- the rewriter (`FakeTextRewriter`) — passed through
  `TextualGradientDescent(rewriter_factory=...)`, the first-class seam

`build_demo_agent_and_data()` constructs the toy problem: a single-leaf
agent whose output equals its concatenated role + task, scored against
a fixed set of target keywords. Applying the fakes across epochs grows
the role/task strings until every keyword is present, at which point
the critic returns score=1.0 and emits a null gradient.
"""

from __future__ import annotations

import contextlib
import importlib
import re
from typing import Iterator

from pydantic import BaseModel

from operad import Agent, Configuration, Dataset
from operad.algorithms.judge import Candidate, Score
from operad.benchmark.entry import Entry
from operad.core.config import Sampling
from operad.data import DataLoader, random_split
from operad.metrics.base import MetricBase
from operad.optim.grad_agent import (
    BackpropAgent,
    ParameterGradAgent,
    ParameterGradInput,
    ParameterGradOutput,
    PropagateInput,
    PropagateOutput,
)
from operad.optim.parameter import Parameter
from operad.optim.rewrite import RewriteAgent, RewriteRequest, RewriteResponse


# `import operad.optim.backward as _bm` resolves to the *function* `backward`
# (shadowed by `operad/optim/__init__.py`), not the submodule; go through
# `importlib` to get the module whose globals we need to patch.
_backward_mod = importlib.import_module("operad.optim.backward")


# ---------------------------------------------------------------------------
# Toy I/O schemas
# ---------------------------------------------------------------------------


class Q(BaseModel):
    prompt: str = ""


class R(BaseModel):
    answer: str = ""


# ---------------------------------------------------------------------------
# The trainable leaf — its output literally contains role + task text
# ---------------------------------------------------------------------------


class KeywordLeaf(Agent[Q, R]):
    """Toy leaf whose answer echoes `role + task` verbatim.

    Because the output string is a pure function of the prompt-building
    fields, editing `role` or `task` through the optimizer is directly
    visible in the scored answer.
    """

    input = Q
    output = R
    role = "assistant."
    task = "answer the question."

    async def forward(self, x: Q) -> R:  # type: ignore[override]
        _ = x
        return R(answer=f"{self.role} | {self.task}")


# ---------------------------------------------------------------------------
# Metric + critic — both score by keyword presence
# ---------------------------------------------------------------------------


def _present(text: str, keyword: str) -> bool:
    return keyword.casefold() in text.casefold()


def _first_missing(text: str, keywords: list[str]) -> str | None:
    for k in keywords:
        if not _present(text, k):
            return k
    return None


class KeywordMatch(MetricBase):
    """Fraction of target keywords present in `predicted.answer`."""

    def __init__(self, targets: list[str]) -> None:
        if not targets:
            raise ValueError("KeywordMatch needs at least one target")
        self.targets = list(targets)
        self.name = "keyword_match"

    async def score(
        self, predicted: BaseModel, expected: BaseModel
    ) -> float:
        _ = expected
        text = str(getattr(predicted, "answer", ""))
        hit = sum(1 for k in self.targets if _present(text, k))
        return hit / len(self.targets)


class FakeCritic(Agent[Candidate, Score]):
    """Deterministic stand-in for an LLM judge.

    Scores the candidate's ``answer`` by how many target keywords it
    contains; the rationale quotes the first missing keyword so the
    rewriter has something concrete to append. Emits an empty rationale
    with ``score=1.0`` once every keyword is present — this is what
    trips `CriticLoss.null_threshold=1.0` and stops the optimizer.
    """

    input = Candidate
    output = Score

    def __init__(
        self,
        *,
        config: Configuration | None = None,
        targets: list[str],
    ) -> None:
        super().__init__(config=config)
        if not targets:
            raise ValueError("FakeCritic needs at least one target")
        self.targets = list(targets)

    async def forward(self, x: Candidate) -> Score:  # type: ignore[override]
        out = getattr(x, "output", None)
        text = str(getattr(out, "answer", "")) if out is not None else ""
        hit = sum(1 for k in self.targets if _present(text, k))
        fraction = hit / len(self.targets)
        missing = _first_missing(text, self.targets)
        rationale = (
            f'include the word "{missing}"' if missing is not None else ""
        )
        return Score(score=fraction, rationale=rationale)


# ---------------------------------------------------------------------------
# Offline gradient agents — pass the critique through verbatim
# ---------------------------------------------------------------------------


class FakeBackpropAgent(BackpropAgent):
    """Propagate the downstream critique without calling an LLM.

    Uses ``getattr`` with defaults because ``abuild()``'s symbolic trace
    constructs the input via ``model_construct``, which bypasses field
    defaults; the sentinel therefore carries no attributes at all.
    """

    async def forward(  # type: ignore[override]
        self, x: PropagateInput
    ) -> PropagateOutput:
        message = getattr(x, "downstream_gradient", "") or ""
        by_field = dict(getattr(x, "downstream_by_field", {}) or {})
        return PropagateOutput(
            message=message,
            by_field=by_field,
            severity=1.0 if message else 0.0,
        )


class FakeTextParameterGrad(ParameterGradAgent):
    """Attribute the output critique to every text parameter equally.

    Sentinel-safe: see ``FakeBackpropAgent`` for the rationale.
    """

    async def forward(  # type: ignore[override]
        self, x: ParameterGradInput
    ) -> ParameterGradOutput:
        message = getattr(x, "output_gradient", "") or ""
        return ParameterGradOutput(
            message=message,
            severity=1.0 if message else 0.0,
        )


# ---------------------------------------------------------------------------
# Offline rewriter — parses the quoted keyword and appends it once
# ---------------------------------------------------------------------------


_QUOTED = re.compile(r'"([^"]+)"')


class FakeTextRewriter(RewriteAgent):
    """Append the first quoted token from the gradient to the old value.

    Idempotent: if the token is already present (case-insensitive), the
    old value is returned unchanged — which stabilises the hash once the
    critic stops producing gradients.
    """

    input = RewriteRequest
    output = RewriteResponse

    async def forward(  # type: ignore[override]
        self, x: RewriteRequest
    ) -> RewriteResponse:
        gradient = getattr(x, "gradient", "") or ""
        old_value = getattr(x, "old_value", "") or ""
        match = _QUOTED.search(gradient)
        if match is None:
            return RewriteResponse(new_value=old_value, rationale="no token")
        token = match.group(1)
        if _present(old_value, token):
            return RewriteResponse(
                new_value=old_value, rationale="already present"
            )
        return RewriteResponse(
            new_value=f"{old_value} {token}",
            rationale=f"appended {token!r}",
        )


# ---------------------------------------------------------------------------
# Scoped swap of the backward defaults
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def offline_backward() -> Iterator[None]:
    """Replace the default LLM-backed propagator + parameter-grad agents.

    `Trainer._run_batch` calls `backward()` without forwarding factory
    overrides, so the default `BackpropAgent()` and
    `parameter_grad_for(kind)()` get built and invoked. Both default
    leaves use a strands-backed forward; replacing the module-level
    names in `operad.optim.backward` is the supported seam to redirect
    that resolution to custom-forward stubs. The originals are restored
    on exit.
    """
    original_backprop = _backward_mod.BackpropAgent
    original_lookup = _backward_mod.parameter_grad_for
    _backward_mod.BackpropAgent = FakeBackpropAgent  # type: ignore[misc]
    _backward_mod.parameter_grad_for = (  # type: ignore[assignment]
        lambda kind: FakeTextParameterGrad
    )
    try:
        yield
    finally:
        _backward_mod.BackpropAgent = original_backprop  # type: ignore[misc]
        _backward_mod.parameter_grad_for = original_lookup  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Toy dataset + factory
# ---------------------------------------------------------------------------


def _offline_config() -> Configuration:
    """A Configuration that cannot accidentally reach a provider.

    Port 0 is unroutable and every leaf here overrides `forward`, so
    strands is never wired anyway; this mirrors
    `examples/evolutionary_demo.py`'s offline config.
    """
    return Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="demo",
        sampling=Sampling(temperature=0.0, max_tokens=16),
    )


_TRAINABLE_PATHS = ("role", "task")


def role_task_parameters(agent: Agent[Q, R]) -> list[Parameter]:
    """Return just the `role` + `task` parameters of `agent`.

    `Agent.parameters()` yields every declared field (role, task, rules,
    examples, plus config knobs) with `requires_grad=True` by default.
    The demo only edits free-text prompt fields, so we narrow here
    rather than threading ``freeze_parameters(...)`` through the caller.
    """
    return [p for p in agent.parameters() if p.path in _TRAINABLE_PATHS]


async def build_demo_agent_and_data(
    targets: list[str],
    *,
    seed: int = 0,
    n_rows: int = 6,
    batch_size: int = 2,
) -> tuple[KeywordLeaf, DataLoader[Q, R], Dataset[Q, R], KeywordMatch]:
    """Return `(agent, train_loader, val_ds, metric)` for the demo."""
    cfg = _offline_config()
    agent = KeywordLeaf(config=cfg)
    await agent.abuild()

    entries = [
        Entry[Q, R](input=Q(prompt=f"q{i}"), expected_output=R(answer=""))
        for i in range(n_rows)
    ]
    dataset: Dataset[Q, R] = Dataset(
        entries=entries, name="train_demo", version="0.1.0", in_cls=Q, out_cls=R
    )
    train_frac = (n_rows - max(1, n_rows // 3)) / n_rows
    val_frac = 1.0 - train_frac
    train_ds, val_ds = random_split(
        dataset, [train_frac, val_frac], seed=seed
    )
    loader: DataLoader[Q, R] = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True, seed=seed
    )
    metric = KeywordMatch(targets=targets)
    return agent, loader, val_ds, metric


async def build_fake_critic(targets: list[str]) -> FakeCritic:
    critic = FakeCritic(config=_offline_config(), targets=targets)
    await critic.abuild()
    return critic


async def build_fake_rewriter() -> FakeTextRewriter:
    rewriter = FakeTextRewriter(config=_offline_config())
    await rewriter.abuild()
    return rewriter


__all__ = [
    "FakeBackpropAgent",
    "FakeCritic",
    "FakeTextParameterGrad",
    "FakeTextRewriter",
    "KeywordLeaf",
    "KeywordMatch",
    "Q",
    "R",
    "build_demo_agent_and_data",
    "build_fake_critic",
    "build_fake_rewriter",
    "offline_backward",
    "role_task_parameters",
]
