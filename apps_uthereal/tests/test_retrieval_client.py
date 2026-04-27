from __future__ import annotations

"""Tests for the uthereal retrieval client slice.

Owner: 1-4-retrieval-client.
"""

import asyncio
import json
import sys
import types
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field

from apps_uthereal.retrieval import cassette as cassette_module
from apps_uthereal.retrieval.cassette import CassetteMiss, CassetteRetrievalClient
from apps_uthereal.retrieval.client import LiveRetrievalClient, RetrievalError
from apps_uthereal.retrieval.keys import retrieve_key


class RetrievalSpecification(BaseModel):
    """Test copy of the vendored retrieval specification contract."""

    spec_id: str
    intent: str
    satisfaction_criteria: list[str]
    metadata_filter: dict[str, Any] = Field(default_factory=dict, alias="filter")

    model_config = ConfigDict(populate_by_name=True)


class RetrievalResult(RetrievalSpecification):
    """Test copy of the vendored retrieval result contract."""

    text_rag_results: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    image_rag_results: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class WorkspaceMetadata(BaseModel):
    """Small metadata model for client tests."""

    workspace_id: str
    title: str
    rules: list[str] = Field(default_factory=list)


@pytest.fixture(autouse=True)
def schema_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install schema modules until the parallel vendored-schema task lands."""
    schema_pkg = types.ModuleType("apps_uthereal.schemas")
    schema_pkg.__path__ = []

    retrieval = types.ModuleType("apps_uthereal.schemas.retrieval")
    retrieval.RetrievalSpecification = RetrievalSpecification
    retrieval.RetrievalResult = RetrievalResult

    workflow = types.ModuleType("apps_uthereal.schemas.workflow")
    workflow.WorkspaceMetadata = WorkspaceMetadata

    monkeypatch.setitem(sys.modules, "apps_uthereal.schemas", schema_pkg)
    monkeypatch.setitem(sys.modules, "apps_uthereal.schemas.retrieval", retrieval)
    monkeypatch.setitem(sys.modules, "apps_uthereal.schemas.workflow", workflow)


def _spec(spec_id: str = "known") -> RetrievalSpecification:
    return RetrievalSpecification(
        spec_id=spec_id,
        intent="implant protocol",
        satisfaction_criteria=["source-backed answer"],
        filter={"tag": "guide"},
    )


def _result(spec: RetrievalSpecification, marker: str = "ok") -> RetrievalResult:
    return RetrievalResult(
        **spec.model_dump(mode="json"),
        text_rag_results={"doc": [{"id": marker, "text": "retrieved text"}]},
        image_rag_results={},
    )


def _metadata(workspace_id: str = "workspace") -> WorkspaceMetadata:
    return WorkspaceMetadata(workspace_id=workspace_id, title="Workspace", rules=["default"])


def _install_http_client(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[str, str, dict[str, Any] | None], Any],
) -> list[Any]:
    instances: list[Any] = []

    class FakeAsyncClient:
        def __init__(
            self,
            *,
            timeout: float,
            headers: dict[str, str] | None = None,
        ) -> None:
            self.timeout = timeout
            self.headers = headers
            self.closed = False
            instances.append(self)

        async def post(self, url: str, *, json: dict[str, Any]) -> httpx.Response:
            return await handler("POST", url, json)

        async def get(self, url: str) -> httpx.Response:
            return await handler("GET", url, None)

        async def aclose(self) -> None:
            self.closed = True

    monkeypatch.setattr(
        "apps_uthereal.retrieval.client.httpx.AsyncClient",
        FakeAsyncClient,
    )
    return instances


def test_client_module_exports_cassette_client() -> None:
    from apps_uthereal.retrieval.client import CassetteRetrievalClient as Exported

    assert Exported is CassetteRetrievalClient


class RecordingInner:
    """In-memory retrieval client used by cassette tests."""

    def __init__(self) -> None:
        self.retrieve_calls: list[tuple[str, RetrievalSpecification]] = []
        self.metadata_calls: list[str] = []
        self.closed = False

    async def retrieve(
        self,
        spec: RetrievalSpecification,
        *,
        workspace_id: str,
    ) -> RetrievalResult:
        self.retrieve_calls.append((workspace_id, spec))
        await asyncio.sleep(0)
        return _result(spec, marker=spec.spec_id)

    async def get_workspace_metadata(self, workspace_id: str) -> WorkspaceMetadata:
        self.metadata_calls.append(workspace_id)
        await asyncio.sleep(0)
        return _metadata(workspace_id)

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_live_client_retrieve_calls_correct_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}
    spec = _spec()

    async def handler(
        method: str,
        url: str,
        body: dict[str, Any] | None,
    ) -> httpx.Response:
        seen.update(method=method, url=url, body=body)
        request = httpx.Request(method, url)
        return httpx.Response(200, json=_result(spec).model_dump(mode="json"), request=request)

    instances = _install_http_client(monkeypatch, handler)
    client = LiveRetrievalClient(
        "https://rag.example.test/",
        timeout_s=12.0,
        headers={"X-Test": "yes"},
    )

    result = await client.retrieve(spec, workspace_id="workspace-1")

    assert result.text_rag_results["doc"][0]["id"] == "ok"
    assert seen["method"] == "POST"
    assert seen["url"] == "https://rag.example.test/retrieve"
    assert seen["body"] == {
        "workspace_id": "workspace-1",
        "spec": spec.model_dump(mode="json"),
    }
    assert instances[0].timeout == 12.0
    assert instances[0].headers == {"X-Test": "yes"}


@pytest.mark.asyncio
async def test_live_client_get_metadata_calls_correct_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def handler(
        method: str,
        url: str,
        body: dict[str, Any] | None,
    ) -> httpx.Response:
        seen.update(method=method, url=url, body=body)
        request = httpx.Request(method, url)
        return httpx.Response(
            200,
            json=_metadata("workspace-1").model_dump(mode="json"),
            request=request,
        )

    _install_http_client(monkeypatch, handler)
    client = LiveRetrievalClient("https://rag.example.test")

    metadata = await client.get_workspace_metadata("workspace-1")

    assert metadata.workspace_id == "workspace-1"
    assert seen == {
        "method": "GET",
        "url": "https://rag.example.test/workspaces/workspace-1/metadata",
        "body": None,
    }


@pytest.mark.asyncio
async def test_live_client_wraps_http_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(
        method: str,
        url: str,
        body: dict[str, Any] | None,
    ) -> httpx.Response:
        request = httpx.Request(method, url)
        return httpx.Response(500, text="backend failed", request=request)

    _install_http_client(monkeypatch, handler)
    client = LiveRetrievalClient("https://rag.example.test")

    with pytest.raises(RetrievalError) as excinfo:
        await client.retrieve(_spec(), workspace_id="workspace-1")

    assert excinfo.value.reason == "http_status"
    assert excinfo.value.status == 500
    assert excinfo.value.body == "backend failed"


@pytest.mark.asyncio
async def test_live_client_wraps_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(
        method: str,
        url: str,
        body: dict[str, Any] | None,
    ) -> httpx.Response:
        raise httpx.TimeoutException("too slow")

    _install_http_client(monkeypatch, handler)
    client = LiveRetrievalClient("https://rag.example.test")

    with pytest.raises(RetrievalError) as excinfo:
        await client.retrieve(_spec(), workspace_id="workspace-1")

    assert excinfo.value.reason == "timeout"


@pytest.mark.asyncio
async def test_cassette_replay_returns_recorded_result() -> None:
    cassette_dir = Path(__file__).parent / "fixtures" / "retrieval_cassette"
    client = CassetteRetrievalClient(cassette_dir=cassette_dir, mode="replay")

    result = await client.retrieve(_spec(), workspace_id="workspace-fixture")

    assert result.spec_id == "known"
    assert result.text_rag_results["doc"][0]["text"] == "fixture text"


@pytest.mark.asyncio
async def test_cassette_replay_misses_raise_CassetteMiss(tmp_path: Path) -> None:
    client = CassetteRetrievalClient(cassette_dir=tmp_path, mode="replay")

    with pytest.raises(CassetteMiss) as excinfo:
        await client.retrieve(_spec("missing"), workspace_id="workspace-1")

    assert excinfo.value.reason == "cassette_miss"
    assert excinfo.value.kind == "retrieve"
    assert excinfo.value.key == retrieve_key(workspace_id="workspace-1", spec=_spec("missing"))


@pytest.mark.asyncio
async def test_cassette_record_writes_file_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, Path]] = []
    original_replace = cassette_module.os.replace

    def replace_spy(src: str | Path, dst: str | Path) -> None:
        calls.append((Path(src), Path(dst)))
        original_replace(src, dst)

    monkeypatch.setattr(cassette_module.os, "replace", replace_spy)
    spec = _spec("recorded")
    inner = RecordingInner()
    client = CassetteRetrievalClient(cassette_dir=tmp_path, inner=inner, mode="record")

    result = await client.retrieve(spec, workspace_id="workspace-1")

    key = retrieve_key(workspace_id="workspace-1", spec=spec)
    path = tmp_path / "retrieve" / f"{key}.json"
    payload = json.loads(path.read_text())
    assert result.spec_id == "recorded"
    assert payload["key"] == key
    assert payload["kind"] == "retrieve"
    assert calls and calls[0][1] == path
    assert calls[0][0].name.startswith(f".{path.name}.")


@pytest.mark.asyncio
async def test_cassette_record_missing_falls_back_then_records(tmp_path: Path) -> None:
    hit_spec = _spec("hit")
    hit_key = retrieve_key(workspace_id="workspace-1", spec=hit_spec)
    hit_path = tmp_path / "retrieve" / f"{hit_key}.json"
    hit_path.parent.mkdir(parents=True)
    hit_path.write_text(
        json.dumps(
            {
                "kind": "retrieve",
                "key": hit_key,
                "workspace_id": "workspace-1",
                "spec": hit_spec.model_dump(mode="json"),
                "result": _result(hit_spec, marker="cached").model_dump(mode="json"),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    inner = RecordingInner()
    client = CassetteRetrievalClient(
        cassette_dir=tmp_path,
        inner=inner,
        mode="record-missing",
    )

    cached = await client.retrieve(hit_spec, workspace_id="workspace-1")
    missed = await client.retrieve(_spec("miss"), workspace_id="workspace-1")

    assert cached.text_rag_results["doc"][0]["id"] == "cached"
    assert missed.text_rag_results["doc"][0]["id"] == "miss"
    assert [call[1].spec_id for call in inner.retrieve_calls] == ["miss"]
    miss_key = retrieve_key(workspace_id="workspace-1", spec=_spec("miss"))
    assert (tmp_path / "retrieve" / f"{miss_key}.json").exists()


def test_retrieve_key_stable_under_field_reorder() -> None:
    spec_a = RetrievalSpecification.model_validate(
        {
            "spec_id": "stable",
            "intent": "find facts",
            "satisfaction_criteria": ["complete"],
            "filter": {"b": 2, "a": 1},
        }
    )
    spec_b = RetrievalSpecification.model_validate(
        {
            "filter": {"a": 1, "b": 2},
            "satisfaction_criteria": ["complete"],
            "intent": "find facts",
            "spec_id": "stable",
        }
    )

    assert retrieve_key(workspace_id="w", spec=spec_a) == retrieve_key(
        workspace_id="w",
        spec=spec_b,
    )


@pytest.mark.asyncio
async def test_concurrent_record_writes_dont_corrupt(tmp_path: Path) -> None:
    inner = RecordingInner()
    client = CassetteRetrievalClient(cassette_dir=tmp_path, inner=inner, mode="record")
    specs = [_spec(f"spec-{idx}") for idx in range(8)]

    await asyncio.gather(
        *(client.retrieve(spec, workspace_id="workspace-1") for spec in specs)
    )

    for spec in specs:
        key = retrieve_key(workspace_id="workspace-1", spec=spec)
        path = tmp_path / "retrieve" / f"{key}.json"
        payload = json.loads(path.read_text())
        assert payload["key"] == key
        assert payload["result"]["spec_id"] == spec.spec_id


@pytest.mark.asyncio
async def test_aclose_closes_underlying_httpx_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(
        method: str,
        url: str,
        body: dict[str, Any] | None,
    ) -> httpx.Response:
        request = httpx.Request(method, url)
        return httpx.Response(200, json={}, request=request)

    instances = _install_http_client(monkeypatch, handler)
    client = LiveRetrievalClient("https://rag.example.test")

    await client.aclose()

    assert instances[0].closed is True


@pytest.mark.asyncio
async def test_cassette_aclose_closes_inner(tmp_path: Path) -> None:
    inner = RecordingInner()
    client = CassetteRetrievalClient(cassette_dir=tmp_path, inner=inner, mode="record")

    await client.aclose()

    assert inner.closed is True
