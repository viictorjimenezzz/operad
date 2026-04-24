"""`TrainerProgressObserver` state tracking across synthetic events."""

from __future__ import annotations

from operad.runtime.events import AlgorithmEvent
from operad.train import TrainerProgressObserver


def _algo(
    kind: str,
    algorithm_path: str = "Trainer",
    payload: dict | None = None,
    t: float = 0.0,
) -> AlgorithmEvent:
    return AlgorithmEvent(
        run_id="r",
        algorithm_path=algorithm_path,
        kind=kind,  # type: ignore[arg-type]
        payload=payload or {},
        started_at=t,
        finished_at=t,
    )


async def test_progress_observer_starts_fresh_on_algo_start() -> None:
    obs = TrainerProgressObserver()
    await obs.on_event(
        _algo("algo_start", payload={"epochs": 5, "seed_hash_content": "abc"})
    )
    assert obs.state.epochs_total == 5
    assert obs.state.current_epoch == 0
    assert obs.state.finished is False


async def test_progress_observer_tracks_batches_and_epochs() -> None:
    obs = TrainerProgressObserver()
    await obs.on_event(_algo("algo_start", payload={"epochs": 2}))
    await obs.on_event(_algo("iteration", payload={"phase": "epoch_start", "epoch": 0}))
    await obs.on_event(
        _algo("batch_start", algorithm_path="DataLoader", payload={"batch_index": 0, "batch_size": 1})
    )
    await obs.on_event(
        _algo("batch_end", algorithm_path="DataLoader", payload={"batch_index": 0, "duration_ms": 50.0})
    )
    await obs.on_event(
        _algo("batch_start", algorithm_path="DataLoader", payload={"batch_index": 1, "batch_size": 1})
    )
    await obs.on_event(
        _algo("batch_end", algorithm_path="DataLoader", payload={"batch_index": 1, "duration_ms": 50.0})
    )
    await obs.on_event(_algo("iteration", payload={"phase": "epoch_end", "epoch": 0}))

    assert obs.state.current_batch == 2
    assert obs.state.batches_total == 2
    assert obs.state.rate_batches_per_s > 0


async def test_progress_observer_marks_finished_on_algo_end() -> None:
    obs = TrainerProgressObserver()
    await obs.on_event(_algo("algo_start", payload={"epochs": 1}))
    await obs.on_event(_algo("algo_end"))
    assert obs.state.finished is True


async def test_progress_observer_silent_noop_without_rich(monkeypatch) -> None:
    """If Rich is missing, the observer still tracks state and never raises."""

    obs = TrainerProgressObserver()
    # Force the no-rich branch regardless of whether it's installed.
    obs._rich_available = False  # type: ignore[attr-defined]
    await obs.on_event(_algo("algo_start", payload={"epochs": 3}))
    await obs.on_event(_algo("iteration", payload={"phase": "epoch_start", "epoch": 0}))
    await obs.on_event(
        _algo("batch_start", algorithm_path="DataLoader", payload={"batch_index": 0})
    )
    assert obs.state.epochs_total == 3
    assert obs.state.current_batch == 1
