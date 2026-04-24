"""Algorithm-level events: a second event type alongside `AgentEvent`.

`AgentEvent` (in `observers/base.py`) covers leaf invocations.
`AlgorithmEvent` covers algorithm-level natural boundaries: a generation
of an evolutionary search, a round of debate, a candidate of best-of-N,
a cell of a sweep, an iteration of a refine/verify loop.

Per-`kind` payload conventions (informational; not enforced — observers
must tolerate unknown keys):

| kind         | payload keys                                               | emitted by   |
|--------------|------------------------------------------------------------|--------------|
| `algo_start` | algorithm-specific init params (e.g. `n`, `generations`)   | all          |
| `algo_end`   | terminal info (e.g. `score`, `best_index`)                 | all          |
| `algo_error` | `{"type": str, "message": str}`                            | all          |
| `generation` | `gen_index:int, population_scores:list[float], survivor_indices:list[int]` | Evolutionary |
| `round`      | `round_index:int, proposals:list[dict], critiques:list[dict], scores:list[float]` | Debate (aggregated per round) |
| `cell`       | `cell_index:int, parameters:dict, score: None`             | Sweep (score is a None placeholder; SweepCell has no native score) |
| `candidate`  | `candidate_index:int, score:float`                         | BestOfN      |
| `iteration`  | `iter_index:int, phase:str, score:float \\| None`          | SelfRefine, VerifierLoop, AutoResearcher |
"""

from __future__ import annotations

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
]


@dataclass
class AlgorithmEvent:
    run_id: str
    algorithm_path: str
    kind: AlgoKind
    payload: dict[str, Any]
    started_at: float
    finished_at: float | None
    metadata: dict[str, Any] = field(default_factory=dict)
