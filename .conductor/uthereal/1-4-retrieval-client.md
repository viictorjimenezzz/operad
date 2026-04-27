# 1-4 — RetrievalClient (Protocol + Live + Cassette)

**Batch:** 1 · **Parallelizable with:** 1-1, 1-2, 1-3, 1-5 · **Depends on:** —

You are abstracting the RAG service behind a Protocol. Three
implementations are required: Live (HTTP to the user's container),
Cassette (record/replay over Live or standalone), and a tiny
test-server fixture for hermetic tests.

## Goal

Provide a single `RetrievalClient` Protocol with three implementations,
plus a recording/replay layer that mirrors operad's LLM cassette
semantics.

## Files to create

| Path | Purpose |
|---|---|
| `apps_uthereal/retrieval/client.py` | Protocol + LiveRetrievalClient + RetrievalError |
| `apps_uthereal/retrieval/cassette.py` | CassetteRetrievalClient |
| `apps_uthereal/retrieval/keys.py` | canonical hashing for cassette keys |
| `apps_uthereal/tests/test_retrieval_client.py` | tests |
| `apps_uthereal/tests/fixtures/retrieval_cassette/` | sample cassette files |

## API surface

```python
# apps_uthereal/retrieval/client.py
from __future__ import annotations

from typing import Protocol
import httpx
from apps_uthereal.schemas.retrieval import RetrievalSpecification, RetrievalResult
from apps_uthereal.schemas.workflow import WorkspaceMetadata
from apps_uthereal.errors import RetrievalError


class RetrievalClient(Protocol):
    async def retrieve(
        self,
        spec: RetrievalSpecification,
        *,
        workspace_id: str,
    ) -> RetrievalResult: ...

    async def get_workspace_metadata(
        self,
        workspace_id: str,
    ) -> WorkspaceMetadata: ...

    async def aclose(self) -> None: ...


class LiveRetrievalClient:
    """HTTP client against a hosted RAG service.

    Endpoints (frozen — match this in the user's container):
      POST {base_url}/retrieve
        request: {"workspace_id": str, "spec": RetrievalSpecification}
        response: RetrievalResult

      GET {base_url}/workspaces/{workspace_id}/metadata
        response: WorkspaceMetadata
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    async def retrieve(self, spec, *, workspace_id) -> RetrievalResult: ...
    async def get_workspace_metadata(self, workspace_id) -> WorkspaceMetadata: ...
    async def aclose(self) -> None: ...


# apps_uthereal/retrieval/cassette.py
class CassetteRetrievalClient:
    """Record/replay wrapper around an inner RetrievalClient.

    Modes (mirror operad's cassette semantics, see C8):
      "record"          - always call inner; record the result; raise if inner is None
      "replay"          - read from disk only; raise CassetteMiss on miss
      "record-missing"  - replay hits, fall back to inner on miss + record

    Cassette layout under `cassette_dir`:
        retrieve/<key>.json     - one file per (workspace_id, spec) pair
        metadata/<workspace_id>.json
    """

    def __init__(
        self,
        *,
        cassette_dir: Path,
        inner: RetrievalClient | None = None,
        mode: Literal["record", "replay", "record-missing"] = "replay",
    ) -> None: ...

    async def retrieve(self, spec, *, workspace_id) -> RetrievalResult: ...
    async def get_workspace_metadata(self, workspace_id) -> WorkspaceMetadata: ...
    async def aclose(self) -> None: ...


class CassetteMiss(RetrievalError): ...


# apps_uthereal/retrieval/keys.py
def retrieve_key(*, workspace_id: str, spec: RetrievalSpecification) -> str:
    """sha256(workspace_id || canonical_json(spec))[:16]."""

def metadata_key(*, workspace_id: str) -> str:
    """workspace_id, sanitized for filename use."""
```

## Implementation notes

- **httpx.** Use `httpx.AsyncClient(timeout=timeout_s, headers=headers)`.
  Reuse one client across calls; close in `aclose`. Do not create a new
  client per call.
- **Errors.** Wrap any `httpx.HTTPStatusError`, `httpx.TimeoutException`,
  `httpx.RequestError` in `RetrievalError(reason=..., status=...,
  body=...)`. Never let raw httpx errors leak.
- **Canonical JSON for the key.** Field-sorted, no whitespace. Use
  `json.dumps(model.model_dump(mode="json"), sort_keys=True,
  separators=(",", ":"))`. Test that two equivalent specs produce equal
  keys.
- **Cassette files are JSON.** One file per call, schema:
  ```json
  {
    "kind": "retrieve" | "metadata",
    "key": "ab12...",
    "workspace_id": "...",
    "spec": {...}  // for retrieve
    "result": {...}
  }
  ```
- **Record mode requires `inner`.** `record` and `record-missing` raise
  `RetrievalError(reason="record_requires_inner")` if `inner is None`.
- **Replay miss.** Raise `CassetteMiss(reason="cassette_miss",
  kind="retrieve", key=key)` with enough context that the `fix` and
  `verify` commands can show a useful error.
- **Concurrent calls.** Cassette writes must be safe under concurrent
  retrieval (the runner fans out specs). Use a per-key file write
  (different keys → different files → no contention) and `os.replace`
  for atomic writes.

## Acceptance criteria

- [ ] `LiveRetrievalClient` POSTs/GETs to the documented endpoints with the
      documented payloads.
- [ ] `CassetteRetrievalClient(mode="replay")` returns a recorded
      `RetrievalResult` for a known key.
- [ ] `CassetteRetrievalClient(mode="replay")` raises `CassetteMiss` on a
      missing key.
- [ ] `CassetteRetrievalClient(mode="record-missing", inner=LiveClient)`
      replays hits and records misses.
- [ ] `retrieve_key(workspace_id="w", spec=specA) == retrieve_key(w, specA_reordered)`
      when the two specs are field-equivalent.
- [ ] No `httpx` exception propagates raw — all wrapped in
      `RetrievalError`.
- [ ] All operations are awaitable; nothing blocks the event loop.
- [ ] No imports from `uthereal_*`.

## Tests

- `test_live_client_retrieve_calls_correct_endpoint` — use `respx` to mock
  HTTP and assert URL/payload.
- `test_live_client_get_metadata_calls_correct_endpoint`.
- `test_live_client_wraps_http_errors` — respx returns 500; assert
  `RetrievalError` raised with `status=500`.
- `test_live_client_wraps_timeouts` — respx times out; assert
  `RetrievalError(reason="timeout")`.
- `test_cassette_replay_returns_recorded_result`.
- `test_cassette_replay_misses_raise_CassetteMiss`.
- `test_cassette_record_writes_file_atomically`.
- `test_cassette_record_missing_falls_back_then_records`.
- `test_retrieve_key_stable_under_field_reorder`.
- `test_concurrent_record_writes_dont_corrupt` — gather several
  retrieves with different keys.
- `test_aclose_closes_underlying_httpx_client`.

## Fixtures

A small mock server fixture in `conftest.py` (the file owned by 1-1 — do
NOT modify it; instead, add `tests/fixtures/mock_rag_server.py` and
import from it):

```python
# tests/fixtures/mock_rag_server.py
class MockRAGServer:
    """In-process FastAPI shim for tests.

    Use as:
        async with MockRAGServer().lifespan(httpx.AsyncClient()) as client:
            ...
    """
```

Or, simpler and probably better, use `respx` to mock httpx directly without
spinning up a real server. Choose one approach and document it.

## References

- `operad/core/runner.py` — operad's HTTP-call patterns and error
  wrapping.
- `respx` documentation for httpx mocking.
- The existing operad cassette implementation under `operad/runtime/`.
  Mirror its semantics (cassette miss diagnostics, key derivation).

## Notes

(Append discoveries here as you implement.)
