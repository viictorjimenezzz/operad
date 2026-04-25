"""VCR-style record/replay for default-leaf LLM calls and training runs.

Inference cassette (``cassette_context``): monkeypatches
:meth:`operad.core.agent.Agent.forward` so that LLM calls are replayed
from a JSONL file keyed by prompt + config + input hashes.

Training cassette (``training_cassette_context``): records/replays the
net effect of each optimizer step — per-step mean loss, post-step
parameter values, and LR scheduler state — stored in a sibling
``<name>.train.jsonl`` file. In replay mode the trainer skips every LLM
call inside ``_run_batch`` and ``optimizer.step()`` and restores the
recorded state directly, yielding a byte-equal ``TrainingReport``.

Both cassette files store only hashes (never prompt text or credentials)
and are safe to commit.
"""

from __future__ import annotations

import hashlib
import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Literal

from pydantic import BaseModel

from ..core.agent import Agent
from .hashing import hash_input, hash_model, hash_prompt

Mode = Literal["record", "replay"]


class CassetteMiss(KeyError):
    """Raised in replay mode when the requested key is not in the cassette.

    Carries structured per-segment match counts so callers can tell which
    hash segment drifted (prompt, input, or config) and act accordingly.
    """

    def __init__(
        self,
        key: str,
        *,
        hash_model: str,
        hash_prompt: str,
        hash_input: str,
        matches: dict[str, int],
        path: Path,
    ) -> None:
        self.key = key
        self.hash_model = hash_model
        self.hash_prompt = hash_prompt
        self.hash_input = hash_input
        self.matches = matches
        self.path = path
        super().__init__(str(self))

    def _cause(self) -> str:
        m = self.matches
        drifted = [k for k, v in m.items() if v == 0]
        if m["hash_model"] == 0 and m["hash_prompt"] == 0 and m["hash_input"] == 0:
            return "Cassette is empty; record first"
        if len(drifted) >= 2:
            return "multiple segments drifted; review each"
        if drifted == ["hash_prompt"]:
            return "prompt drift"
        if drifted == ["hash_input"]:
            return "input drift"
        if drifted == ["hash_model"]:
            return "config drift"
        return "unknown"

    def __str__(self) -> str:
        def _mark(name: str, h: str) -> str:
            n = self.matches[name]
            if n > 0:
                suffix = f"(✓ {n} {'entry matches' if n == 1 else 'entries match'})"
            else:
                suffix = "(✗ not in cassette)"
            return f"  {name:<11} = {h}   {suffix}"

        lines = [
            f"CassetteMiss: no cassette entry for key {self.key}",
            _mark("hash_model", self.hash_model),
            _mark("hash_prompt", self.hash_prompt),
            _mark("hash_input", self.hash_input),
            "",
            f"Most likely: {self._cause()}. If intentional, re-record with",
            f"  OPERAD_CASSETTE=record uv run pytest {self.path} -v",
            f"(at {self.path})",
        ]
        return "\n".join(lines)


def _compose_key(h_model: str, h_prompt: str, h_input: str) -> str:
    return hashlib.sha256(
        f"{h_model}|{h_prompt}|{h_input}".encode("utf-8")
    ).hexdigest()[:16]


def _miss_diff(
    entries: dict[str, dict[str, Any]],
    *,
    h_m: str,
    h_p: str,
    h_i: str,
) -> dict[str, int]:
    by_model = sum(1 for e in entries.values() if e.get("hash_model") == h_m)
    by_prompt = sum(1 for e in entries.values() if e.get("hash_prompt") == h_p)
    by_input = sum(1 for e in entries.values() if e.get("hash_input") == h_i)
    return {"hash_model": by_model, "hash_prompt": by_prompt, "hash_input": by_input}


def _load(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        out[entry["key"]] = entry
    return out


def _append(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


@contextmanager
def cassette_context(path: Path, mode: Mode = "replay") -> Iterator[None]:
    """Patch ``Agent.forward`` for the duration of the context.

    On ``replay`` (default), unknown keys raise :class:`CassetteMiss`. On
    ``record`` the original forward executes, the result is serialised
    to JSON, and a new JSONL line is appended to ``path``.
    """
    if mode not in ("record", "replay"):
        raise ValueError(f"invalid cassette mode {mode!r}")

    entries = _load(path)
    original = Agent.forward

    async def wrapper(self: Agent[Any, Any], x: BaseModel) -> BaseModel:
        if self.config is None:
            raise RuntimeError(
                "cassette wrapper requires self.config; default-leaf "
                "agents must be constructed with a Configuration"
            )
        system = self._compose_system_for_call(x)
        user = self.format_user_message(x)
        h_m = hash_model(self.config)
        h_p = hash_prompt(system, user)
        h_i = hash_input(x)
        key = _compose_key(h_m, h_p, h_i)

        hit = entries.get(key)
        if hit is not None:
            return self.output.model_validate_json(hit["response_json"])  # type: ignore[union-attr,return-value]

        if mode == "replay":
            matches = _miss_diff(entries, h_m=h_m, h_p=h_p, h_i=h_i)
            raise CassetteMiss(
                key,
                hash_model=h_m,
                hash_prompt=h_p,
                hash_input=h_i,
                matches=matches,
                path=path,
            )

        # record mode
        result = await original(self, x)
        response_json = result.model_dump_json()
        entry = {
            "key": key,
            "hash_model": h_m,
            "hash_prompt": h_p,
            "hash_input": h_i,
            "response_json": response_json,
            "recorded_at": time.time(),
        }
        entries[key] = entry
        _append(path, entry)
        return result

    Agent.forward = wrapper  # type: ignore[method-assign]
    try:
        yield
    finally:
        Agent.forward = original  # type: ignore[method-assign]



# ---------------------------------------------------------------------------
# Training cassette
# ---------------------------------------------------------------------------


class TrainCassetteMiss(KeyError):
    """Raised in replay mode when a training-step key is absent.

    Carries the hash segments so callers know which part of the agent or
    data caused the miss.
    """

    def __init__(
        self,
        key: str,
        *,
        epoch: int,
        step_idx: int,
        hash_agent: str,
        hash_inputs: str,
        hash_params: str,
        path: Path,
    ) -> None:
        self.key = key
        self.epoch = epoch
        self.step_idx = step_idx
        self.hash_agent = hash_agent
        self.hash_inputs = hash_inputs
        self.hash_params = hash_params
        self.path = path
        super().__init__(str(self))

    def _cause(self, entries: dict[str, dict[str, Any]]) -> str:
        by_agent = sum(1 for e in entries.values() if e.get("hash_agent") == self.hash_agent)
        by_inputs = sum(1 for e in entries.values() if e.get("hash_inputs") == self.hash_inputs)
        by_params = sum(1 for e in entries.values() if e.get("hash_params") == self.hash_params)
        if not entries:
            return "cassette is empty; record first"
        missing = [name for name, cnt in (
            ("hash_agent", by_agent),
            ("hash_inputs", by_inputs),
            ("hash_params", by_params),
        ) if cnt == 0]
        if len(missing) >= 2:
            return f"multiple segments drifted: {', '.join(missing)}"
        if missing == ["hash_agent"]:
            return "hash_agent drift (agent prompt changed)"
        if missing == ["hash_inputs"]:
            return "hash_inputs drift (input data changed)"
        if missing == ["hash_params"]:
            return "hash_params drift (parameter values changed)"
        return "unknown"

    def __str__(self) -> str:
        lines = [
            f"TrainCassetteMiss: no training cassette entry for key {self.key}",
            f"  epoch={self.epoch}  step_idx={self.step_idx}",
            f"  hash_agent  = {self.hash_agent}",
            f"  hash_inputs = {self.hash_inputs}",
            f"  hash_params = {self.hash_params}",
            f"(at {self.path})",
        ]
        return "\n".join(lines)


@dataclass
class _TrainCtx:
    path: Path
    mode: Mode
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)


_TRAIN_CTX: ContextVar[_TrainCtx | None] = ContextVar("_TRAIN_CTX", default=None)


def get_train_ctx() -> _TrainCtx | None:
    """Return the active training cassette context, or ``None``."""
    return _TRAIN_CTX.get()


def _compose_train_key(
    epoch: int,
    step_idx: int,
    hash_agent: str,
    hash_inputs: str,
    hash_params: str,
) -> str:
    raw = f"train|{epoch}|{step_idx}|{hash_agent}|{hash_inputs}|{hash_params}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _hash_train_inputs(inputs: list[BaseModel]) -> str:
    combined = "|".join(m.model_dump_json() for m in inputs)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def _hash_train_params(params: list[Any]) -> str:
    # params is list[Parameter]; avoid importing here to prevent circular deps
    snap = {p.path: json.dumps(p.value, default=str, sort_keys=True) for p in params}
    combined = json.dumps(snap, sort_keys=True)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def _append_train(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def record_train_step(
    ctx: _TrainCtx,
    *,
    key: str,
    hash_agent: str,
    hash_inputs: str,
    hash_params: str,
    epoch: int,
    step_idx: int,
    mean_loss: float,
    n_samples: int,
    post_step_params: dict[str, Any],
    lr_state: dict[str, Any] | None,
) -> None:
    """Append a training-step entry to the cassette and update in-memory index."""
    entry: dict[str, Any] = {
        "epoch": epoch,
        "hash_agent": hash_agent,
        "hash_inputs": hash_inputs,
        "hash_params": hash_params,
        "key": key,
        "lr_state_json": json.dumps(lr_state, sort_keys=True) if lr_state is not None else None,
        "mean_loss": mean_loss,
        "n_samples": n_samples,
        "post_step_params": post_step_params,
        "recorded_at": time.time(),
        "step_idx": step_idx,
    }
    ctx.entries[key] = entry
    _append_train(ctx.path, entry)


@contextmanager
def training_cassette_context(path: Path | str, mode: Mode = "replay") -> Iterator[None]:
    """Activate a training cassette for the duration of the context.

    ``path`` is coerced to ``<stem>.train.jsonl``. In ``replay`` mode the
    existing file is loaded into memory; unknown keys raise
    :class:`TrainCassetteMiss`. In ``record`` mode entries are appended to
    the file as the training loop runs.
    """
    if mode not in ("record", "replay"):
        raise ValueError(f"invalid cassette mode {mode!r}")
    p = Path(path).with_suffix(".train.jsonl")
    entries = _load(p) if mode == "replay" and p.exists() else {}
    ctx = _TrainCtx(path=p, mode=mode, entries=entries)
    token = _TRAIN_CTX.set(ctx)
    try:
        yield
    finally:
        _TRAIN_CTX.reset(token)


__all__ = [
    "CassetteMiss",
    "Mode",
    "TrainCassetteMiss",
    "cassette_context",
    "get_train_ctx",
    "record_train_step",
    "training_cassette_context",
    "_hash_train_inputs",
    "_hash_train_params",
    "_compose_train_key",
]
