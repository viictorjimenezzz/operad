"""Algorithm-level events: a second event type alongside `AgentEvent`.

`AgentEvent` (in `observers/base.py`) covers leaf invocations.
`AlgorithmEvent` covers algorithm-level natural boundaries: a generation
of an evolutionary search, a round of debate, a candidate of best-of-N,
a cell of a sweep, an iteration of a refine/verify loop.

Per-`kind` payload conventions (informational; not enforced — observers
must tolerate unknown keys):

| kind          | payload keys                                                                                                                        | emitted by   |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------|--------------|
| `algo_start`  | algorithm-specific init params (e.g. `n`, `generations`)                                                                            | all          |
| `algo_end`    | terminal info (e.g. `score`, `best_index`)                                                                                          | all          |
| `algo_error`  | `{"type": str, "message": str}`                                                                                                     | all          |
| `generation`  | `gen_index:int, population_scores:list[float], survivor_indices:list[int], selected_lineage_id:str, individuals:list[dict], mutations:list[dict], op_success_counts:dict, op_attempt_counts:dict` | Evolutionary |
| `round`       | `round_index:int, proposals:list[dict], critiques:list[dict], scores:list[float]`                                                   | Debate (aggregated per round) |
| `cell`        | `cell_index:int, parameters:dict, score: None`                                                                                      | Sweep (score is a None placeholder; SweepCell has no native score) |
| `candidate`   | `candidate_index:int, score:float`                                                                                                  | BestOfN      |
| `iteration`   | `iter_index:int, phase:str, score:float \\| None`                                                                                   | SelfRefine, VerifierAgent, AutoResearcher |
| `batch_start` | `batch_index:int, batch_size:int, hash_batch:str, epoch:int \\| None`                                                                | DataLoader   |
| `batch_end`   | `batch_index:int, batch_size:int, duration_ms:float, epoch:int \\| None`                                                             | DataLoader (fires on *next* `__anext__` or `StopAsyncIteration`; measures how long the consumer held the batch) |
| `gradient_applied` | `epoch:int, batch:int, message:str, target_paths:list[str]`                                                                     | Trainer      |
| `plan`        | `attempt_index:int, plan:dict`                                                                                                      | AutoResearcher |

The `mutations` entries in `generation` payloads have shape
`{"individual_id": int, "lineage_id": str, "op": str | None, "improved": bool}`, where
`op` is `None` when the individual is a surviving unmutated clone and
`improved` is `True` iff that individual's score exceeds the previous
generation's median (or the seed's score on generation 0). The
`mutations` list is capped at `EvoGradient._max_mutation_entries` (200
by default); aggregate counts remain accurate past the cap.

The richer `individuals` entries include lineage and parameter-change
data for dashboard drilldowns:
`individual_id`, `lineage_id`, `parent_lineage_id`, `score`, `selected`,
`op`, `path`, `improved`, and `parameter_deltas`.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal


AlgoKind = Literal[
    "algo_start",
    "algo_end",
    "algo_error",
    "generation",
    "round",
    "cell",
    "candidate",
    "iteration",
    "batch_start",
    "batch_end",
    "gradient_applied",
    "plan",
]


# Epoch propagation for DataLoader `batch_*` events. `Trainer.fit` sets
# this at the top of each epoch and resets it at the end; callers
# iterating a `DataLoader` outside a Trainer see `None`.
_CURRENT_EPOCH: ContextVar[int | None] = ContextVar(
    "_CURRENT_EPOCH", default=None
)


def set_current_epoch(epoch: int | None) -> None:
    """Set the epoch reported in subsequent `batch_*` payloads."""
    _CURRENT_EPOCH.set(epoch)


def get_current_epoch() -> int | None:
    """Return the epoch previously set by `set_current_epoch`, else None."""
    return _CURRENT_EPOCH.get()


@dataclass
class AlgorithmEvent:
    run_id: str
    algorithm_path: str
    kind: AlgoKind
    payload: dict[str, Any]
    started_at: float
    finished_at: float | None
    metadata: dict[str, Any] = field(default_factory=dict)
