from __future__ import annotations

"""Record/replay retrieval client cassettes.

Owner: 1-4-retrieval-client.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Literal, TYPE_CHECKING
from uuid import uuid4

from apps_uthereal.retrieval.client import RetrievalClient, RetrievalError
from apps_uthereal.retrieval.keys import metadata_key, retrieve_key

if TYPE_CHECKING:
    from apps_uthereal.schemas.retrieval import (
        RetrievalResult,
        RetrievalSpecification,
    )
    from apps_uthereal.schemas.workflow import WorkspaceMetadata


Mode = Literal["record", "replay", "record-missing"]


class CassetteMiss(RetrievalError):
    """Raised when replay mode cannot find a recorded retrieval entry."""

    def __init__(
        self,
        *,
        kind: Literal["retrieve", "metadata"],
        key: str,
        workspace_id: str,
        path: Path,
        spec: RetrievalSpecification | None = None,
    ) -> None:
        self.kind = kind
        self.key = key
        self.workspace_id = workspace_id
        self.path = path
        super().__init__(
            "cassette_miss",
            spec=spec,
            body=f"{kind} cassette miss for key {key} at {path}",
        )


class CassetteRetrievalClient:
    """Record/replay wrapper around an inner retrieval client.

    Modes:
      "record"          - always call inner and record the result.
      "replay"          - read from disk only; misses raise ``CassetteMiss``.
      "record-missing"  - replay hits, call inner on misses, then record.
    """

    def __init__(
        self,
        *,
        cassette_dir: Path,
        inner: RetrievalClient | None = None,
        mode: Mode = "replay",
    ) -> None:
        if mode not in ("record", "replay", "record-missing"):
            raise ValueError(f"invalid retrieval cassette mode {mode!r}")
        if mode in ("record", "record-missing") and inner is None:
            raise RetrievalError("record_requires_inner")
        self._cassette_dir = cassette_dir
        self._inner = inner
        self._mode = mode

    async def retrieve(
        self,
        spec: RetrievalSpecification,
        *,
        workspace_id: str,
    ) -> RetrievalResult:
        """Retrieve from cassette or inner client according to mode."""
        key = retrieve_key(workspace_id=workspace_id, spec=spec)
        path = self._retrieve_path(key)

        if self._mode in ("replay", "record-missing"):
            entry = await _read_json_or_none(path)
            if entry is not None:
                return _retrieval_result_type().model_validate(entry["result"])
            if self._mode == "replay":
                raise CassetteMiss(
                    kind="retrieve",
                    key=key,
                    workspace_id=workspace_id,
                    path=path,
                    spec=spec,
                )

        result = await self._require_inner().retrieve(
            spec,
            workspace_id=workspace_id,
        )
        await _atomic_write_json(
            path,
            {
                "kind": "retrieve",
                "key": key,
                "workspace_id": workspace_id,
                "spec": spec.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
            },
        )
        return result

    async def get_workspace_metadata(self, workspace_id: str) -> WorkspaceMetadata:
        """Get workspace metadata from cassette or inner client."""
        key = metadata_key(workspace_id=workspace_id)
        path = self._metadata_path(key)

        if self._mode in ("replay", "record-missing"):
            entry = await _read_json_or_none(path)
            if entry is not None:
                return _workspace_metadata_type().model_validate(entry["result"])
            if self._mode == "replay":
                raise CassetteMiss(
                    kind="metadata",
                    key=key,
                    workspace_id=workspace_id,
                    path=path,
                )

        result = await self._require_inner().get_workspace_metadata(workspace_id)
        await _atomic_write_json(
            path,
            {
                "kind": "metadata",
                "key": key,
                "workspace_id": workspace_id,
                "result": result.model_dump(mode="json"),
            },
        )
        return result

    async def aclose(self) -> None:
        """Close the wrapped client when one exists."""
        if self._inner is not None:
            await self._inner.aclose()

    def _retrieve_path(self, key: str) -> Path:
        return self._cassette_dir / "retrieve" / f"{key}.json"

    def _metadata_path(self, key: str) -> Path:
        return self._cassette_dir / "metadata" / f"{key}.json"

    def _require_inner(self) -> RetrievalClient:
        if self._inner is None:
            raise RetrievalError("record_requires_inner")
        return self._inner


def _retrieval_result_type() -> type[Any]:
    from apps_uthereal.schemas.retrieval import RetrievalResult

    return RetrievalResult


def _workspace_metadata_type() -> type[Any]:
    from apps_uthereal.schemas.workflow import WorkspaceMetadata

    return WorkspaceMetadata


def _read_json_sync(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


async def _read_json_or_none(path: Path) -> dict[str, Any] | None:
    try:
        return await asyncio.to_thread(_read_json_sync, path)
    except FileNotFoundError:
        return None


def _write_json_sync(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    os.replace(tmp, path)


async def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    await asyncio.to_thread(_write_json_sync, path, payload)


__all__ = ["CassetteMiss", "CassetteRetrievalClient", "Mode"]
