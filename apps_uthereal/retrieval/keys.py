from __future__ import annotations

"""Deterministic cassette key helpers for retrieval calls.

Owner: 1-4-retrieval-client.
"""

import hashlib
import json
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from apps_uthereal.schemas.retrieval import RetrievalSpecification


def canonical_json(spec: RetrievalSpecification) -> str:
    """Return field-sorted, whitespace-free JSON for a retrieval spec."""
    return json.dumps(
        spec.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )


def retrieve_key(*, workspace_id: str, spec: RetrievalSpecification) -> str:
    """Return ``sha256(workspace_id || canonical_json(spec))[:16]``."""
    raw = f"{workspace_id}{canonical_json(spec)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def metadata_key(*, workspace_id: str) -> str:
    """Return a filename-safe workspace metadata key."""
    return quote(workspace_id, safe="-_.~") or "_"


__all__ = ["canonical_json", "metadata_key", "retrieve_key"]
