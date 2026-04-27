"""Aggregated views over the run registry: agents, algorithms, training.

These routes are projections on top of the existing ``RunRegistry`` and
the archive store. They feed the redesigned three-rail dashboard
(Agents / Algorithms / Training) without changing the underlying
observer pipeline.

Conventions:

* **agent group key** = ``hash_content`` of the root agent.
  Two agent runs share a group when their root agent has the same
  declared state. The set of runs in a group is the W&B-equivalent
  "Group" of N "Runs".
* **algorithm group key** = ``algorithm_path``.
  Each entry in ``/algorithms`` is one invocation of an algorithm
  script. Optionally grouped by class name.
* **training group key** = trainer's root agent ``hash_content``,
  same as the agent group key but filtered to runs whose
  ``algorithm_path`` ends with ``.Trainer``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ..runs import RunInfo


router = APIRouter(tags=["groups"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _latest_root_hash_content(info: RunInfo) -> str | None:
    """Find the most recent root-agent ``hash_content`` for this run."""
    root = info.root_agent_path
    if not isinstance(root, str):
        return None
    for env in reversed(list(info.events)):
        if env.get("type") != "agent_event":
            continue
        if env.get("kind") not in {"end", "start"}:
            continue
        if env.get("agent_path") != root:
            continue
        meta = env.get("metadata")
        if not isinstance(meta, dict):
            continue
        hc = meta.get("hash_content")
        if isinstance(hc, str) and hc:
            return hc
    return None


def _class_name_from_path(path: str | None) -> str | None:
    if not isinstance(path, str) or not path:
        return None
    return path.rsplit(".", 1)[-1]


def _agent_class_name(info: RunInfo) -> str | None:
    return _class_name_from_path(info.root_agent_path)


def _all_runs(request: Request) -> list[RunInfo]:
    obs = request.app.state.observer
    try:
        return list(obs.registry.list())
    except Exception:
        return []


def _is_trainer(info: RunInfo) -> bool:
    return isinstance(info.algorithm_path, str) and info.algorithm_path.endswith(".Trainer")


# ---------------------------------------------------------------------------
# /agents — agent instances (groups by hash_content)
# ---------------------------------------------------------------------------


@router.get("/api/agents")
async def list_agent_groups(request: Request) -> JSONResponse:
    """Return one entry per agent instance (root ``hash_content``).

    Each entry aggregates:
      ``count``      number of invocations seen for this instance
      ``running``    number currently running
      ``errors``     number that failed
      ``last_seen``  unix-seconds of latest activity
      ``first_seen`` unix-seconds of earliest activity
      ``class_name`` agent root class name
      ``root_agent_path`` dotted path
      ``hash_content`` group key
      ``latencies``  rolling list of last-N latency samples (for sparkline)
      ``prompt_tokens`` / ``completion_tokens`` totals
      ``cost_usd``     best-effort total cost
      ``run_ids``    truncated list of recent run ids in this group
    """
    runs = _all_runs(request)
    groups: dict[str, dict[str, Any]] = {}
    for info in runs:
        if info.is_algorithm and not _is_trainer(info):
            # Algorithm orchestrators belong on the algorithms rail; their
            # synthetic children would otherwise pollute "agents".
            continue
        if info.synthetic:
            # Synthetic children are inner agent invocations of an
            # algorithm; they belong to the algorithm rail's drill-down.
            continue
        hc = _latest_root_hash_content(info)
        if hc is None:
            # No identity hash yet (run started but agent didn't end);
            # surface anyway under a per-run pseudo group so the row
            # doesn't disappear from the sidebar.
            hc = f"_pending_{info.run_id}"
        bucket = groups.setdefault(
            hc,
            {
                "hash_content": hc,
                "class_name": _agent_class_name(info),
                "root_agent_path": info.root_agent_path,
                "count": 0,
                "running": 0,
                "errors": 0,
                "last_seen": 0.0,
                "first_seen": float("inf"),
                "latencies": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost_usd": 0.0,
                "run_ids": [],
                "is_trainer": False,
            },
        )
        bucket["count"] += 1
        if info.state == "running":
            bucket["running"] += 1
        elif info.state == "error":
            bucket["errors"] += 1
        bucket["last_seen"] = max(bucket["last_seen"], info.last_event_at)
        if info.started_at < bucket["first_seen"]:
            bucket["first_seen"] = info.started_at
        bucket["latencies"].append(info.duration_ms)
        bucket["prompt_tokens"] += info.total_prompt_tokens
        bucket["completion_tokens"] += info.total_completion_tokens
        bucket["run_ids"].append(info.run_id)
        if not bucket["class_name"] and info.root_agent_path:
            bucket["class_name"] = _agent_class_name(info)
        if _is_trainer(info):
            bucket["is_trainer"] = True

    # cost is observed elsewhere; pull from cost observer if available.
    cost = getattr(request.app.state, "cost_observer", None)
    if cost is not None:
        try:
            totals = cost.totals()
        except Exception:
            totals = {}
        for bucket in groups.values():
            for run_id in bucket["run_ids"]:
                t = totals.get(run_id) or {}
                if isinstance(t, dict):
                    c = t.get("cost_usd") or 0.0
                    if isinstance(c, (int, float)):
                        bucket["cost_usd"] += float(c)

    out: list[dict[str, Any]] = []
    for bucket in groups.values():
        if bucket["first_seen"] == float("inf"):
            bucket["first_seen"] = bucket["last_seen"]
        # Trim retained run_ids to the last 50 to keep payload small.
        bucket["run_ids"] = bucket["run_ids"][-50:]
        bucket["latencies"] = bucket["latencies"][-50:]
        out.append(bucket)
    out.sort(key=lambda b: b["last_seen"], reverse=True)
    return JSONResponse(out)


@router.get("/api/agents/{hash_content}")
async def get_agent_group(request: Request, hash_content: str) -> JSONResponse:
    """Return aggregated KPIs for a single agent group + the runs in it."""
    target = hash_content.strip()
    if not target:
        raise HTTPException(status_code=400, detail="hash_content is required")
    runs = _all_runs(request)
    group_runs: list[RunInfo] = []
    for info in runs:
        if info.is_algorithm and not _is_trainer(info):
            continue
        if info.synthetic:
            continue
        hc = _latest_root_hash_content(info)
        if hc and hc == target:
            group_runs.append(info)
    if not group_runs:
        raise HTTPException(status_code=404, detail="no runs match this hash_content")

    # Aggregations
    latencies = [info.duration_ms for info in group_runs if info.duration_ms > 0]
    prompt_tokens = sum(info.total_prompt_tokens for info in group_runs)
    completion_tokens = sum(info.total_completion_tokens for info in group_runs)
    cost_usd = 0.0
    cost = getattr(request.app.state, "cost_observer", None)
    if cost is not None:
        try:
            totals = cost.totals()
        except Exception:
            totals = {}
        for info in group_runs:
            t = totals.get(info.run_id) or {}
            if isinstance(t, dict):
                c = t.get("cost_usd") or 0.0
                if isinstance(c, (int, float)):
                    cost_usd += float(c)

    running = sum(1 for r in group_runs if r.state == "running")
    errors = sum(1 for r in group_runs if r.state == "error")

    return JSONResponse(
        {
            "hash_content": target,
            "class_name": _class_name_from_path(group_runs[-1].root_agent_path),
            "root_agent_path": group_runs[-1].root_agent_path,
            "count": len(group_runs),
            "running": running,
            "errors": errors,
            "last_seen": max(r.last_event_at for r in group_runs),
            "first_seen": min(r.started_at for r in group_runs),
            "latencies": latencies,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost_usd,
            "is_trainer": any(_is_trainer(r) for r in group_runs),
            "runs": [r.summary() for r in sorted(group_runs, key=lambda r: r.started_at)],
        }
    )


@router.get("/api/agents/{hash_content}/runs")
async def list_agent_group_runs(request: Request, hash_content: str) -> JSONResponse:
    """Return only the run summaries for an agent group (lighter payload)."""
    target = hash_content.strip()
    if not target:
        raise HTTPException(status_code=400, detail="hash_content is required")
    runs = _all_runs(request)
    matches: list[RunInfo] = []
    for info in runs:
        if info.synthetic:
            continue
        hc = _latest_root_hash_content(info)
        if hc and hc == target:
            matches.append(info)
    matches.sort(key=lambda r: r.started_at)
    return JSONResponse([r.summary() for r in matches])


# ---------------------------------------------------------------------------
# /algorithms — algorithm orchestrator runs
# ---------------------------------------------------------------------------


@router.get("/api/algorithms")
async def list_algorithm_runs(request: Request) -> JSONResponse:
    """Return one entry per algorithm orchestrator run, grouped by class."""
    runs = _all_runs(request)
    groups: dict[str, list[RunInfo]] = {}
    for info in runs:
        if not info.is_algorithm:
            continue
        if info.synthetic:
            continue
        if _is_trainer(info):
            # Trainer goes on its own rail; keep the algorithms rail focused
            # on Beam / Sweep / Debate / Evo / SelfRefine / AutoResearcher.
            continue
        key = info.algorithm_path or "_unknown"
        groups.setdefault(key, []).append(info)

    out: list[dict[str, Any]] = []
    for key, members in groups.items():
        members.sort(key=lambda r: r.started_at)
        out.append(
            {
                "algorithm_path": key,
                "class_name": _class_name_from_path(key),
                "count": len(members),
                "running": sum(1 for r in members if r.state == "running"),
                "errors": sum(1 for r in members if r.state == "error"),
                "last_seen": max(r.last_event_at for r in members),
                "first_seen": min(r.started_at for r in members),
                "runs": [r.summary() for r in members],
            }
        )
    out.sort(key=lambda g: g["last_seen"], reverse=True)
    return JSONResponse(out)


# ---------------------------------------------------------------------------
# /trainings — Trainer-orchestrated training runs
# ---------------------------------------------------------------------------


@router.get("/api/trainings")
async def list_training_runs(request: Request) -> JSONResponse:
    """Return one entry per Trainer.fit() run, grouped by trainee identity."""
    runs = _all_runs(request)
    groups: dict[str, list[RunInfo]] = {}
    pending: list[RunInfo] = []
    for info in runs:
        if not _is_trainer(info):
            continue
        if info.synthetic:
            continue
        hc = _latest_root_hash_content(info)
        key = hc or f"_pending_{info.run_id}"
        if hc is None:
            pending.append(info)
        groups.setdefault(key, []).append(info)

    out: list[dict[str, Any]] = []
    for key, members in groups.items():
        members.sort(key=lambda r: r.started_at)
        head = members[-1]
        out.append(
            {
                "hash_content": key if not key.startswith("_pending_") else None,
                "class_name": _class_name_from_path(head.root_agent_path),
                "root_agent_path": head.root_agent_path,
                "count": len(members),
                "running": sum(1 for r in members if r.state == "running"),
                "errors": sum(1 for r in members if r.state == "error"),
                "last_seen": max(r.last_event_at for r in members),
                "first_seen": min(r.started_at for r in members),
                "runs": [r.summary() for r in members],
            }
        )
    out.sort(key=lambda g: g["last_seen"], reverse=True)
    del pending
    return JSONResponse(out)
