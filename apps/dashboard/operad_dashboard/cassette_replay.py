"""Cassette discovery and replay helpers for dashboard `/cassettes` routes."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

from .replay import record_to_envelope
from .runs import RunRegistry

_DEFAULT_ROOT = Path("./.cassettes/")


class CassettePathError(ValueError):
    """Raised when a cassette path is outside the configured cassette root."""


def cassette_root_from_env() -> Path:
    configured = Path(os.environ.get("OPERAD_DASHBOARD_CASSETTE_DIR", str(_DEFAULT_ROOT)))
    return configured.expanduser().resolve()


def resolve_cassette_path(root: Path, requested_path: str) -> Path:
    candidate = (root / requested_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise CassettePathError(f"path escapes cassette root: {requested_path}") from exc
    if not candidate.exists() or not candidate.is_file():
        raise CassettePathError(f"cassette not found: {requested_path}")
    return candidate


def discover_cassettes(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for file_path in sorted(root.rglob("*.jsonl")):
        if not file_path.is_file():
            continue
        stat = file_path.stat()
        header = first_json_line(file_path)
        cassette_type = classify_cassette(file_path, header)
        metadata = parse_metadata(cassette_type, header)
        out.append(
            {
                "path": file_path.relative_to(root).as_posix(),
                "type": cassette_type,
                "size": int(stat.st_size),
                "mtime": float(stat.st_mtime),
                "metadata": metadata,
            }
        )
    return out


def first_json_line(path: Path) -> dict[str, Any] | None:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                return None
            if isinstance(value, dict):
                return value
            return None
    return None


def classify_cassette(path: Path, header: dict[str, Any] | None) -> str:
    if path.name.endswith(".train.jsonl"):
        return "training"
    if header is None:
        return "unknown"
    if header.get("event") in {"agent", "algorithm"}:
        return "trace"
    if all(key in header for key in ("hash_model", "hash_prompt", "hash_input", "response_json")):
        return "inference"
    if "step_idx" in header and "epoch" in header:
        return "training"
    return "unknown"


def parse_metadata(cassette_type: str, header: dict[str, Any] | None) -> dict[str, Any]:
    if header is None:
        return {}
    metadata: dict[str, Any] = {}
    if cassette_type == "trace":
        run_id = header.get("run_id")
        algorithm = header.get("algorithm_path")
        if isinstance(run_id, str):
            metadata["run_id"] = run_id
        if isinstance(algorithm, str):
            metadata["algorithm"] = algorithm
    recorded_at = header.get("recorded_at")
    if isinstance(recorded_at, (int, float)):
        metadata["recorded_at"] = float(recorded_at)
    if cassette_type == "training":
        epoch = header.get("epoch")
        step_idx = header.get("step_idx")
        if isinstance(epoch, int):
            metadata["epoch"] = epoch
        if isinstance(step_idx, int):
            metadata["step_idx"] = step_idx
    return metadata


def iter_json_lines(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield value


def parse_issues(path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                issues.append(
                    {
                        "event_index": line_number,
                        "field": "line",
                        "expected": "valid json object",
                        "actual": raw,
                    }
                )
                continue
            if not isinstance(value, dict):
                issues.append(
                    {
                        "event_index": line_number,
                        "field": "line",
                        "expected": "json object",
                        "actual": value,
                    }
                )
    return issues


def _synthetic_timestamp(index: int, *, deterministic: bool, start_ts: float | None = None) -> float:
    if deterministic:
        return float(index) * 0.001
    base = start_ts if start_ts is not None else time.time()
    return base + (float(index) * 0.001)


def replay_run_id(path: Path, run_id_override: str | None = None) -> str:
    if run_id_override:
        return run_id_override
    stem = path.stem.replace(".", "-")
    suffix = uuid.uuid4().hex[:8]
    return f"cassette-{stem}-{suffix}"


def iter_normalized_envelopes(
    path: Path,
    *,
    run_id: str,
    deterministic: bool,
) -> Iterator[dict[str, Any]]:
    start_ts = None if deterministic else time.time()
    event_index = 0
    for record in iter_json_lines(path):
        envelope = _trace_record_to_envelope(record, run_id=run_id)
        if envelope is not None:
            if deterministic:
                envelope = _with_deterministic_times(envelope, event_index)
            elif envelope.get("started_at") is None:
                ts = _synthetic_timestamp(event_index, deterministic=False, start_ts=start_ts)
                envelope["started_at"] = ts
                if envelope.get("finished_at") is None:
                    envelope["finished_at"] = ts
            event_index += 1
            yield envelope
            continue

        for synthesized in _cassette_entry_to_envelopes(
            record,
            run_id=run_id,
            deterministic=deterministic,
            start_index=event_index,
            start_ts=start_ts,
        ):
            yield synthesized
            event_index += 1


def _trace_record_to_envelope(record: dict[str, Any], *, run_id: str) -> dict[str, Any] | None:
    env = record_to_envelope(record)
    if env is None:
        return None
    env["run_id"] = run_id
    return env


def _with_deterministic_times(env: dict[str, Any], index: int) -> dict[str, Any]:
    ts = _synthetic_timestamp(index, deterministic=True)
    out = dict(env)
    out["started_at"] = ts
    if "finished_at" in out:
        out["finished_at"] = ts
    return out


def _cassette_entry_to_envelopes(
    record: dict[str, Any],
    *,
    run_id: str,
    deterministic: bool,
    start_index: int,
    start_ts: float | None,
) -> list[dict[str, Any]]:
    if all(key in record for key in ("hash_model", "hash_prompt", "hash_input", "response_json")):
        return _inference_entry_to_envelopes(
            record,
            run_id=run_id,
            deterministic=deterministic,
            start_index=start_index,
            start_ts=start_ts,
        )
    if "step_idx" in record and "epoch" in record:
        return [
            _training_entry_to_envelope(
                record,
                run_id=run_id,
                deterministic=deterministic,
                index=start_index,
                start_ts=start_ts,
            )
        ]
    return []


def _inference_entry_to_envelopes(
    record: dict[str, Any],
    *,
    run_id: str,
    deterministic: bool,
    start_index: int,
    start_ts: float | None,
) -> list[dict[str, Any]]:
    started_at = _synthetic_timestamp(start_index, deterministic=deterministic, start_ts=start_ts)
    finished_at = _synthetic_timestamp(start_index + 1, deterministic=deterministic, start_ts=start_ts)
    response_json = record.get("response_json")
    response_value: Any
    if isinstance(response_json, str):
        try:
            response_value = json.loads(response_json)
        except json.JSONDecodeError:
            response_value = response_json
    else:
        response_value = response_json

    common_meta = {
        "cassette": {
            "entry_key": record.get("key"),
            "hash_model": record.get("hash_model"),
            "hash_prompt": record.get("hash_prompt"),
            "hash_input": record.get("hash_input"),
        }
    }
    return [
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "CassetteReplay",
            "kind": "start",
            "input": None,
            "output": None,
            "started_at": started_at,
            "finished_at": None,
            "metadata": common_meta,
            "error": None,
        },
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "CassetteReplay",
            "kind": "end",
            "input": None,
            "output": response_value,
            "started_at": started_at,
            "finished_at": finished_at,
            "metadata": common_meta,
            "error": None,
        },
    ]


def _training_entry_to_envelope(
    record: dict[str, Any],
    *,
    run_id: str,
    deterministic: bool,
    index: int,
    start_ts: float | None,
) -> dict[str, Any]:
    ts = _synthetic_timestamp(index, deterministic=deterministic, start_ts=start_ts)
    payload = {
        "phase": "cassette_step",
        "epoch": record.get("epoch"),
        "step_idx": record.get("step_idx"),
        "mean_loss": record.get("mean_loss"),
        "n_samples": record.get("n_samples"),
        "post_step_params": record.get("post_step_params"),
        "hash_agent": record.get("hash_agent"),
        "hash_inputs": record.get("hash_inputs"),
        "hash_params": record.get("hash_params"),
    }
    return {
        "type": "algo_event",
        "run_id": run_id,
        "algorithm_path": "Trainer",
        "kind": "iteration",
        "payload": payload,
        "started_at": ts,
        "finished_at": ts,
        "metadata": {"cassette": {"entry_key": record.get("key")}},
    }


def replay_snapshot(path: Path, *, run_id: str) -> dict[str, Any]:
    registry = RunRegistry()
    for envelope in iter_normalized_envelopes(path, run_id=run_id, deterministic=True):
        registry.record_envelope(envelope)
    info = registry.get(run_id)
    if info is None:
        return {"summary": None, "events": []}
    return {"summary": info.summary(), "events": list(info.events)}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def determinism_diff(path: Path) -> dict[str, Any]:
    issues = parse_issues(path)
    if issues:
        return {"ok": False, "diff": issues[:200]}

    expected = replay_snapshot(path, run_id="determinism-run")
    actual = replay_snapshot(path, run_id="determinism-run")

    diff: list[dict[str, Any]] = []
    if canonical_json(expected) != canonical_json(actual):
        expected_events = expected.get("events") or []
        actual_events = actual.get("events") or []
        max_len = max(len(expected_events), len(actual_events))
        for idx in range(max_len):
            e = expected_events[idx] if idx < len(expected_events) else None
            a = actual_events[idx] if idx < len(actual_events) else None
            if canonical_json(e) == canonical_json(a):
                continue
            diff.extend(_flatten_event_diff(idx, e, a))
        if canonical_json(expected.get("summary")) != canonical_json(actual.get("summary")):
            diff.extend(_flatten_event_diff(-1, expected.get("summary"), actual.get("summary"), prefix="summary"))
    return {"ok": len(diff) == 0, "diff": diff[:200]}


def _flatten_event_diff(
    event_index: int,
    expected: Any,
    actual: Any,
    *,
    prefix: str = "",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        keys = sorted(set(expected.keys()) | set(actual.keys()))
        for key in keys:
            field = f"{prefix}.{key}" if prefix else str(key)
            out.extend(_flatten_event_diff(event_index, expected.get(key), actual.get(key), prefix=field))
        return out
    if isinstance(expected, list) and isinstance(actual, list):
        max_len = max(len(expected), len(actual))
        for idx in range(max_len):
            field = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            left = expected[idx] if idx < len(expected) else None
            right = actual[idx] if idx < len(actual) else None
            out.extend(_flatten_event_diff(event_index, left, right, prefix=field))
        return out

    if canonical_json(expected) != canonical_json(actual):
        out.append(
            {
                "event_index": event_index,
                "field": prefix or "value",
                "expected": expected,
                "actual": actual,
            }
        )
    return out


def preview_envelopes(path: Path, *, run_id: str, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for env in iter_normalized_envelopes(path, run_id=run_id, deterministic=True):
        out.append(env)
        if len(out) >= limit:
            break
    return out
