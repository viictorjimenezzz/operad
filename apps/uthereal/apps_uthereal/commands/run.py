from __future__ import annotations

"""Run one uthereal dataset entry through the Artemis runner.

Owner: 4-1-cli-run-show-feedback.
"""

import argparse
import json
import os
import sys
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator, Literal

import httpx
from pydantic import ValidationError

from operad.utils.cassette import CassetteMiss, cassette_context

from apps_uthereal.paths import run_dir
from apps_uthereal.retrieval.client import RetrievalClient, RetrievalError
from apps_uthereal.schemas.retrieval import RetrievalResult, RetrievalSpecification
from apps_uthereal.schemas.workflow import (
    ArtemisInput,
    DatasetEntry,
    WorkspaceMetadata,
)
from apps_uthereal.workflow.runner import ArtemisRunner


CassetteMode = Literal["record", "replay", "record-missing"]
_CASSETTE_MODES: tuple[CassetteMode, ...] = (
    "record",
    "replay",
    "record-missing",
)
_DEFAULT_SELFSERVE_ROOT = (
    Path.home()
    / "Documents"
    / "uthereal"
    / "uthereal-src"
    / "uthereal_workflow"
    / "agentic_workflows"
    / "chat"
    / "selfserve"
)


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``run`` subcommand parser."""

    parser = subparsers.add_parser("run")
    parser.add_argument("--entry", type=Path, required=True)
    parser.add_argument(
        "--selfserve-root",
        type=Path,
        default=None,
        help=(
            "Path to uthereal selfserve YAMLs. Defaults to "
            "$UTHEREAL_SELFSERVE_ROOT, then ~/Documents/uthereal/.../selfserve."
        ),
    )
    parser.add_argument(
        "--rag-base-url",
        default=None,
        help="RAG service URL. Defaults to $UTHEREAL_RAG_URL when set.",
    )
    parser.add_argument(
        "--cassette-mode",
        choices=_CASSETTE_MODES,
        default="record-missing",
    )
    parser.set_defaults(func=run)


async def run(args: argparse.Namespace) -> int:
    """Execute one dataset entry and write run artifacts."""

    entry_path = Path(args.entry)
    if not entry_path.exists():
        print(f"entry not found: {entry_path}", file=sys.stderr)
        return 2

    selfserve_root = _resolve_selfserve_root(args.selfserve_root)
    if selfserve_root is None:
        print("selfserve root not found; pass --selfserve-root", file=sys.stderr)
        return 2

    try:
        raw_entry = json.loads(entry_path.read_text(encoding="utf-8"))
        if not isinstance(raw_entry, dict):
            print("entry JSON must be an object", file=sys.stderr)
            return 2
        entry = DatasetEntry.model_validate(raw_entry)
        workspace = _workspace_from_entry(raw_entry, entry)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    current_run_dir = run_dir(entry.entry_id or entry.compute_entry_id())
    _write_json(current_run_dir / "entry.json", entry.model_dump(mode="json"))
    cassette_root = current_run_dir / "cassettes"
    llm_dir = cassette_root / "llm"
    rag_dir = cassette_root / "rag"
    llm_dir.mkdir(parents=True, exist_ok=True)
    rag_dir.mkdir(parents=True, exist_ok=True)

    rag_base_url = args.rag_base_url or os.environ.get("UTHEREAL_RAG_URL")
    live_rag = LiveRetrievalClient(rag_base_url) if rag_base_url else None
    retrieval = CassetteRetrievalClient(
        cassette_dir=rag_dir,
        inner=live_rag,
        mode=args.cassette_mode,
    )
    runner = ArtemisRunner(selfserve_root=selfserve_root, retrieval=retrieval)

    # If the entry didn't ship a `workspace` block and we have a path to fetch one
    # (live RAG service or a previously-recorded cassette), pull rules + tags now
    # so the rule_classifier and retrieval_orchestrator see them. Falls back to
    # the stub workspace silently when no metadata is reachable (e.g. hermetic
    # DIRECT_ANSWER demo without --rag-base-url).
    if not _entry_has_workspace_block(raw_entry) and entry.id_tenant and entry.workspace_id:
        try:
            fetched = await retrieval.get_workspace_metadata(
                id_tenant=entry.id_tenant,
                id_workspace=entry.workspace_id,
                id_assistant=entry.id_assistant,
            )
            workspace = _merge_workspace(fetched, workspace)
        except RetrievalError:
            pass
    artemis_input = ArtemisInput(entry=entry, workspace=workspace)
    llm_mode = (
        "record" if args.cassette_mode in {"record", "record-missing"} else "replay"
    )

    try:
        with _cassette_env(llm_dir, llm_mode):
            with cassette_context(llm_dir / "calls.jsonl", mode=llm_mode):
                await runner.abuild()
                answer, trace = await runner.run_with_trace(artemis_input)
    except (CassetteMiss, RetrievalError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    trace.to_jsonl(current_run_dir / "trace.jsonl")
    (current_run_dir / "answer.txt").write_text(
        answer.utterance + "\n",
        encoding="utf-8",
    )
    print(
        f"entry_id={trace.entry_id} trace_id={trace.trace_id} "
        f"answer={current_run_dir / 'answer.txt'}"
    )
    return 0


class LiveRetrievalClient:
    """HTTP-backed retrieval client used only when ``--rag-base-url`` is set.

    Talks to uthereal's `/retrieve` API:
        POST /retrieve/{id_tenant}/{id_workspace}      -> one retrieval result
        GET  /retrieve/{id_tenant}/{id_workspace}/metadata?id_assistant=...

    Auth follows the standard uthereal-apps convention: the ``X-API-Key``
    header is set from ``UTHEREAL_API_KEY`` (which is ``test-api-key`` in
    the canonical local-dev env). The composite auth path on the server
    accepts an API key alone and returns the local sentinel JwtContext
    (see ``uthereal_apps.api.auth.composite.do_validate_auth``).

    A bearer JWT may also be passed explicitly via ``api_key`` -- but
    for local dev no extra config is needed beyond exporting
    ``UTHEREAL_API_KEY`` (and the rest of ``env_local_dev.sh``).
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        resolved_key = api_key if api_key is not None else os.environ.get("UTHEREAL_API_KEY")
        self._headers: dict[str, str] = {}
        if resolved_key:
            self._headers["X-API-Key"] = resolved_key
        self._timeout = timeout

    async def retrieve(
        self,
        spec: RetrievalSpecification,
        *,
        id_tenant: str,
        id_workspace: str,
        id_assistant: str,
    ) -> RetrievalResult:
        """Retrieve one specification from the live RAG service."""

        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=self._timeout,
        ) as client:
            response = await client.post(
                f"/retrieve/{id_tenant}/{id_workspace}",
                json={
                    "id_assistant": id_assistant,
                    "spec": spec.model_dump(mode="json", by_alias=True),
                },
            )
        if response.status_code >= 400:
            raise RetrievalError(spec, response.status_code, response.text)
        body = response.json()
        result_payload = body.get("result", body)
        return RetrievalResult.model_validate(result_payload)

    async def get_workspace_metadata(
        self,
        *,
        id_tenant: str,
        id_workspace: str,
        id_assistant: str,
    ) -> WorkspaceMetadata:
        """Load workspace metadata from the live RAG service."""

        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=self._timeout,
        ) as client:
            response = await client.get(
                f"/retrieve/{id_tenant}/{id_workspace}/metadata",
                params={"id_assistant": id_assistant},
            )
        if response.status_code >= 400:
            raise RetrievalError(
                RetrievalSpecification(
                    spec_id="workspace_metadata",
                    intent=f"{id_tenant}/{id_workspace}",
                ),
                response.status_code,
                response.text,
            )
        return WorkspaceMetadata.model_validate(response.json())


class CassetteRetrievalClient:
    """Record/replay wrapper for retrieval calls."""

    def __init__(
        self,
        *,
        cassette_dir: Path,
        inner: RetrievalClient | None,
        mode: CassetteMode,
    ) -> None:
        self.cassette_dir = cassette_dir
        self.inner = inner
        self.mode = mode

    async def retrieve(
        self,
        spec: RetrievalSpecification,
        *,
        id_tenant: str,
        id_workspace: str,
        id_assistant: str,
    ) -> RetrievalResult:
        """Replay or record one retrieval result."""

        path = self.cassette_dir / f"{_retrieval_key(id_tenant, id_workspace, id_assistant, spec)}.json"
        if path.exists():
            return RetrievalResult.model_validate_json(path.read_text(encoding="utf-8"))
        if self.mode == "replay" or self.inner is None:
            raise RetrievalError(spec, 404, f"retrieval cassette miss: {path}")
        result = await self.inner.retrieve(
            spec,
            id_tenant=id_tenant,
            id_workspace=id_workspace,
            id_assistant=id_assistant,
        )
        _write_json(path, result.model_dump(mode="json", by_alias=True))
        return result

    async def get_workspace_metadata(
        self,
        *,
        id_tenant: str,
        id_workspace: str,
        id_assistant: str,
    ) -> WorkspaceMetadata:
        """Replay or record workspace metadata."""

        spec = RetrievalSpecification(
            spec_id="workspace_metadata",
            intent=f"{id_tenant}/{id_workspace}",
        )
        key = _hash_text(f"{id_tenant}|{id_workspace}|{id_assistant}")
        path = self.cassette_dir / f"metadata-{key}.json"
        if path.exists():
            return WorkspaceMetadata.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        if self.mode == "replay" or self.inner is None:
            raise RetrievalError(spec, 404, f"metadata cassette miss: {path}")
        metadata = await self.inner.get_workspace_metadata(
            id_tenant=id_tenant,
            id_workspace=id_workspace,
            id_assistant=id_assistant,
        )
        _write_json(path, metadata.model_dump(mode="json"))
        return metadata


def _entry_has_workspace_block(raw_entry: dict[str, Any]) -> bool:
    return isinstance(raw_entry.get("workspace"), dict)


def _merge_workspace(
    fetched: WorkspaceMetadata,
    fallback: WorkspaceMetadata,
) -> WorkspaceMetadata:
    """Use ``fetched`` as the base; fill missing ids from ``fallback``."""

    update: dict[str, Any] = {}
    if not fetched.workspace_id and fallback.workspace_id:
        update["workspace_id"] = fallback.workspace_id
    if not fetched.id_tenant and fallback.id_tenant:
        update["id_tenant"] = fallback.id_tenant
    if not fetched.id_assistant and fallback.id_assistant:
        update["id_assistant"] = fallback.id_assistant
    if update:
        return fetched.model_copy(update=update)
    return fetched


def _workspace_from_entry(
    raw_entry: dict[str, Any],
    entry: DatasetEntry,
) -> WorkspaceMetadata:
    workspace_payload = raw_entry.get("workspace")
    if isinstance(workspace_payload, dict):
        payload = dict(workspace_payload)
        payload.setdefault("workspace_id", entry.workspace_id)
        payload.setdefault("id_tenant", entry.id_tenant)
        payload.setdefault("id_assistant", entry.id_assistant)
        return WorkspaceMetadata.model_validate(payload)
    return WorkspaceMetadata(
        workspace_id=entry.workspace_id,
        id_tenant=entry.id_tenant,
        id_assistant=entry.id_assistant,
    )


def _resolve_selfserve_root(raw_path: Path | None) -> Path | None:
    configured = (
        raw_path or _env_path("UTHEREAL_SELFSERVE_ROOT") or _DEFAULT_SELFSERVE_ROOT
    )
    path = configured.expanduser().resolve()
    if not path.exists():
        return None
    return path


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


@contextmanager
def _cassette_env(path: Path, mode: Literal["record", "replay"]) -> Iterator[None]:
    previous_path = os.environ.get("OPERAD_CASSETTE_PATH")
    previous_mode = os.environ.get("OPERAD_CASSETTE")
    os.environ["OPERAD_CASSETTE_PATH"] = str(path)
    os.environ["OPERAD_CASSETTE"] = mode
    try:
        yield
    finally:
        _restore_env("OPERAD_CASSETTE_PATH", previous_path)
        _restore_env("OPERAD_CASSETTE", previous_mode)


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
        return
    os.environ[name] = value


def _retrieval_key(
    id_tenant: str,
    id_workspace: str,
    id_assistant: str,
    spec: RetrievalSpecification,
) -> str:
    spec_json = _canonical_json(spec.model_dump(mode="json", by_alias=True))
    payload = f"{id_tenant}|{id_workspace}|{id_assistant}|{spec_json}"
    return _hash_text(payload)


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:16]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json_pretty(value), encoding="utf-8")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _canonical_json_pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
