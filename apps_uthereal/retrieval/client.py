from __future__ import annotations

"""Retrieval client protocol and live HTTP implementation.

Owner: 1-4-retrieval-client.
"""

from typing import Any, Protocol, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from apps_uthereal.schemas.retrieval import (
        RetrievalResult,
        RetrievalSpecification,
    )
    from apps_uthereal.schemas.workflow import WorkspaceMetadata


try:
    from apps_uthereal.errors import RetrievalError
except ModuleNotFoundError as exc:
    if exc.name != "apps_uthereal.errors":
        raise

    class RetrievalError(RuntimeError):
        """Raised when retrieval fails before a typed result can be returned."""

        def __init__(
            self,
            reason: str,
            *,
            spec: Any | None = None,
            status: int | None = None,
            body: str | None = None,
        ) -> None:
            self.reason = reason
            self.spec = spec
            self.status = status
            self.body = body
            super().__init__(self._message())

        def _message(self) -> str:
            parts = [f"RetrievalError(reason={self.reason!r})"]
            if self.status is not None:
                parts.append(f"status={self.status}")
            if self.body:
                parts.append(f"body={self.body}")
            return ", ".join(parts)


class RetrievalClient(Protocol):
    """Protocol for all retrieval backends used by the uthereal workflow."""

    async def retrieve(
        self,
        spec: RetrievalSpecification,
        *,
        workspace_id: str,
    ) -> RetrievalResult:
        """Retrieve evidence for one specification."""
        ...

    async def get_workspace_metadata(self, workspace_id: str) -> WorkspaceMetadata:
        """Fetch metadata needed to run retrieval for a workspace."""
        ...

    async def aclose(self) -> None:
        """Close any held network resources."""
        ...


def _retrieval_result_type() -> type[Any]:
    from apps_uthereal.schemas.retrieval import RetrievalResult

    return RetrievalResult


def _workspace_metadata_type() -> type[Any]:
    from apps_uthereal.schemas.workflow import WorkspaceMetadata

    return WorkspaceMetadata


class LiveRetrievalClient:
    """HTTP client against a hosted RAG service.

    Endpoints:
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
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_s, headers=headers)

    async def retrieve(
        self,
        spec: RetrievalSpecification,
        *,
        workspace_id: str,
    ) -> RetrievalResult:
        """POST a retrieval request and validate the typed result."""
        payload = {
            "workspace_id": workspace_id,
            "spec": spec.model_dump(mode="json"),
        }
        response = await self._request(
            "post",
            f"{self._base_url}/retrieve",
            spec=spec,
            json=payload,
        )
        return _retrieval_result_type().model_validate(response.json())

    async def get_workspace_metadata(self, workspace_id: str) -> WorkspaceMetadata:
        """GET typed workspace metadata."""
        response = await self._request(
            "get",
            f"{self._base_url}/workspaces/{workspace_id}/metadata",
        )
        return _workspace_metadata_type().model_validate(response.json())

    async def aclose(self) -> None:
        """Close the underlying ``httpx.AsyncClient``."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        *,
        spec: Any | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            if method == "post":
                response = await self._client.post(url, json=json)
            else:
                response = await self._client.get(url)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise RetrievalError(
                "http_status",
                spec=spec,
                status=exc.response.status_code,
                body=exc.response.text,
            ) from exc
        except httpx.TimeoutException as exc:
            raise RetrievalError("timeout", spec=spec, body=str(exc)) from exc
        except httpx.RequestError as exc:
            raise RetrievalError("request_error", spec=spec, body=str(exc)) from exc


def __getattr__(name: str) -> Any:
    """Provide the contract import path without creating an import cycle."""
    if name == "CassetteRetrievalClient":
        from apps_uthereal.retrieval.cassette import CassetteRetrievalClient

        return CassetteRetrievalClient
    raise AttributeError(name)


__all__ = [
    "CassetteRetrievalClient",
    "LiveRetrievalClient",
    "RetrievalClient",
    "RetrievalError",
]
