"""Active-learning sampler: weight examples by the agent's uncertainty.

`UncertaintySampler` is an `operad.data.Sampler` that draws indices
with replacement, weighted by a (scorer-derived or user-supplied)
uncertainty score. Trainer integration is opt-in: if a sampler exposes
an async ``refresh()`` method, `Trainer.fit` calls it at the top of
each epoch under `no_grad()`.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Iterator

from ..benchmark.dataset import Dataset
from ..core.agent import Agent
from ..core.output import OperadOutput
from ..optim.gradmode import no_grad


class UncertaintySampler:
    """Weight examples by a scorer's uncertainty (higher → sampled more).

    The default uncertainty function expects a calibrated scorer
    (typically `operad.agents.reasoning.components.critic.Critic`)
    whose `Score.score` lives in [0, 1]. Uncertainty peaks at 0.5:
    ``uncertainty = 1 - abs(score - 0.5) * 2``.

    Without a ``scorer`` and without a custom ``uncertainty_fn``,
    the sampler falls back to agent self-consistency across three
    re-runs — expensive, documented for awareness.
    """

    def __init__(
        self,
        dataset: Dataset[Any, Any],
        agent: Agent[Any, Any],
        *,
        uncertainty_fn: Callable[[OperadOutput[Any]], float] | None = None,
        scorer: Agent[Any, Any] | None = None,
        num_samples: int | None = None,
        seed: int | None = None,
        refresh_every: int = 1,
    ) -> None:
        if refresh_every < 1:
            raise ValueError("refresh_every must be >= 1")
        self._dataset = dataset
        self._agent = agent
        self._scorer = scorer
        self._user_fn = uncertainty_fn
        self._num_samples = (
            num_samples if num_samples is not None else len(dataset)
        )
        if self._num_samples < 0:
            raise ValueError("num_samples must be >= 0")
        self._seed = seed
        self._refresh_every = refresh_every
        self._epoch_calls = 0
        self._weights: list[float] | None = None

    def __len__(self) -> int:
        return self._num_samples

    def __iter__(self) -> Iterator[int]:
        if self._weights is None:
            raise RuntimeError(
                "UncertaintySampler: call `await sampler.refresh()` before "
                "iterating (Trainer does this automatically per epoch)"
            )
        if self._num_samples == 0:
            return iter([])
        rng = random.Random(self._seed)
        picks = rng.choices(
            range(len(self._weights)),
            weights=self._weights,
            k=self._num_samples,
        )
        return iter(picks)

    async def refresh(self) -> None:
        """Recompute per-example weights.

        Work is elided on epochs that do not divide ``refresh_every``
        so real runs can amortise the scoring cost.
        """
        should_refresh = (
            self._weights is None
            or (self._epoch_calls % self._refresh_every) == 0
        )
        self._epoch_calls += 1
        if not should_refresh:
            return
        async with no_grad():
            weights: list[float] = []
            for i in range(len(self._dataset)):
                entry = self._dataset[i]
                out = await self._agent(entry.input)
                u = await self._compute_uncertainty(entry.input, out)
                weights.append(max(float(u), 1e-6))
        self._weights = weights

    async def _compute_uncertainty(
        self, x: Any, out: OperadOutput[Any]
    ) -> float:
        if self._user_fn is not None:
            return float(self._user_fn(out))
        if self._scorer is not None:
            from ..agents.reasoning.schemas import Candidate

            judgement = await self._scorer(
                Candidate(input=x, output=out.response)
            )
            score = float(judgement.response.score)
            return 1.0 - abs(score - 0.5) * 2.0
        samples = [await self._agent(x) for _ in range(3)]
        texts = {str(s.response.model_dump()) for s in samples}
        return (len(texts) - 1) / 2.0


__all__ = ["UncertaintySampler"]
