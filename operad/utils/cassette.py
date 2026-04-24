"""VCR-style record/replay for default-leaf LLM calls.

Tests that opt in (via the ``cassette`` pytest fixture) run inside a
context that monkeypatches :meth:`operad.core.agent.Agent.forward`. The
wrapper computes a deterministic key from the rendered prompt,
configuration, and input; on replay it returns a deserialised response
from a JSONL cassette file, on record it calls the real forward and
appends the result.

Only default-forward leaves are affected. Composites override
``forward`` and therefore bypass the wrapper entirely. FakeLeaf
subclasses are likewise unaffected.

Storage is JSONL (one entry per line) keyed by the full triple of
hashes; the ``key`` column is the sha256 of those three concatenated,
truncated to 16 hex characters. The rendered system/user prompt and
input payload are deliberately **not** stored — only their hashes — so
cassette files are safe to commit regardless of prompt content.
"""

from __future__ import annotations

import hashlib
import json
import time
from contextlib import contextmanager
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
        system = self.format_system_message()
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


__all__ = ["CassetteMiss", "cassette_context", "Mode"]
