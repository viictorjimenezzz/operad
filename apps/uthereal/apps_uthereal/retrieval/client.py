from __future__ import annotations

"""Retrieval client protocol used by the Artemis runner.

Owner: 1-4-retrieval-client.
"""

from typing import Protocol

from apps_uthereal.schemas.retrieval import RetrievalResult, RetrievalSpecification
from apps_uthereal.schemas.workflow import WorkspaceMetadata


class RetrievalError(Exception):
    """Structured retrieval failure raised by retrieval clients."""

    def __init__(
        self,
        spec: RetrievalSpecification,
        status: int,
        body: str,
    ) -> None:
        self.spec = spec
        self.status = status
        self.body = body
        super().__init__(f"retrieval failed for {spec.spec_id}: {status} {body}")


class RetrievalClient(Protocol):
    """Protocol surface for retrieval backends."""

    async def retrieve(
        self,
        spec: RetrievalSpecification,
        *,
        workspace_id: str,
    ) -> RetrievalResult:
        """Retrieve text and image hits for one retrieval specification."""

    async def get_workspace_metadata(self, workspace_id: str) -> WorkspaceMetadata:
        """Return metadata needed to render retrieval inputs."""


__all__ = ["RetrievalClient", "RetrievalError"]
